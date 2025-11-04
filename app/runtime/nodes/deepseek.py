# app/runtime/nodes/deepseek.py
from typing import Dict, Any, List
from services.deepseek_client import DeepSeekClient
from pocketflow import Node

SYSTEM_PROMPT = (
    "You are a medical/massage Q&A assistant for preliminary guidance only. "
    "You are not a doctor. Always include safety notes and when to seek in-person care."
)

class DeepSeekChatNode(Node):
    def __init__(self, *, temperature: float = 0.2) -> None:
        self.temperature = temperature

    async def exec(self, shared: Dict[str, Any]) -> None:
        repo = shared["repo"]
        tenant_id = shared["tenant_id"]
        enc_id = shared["encounter_id"]

        # Build conversation messages
        history = await repo.get_messages(tenant_id, enc_id)
        messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in history:
            messages.append({"role": m.role, "content": m.content_text})
        messages.append({"role": "user", "content": shared["user_text"]})

        # Get DeepSeek client from shared, or create a short-lived one.
        client: DeepSeekClient = shared.get("deepseek_client") or DeepSeekClient()

        reply = await client.chat(messages=messages, temperature=self.temperature)

        shared["assistant_reply"] = reply
        shared.setdefault("to_persist", []).append({"role": "assistant", "content": reply})
