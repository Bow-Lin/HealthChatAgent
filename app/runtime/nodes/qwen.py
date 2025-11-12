# app/runtime/nodes/deepseek.py
from __future__ import annotations

from typing import Dict, Any, List
from pocketflow import AsyncNode
from app.services.qwen_client import QwenClient

SYSTEM_PROMPT = (
    "You are a professional medical/massage specialist for preliminary guidance only. "
    "You are not a doctor. Always include safety notes and when to seek in-person care.用中文回答"
)


class QwenChatNode(AsyncNode):
    """LLM chat node with clean prep/exec/post lifecycle.
    - prep_async: gather repo history + build messages (+ optional prior summaries) + resolve client
    - exec_async: call LLM (pure compute, no side-effects)
    - post_async: write back to shared and return routing token
    """

    def __init__(self, *, temperature: float = 0.2, **kwargs) -> None:
        super().__init__(**kwargs)
        self.temperature = temperature

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        repo = shared["repo"]
        tenant_id = shared["tenant_id"]
        enc_id = shared["encounter_id"]
        user_text = shared.get("user_text", "")

        # 1) Build base messages
        messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

        # 2) Inject prior summaries (from HistoryLookupNode) as extra system context if available
        prior_summaries = shared.get("prior_summaries") or []
        if prior_summaries:
            ctx_lines = "\n".join(f"- {s}" for s in prior_summaries)
            messages.append({
                "role": "system",
                "content": "Context: Prior visit summaries (most recent first):\n" + ctx_lines,
            })

        # 3) Current encounter history from repo
        history = await repo.get_messages(tenant_id, enc_id)
        print("--------------------------run here")
        print(history)
        for m in history:
            messages.append({"role": m.role, "content": m.content_json})

        # 4) Current user query
        messages.append({"role": "user", "content": user_text})

        # 5) Qwen client
        client: QwenClient = shared.get("deepseek_client") or QwenClient()

        return {
            "messages": messages,
            "client": client,
            "temperature": self.temperature,
        }

    async def exec_async(self, prep: Dict[str, Any]) -> Dict[str, Any]:
        client: QwenClient = prep["client"]
        reply = await client.chat(messages=prep["messages"], temperature=prep["temperature"])
        return {"reply": reply}

    async def exec_fallback_async(self, prep: Dict[str, Any], exc: Exception) -> Dict[str, Any]:
        return {
            "reply": "Sorry, I'm having trouble generating a response right now. "
                     "Please try again soon.",
            "error": str(exc),
            "degraded": True,
        }

    async def post_async(self, shared: Dict[str, Any], prep: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        reply = exec_res["reply"]
        shared["assistant_reply"] = reply
        shared.setdefault("to_persist", []).append({"role": "assistant", "content": reply})
        return "ok"
