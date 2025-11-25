# app/runtime/nodes/iflow.py
from __future__ import annotations

from typing import Dict, Any, List
from pocketflow import AsyncNode
from app.services.iflow_client import IFlowClient

SYSTEM_PROMPT = (
    "你是一位经验丰富的中医推拿专家，擅长运用中医理论进行辨证指导与推拿调理。"
    "你可以根据用户的身体状况，提供中医知识讲解、养生建议和推拿指导。"
    "在回答时，请用第一人称与用户交流，例如“你需要注意脾胃调养”、“我现在会为你做肩颈放松”。"
    "在给出推拿建议后，请描述实际情况下，在你的店里你将如何为用户提供推拿服务，包括手法、部位和目的。"
    "同时，请务必提醒用户：你提供的仅是健康指导与推拿建议，不能替代医生的诊断或治疗。"
    "牢记，你就是专业的推拿师，必要时你可以推荐客户去医院，但不要推荐他们去找别的推拿师。"
    "若出现明显疼痛、麻木或持续不适，应及时前往正规医院就诊。"
)



class IFlowChatNode(AsyncNode):
    """LLM chat node using iFlow/Qwen3 with optional streaming."""

    def __init__(self, *, temperature: float = 0.2, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.temperature = temperature

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        repo = shared["repo"]
        tenant_id = shared["tenant_id"]
        enc_id = shared["encounter_id"]

        # Prefer "input_text" (used by your chat endpoints), fallback to "user_text"
        user_text = (
            shared.get("input_text")
            or shared.get("user_text")
            or ""
        )

        # Whether caller wants streaming
        stream = bool(shared.get("stream"))

        # 1) Base system prompt
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        # 2) Optional prior summaries from HistoryLookupNode
        prior_summaries = shared.get("prior_summaries") or []
        if prior_summaries:
            ctx_lines = "\n".join(f"- {s}" for s in prior_summaries)
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Context: Prior visit summaries (most recent first):\n"
                        + ctx_lines
                    ),
                }
            )

        # 3) Current encounter message history
        history = await repo.get_messages(tenant_id, enc_id)
        for m in history:
            # Prefer plain content; fallback to content_json if present
            content = getattr(m, "content", None)
            if content is None and hasattr(m, "content_json"):
                content = m.content_json
            if not content:
                continue
            messages.append({"role": m.role, "content": content})

        # 4) Current user query
        messages.append({"role": "user", "content": user_text})

        # 5) iFlow client (allow injection via shared for testing)
        client: IFlowClient = shared.get("iflow_client") or IFlowClient()

        return {
            "messages": messages,
            "client": client,
            "temperature": self.temperature,
            "stream": stream,
        }

    async def exec_async(self, prep: Dict[str, Any]) -> Dict[str, Any]:
        client: IFlowClient = prep["client"]
        stream: bool = bool(prep.get("stream"))

        if True:
            # Streaming: get async iterator of text chunks
            reply_stream = await client.achat_completion(
                messages=prep["messages"],
                temperature=prep["temperature"],
                model="qwen3-max",
                stream=True,
            )
            return {"reply": reply_stream}

        # Non-streaming: get full text
        reply_text = await client.achat_completion(
            messages=prep["messages"],
            temperature=prep["temperature"],
            model="qwen3-max",
            stream=False,
        )
        return {"reply": reply_text}

    async def exec_fallback_async(
        self,
        prep: Dict[str, Any],
        exc: Exception,
    ) -> Dict[str, Any]:
        return {
            "reply": (
                "Sorry, I'm having trouble generating a response right now. "
                "Please try again soon."
            ),
            "error": str(exc),
            "degraded": True,
        }

    async def post_async(
        self,
        shared: Dict[str, Any],
        prep: Dict[str, Any],
        exec_res: Dict[str, Any],
    ) -> str:
        reply = exec_res["reply"]

        if hasattr(reply, "__aiter__"):
            # Streaming path:
            # - expose the stream via a dedicated key
            # - keep assistant_reply as a string for downstream nodes
            shared["assistant_reply_stream"] = reply
            shared.setdefault("assistant_reply", "")
        else:
            text = reply or ""
            shared["assistant_reply"] = text
            shared.setdefault("to_persist", []).append(
                {"role": "assistant", "content": text}
            )

        return "ok"
