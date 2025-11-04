# app/runtime/nodes/persist.py
from __future__ import annotations
from typing import Any, Dict, List
from pocketflow import Node

class PersistNode(Node):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def exec(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        repo = shared["repo"]
        tenant_id = shared["tenant_id"]
        encounter_id = shared["encounter_id"]
        user_text = shared["user_text"]
        to_persist: List[Dict[str, Any]] = shared.get("to_persist", [])

        async with repo.transaction() as s:
            await repo.append_message(tenant_id, encounter_id, "user", user_text, session=s)
            for item in to_persist:
                await repo.append_message(
                    tenant_id,
                    encounter_id,
                    item.get("role", "assistant"),
                    item.get("content", ""),
                    item.get("content_json"),
                    session=s,
                )
            await repo.audit(
                tenant_id,
                "chat.append",
                "encounter",
                str(encounter_id),
                {"count": 1 + len(to_persist)},
                session=s,
            )
        return shared
