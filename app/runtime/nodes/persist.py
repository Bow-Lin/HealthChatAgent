# app/runtime/nodes/persist.py
from __future__ import annotations
from typing import Any, Dict, List
from copy import deepcopy
from pocketflow import AsyncNode


class PersistNode(AsyncNode):
    """
    Persist chat messages and audit in a single transaction.
    - prep_async: snapshot inputs (no side-effects)
    - exec_async: compute a write plan (no side-effects)
    - post_async: execute DB writes in a transaction and route
    """

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        repo = shared["repo"]
        tenant_id = shared["tenant_id"]
        encounter_id = shared["encounter_id"]
        user_text = str(shared.get("user_text", ""))

        # Snapshot to_persist to avoid later mutation during flow
        to_persist_raw = shared.get("to_persist", [])
        to_persist: List[Dict[str, Any]] = deepcopy(to_persist_raw) if isinstance(to_persist_raw, list) else []

        return {
            "repo": repo,
            "tenant_id": tenant_id,
            "encounter_id": encounter_id,
            "user_text": user_text,
            "to_persist": to_persist,
        }

    async def exec_async(self, prep: Dict[str, Any]) -> Dict[str, Any]:
        # Build a write plan: first the user message, then assistant/system items.
        plan: List[Dict[str, Any]] = [{
            "role": "user",
            "content": prep["user_text"],
            "content_json": None,
        }]
        for item in prep["to_persist"]:
            plan.append({
                "role": item.get("role", "assistant"),
                "content": item.get("content", ""),
                "content_json": item.get("content_json"),
            })
        return {
            "plan": plan,
            "audit_meta": {"count": len(plan)},
        }

    async def post_async(self, shared: Dict[str, Any], prep: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        repo = prep["repo"]
        tenant_id = prep["tenant_id"]
        encounter_id = prep["encounter_id"]
        plan: List[Dict[str, Any]] = exec_res["plan"]

        # Execute writes in a single transaction
        async with repo.transaction() as s:
            for msg in plan:
                await repo.append_message(
                    tenant_id,
                    encounter_id,
                    msg["role"],
                    msg["content"],
                    msg.get("content_json"),
                    session=s,
                )
            await repo.audit(
                tenant_id,
                "chat.append",
                "encounter",
                str(encounter_id),
                exec_res["audit_meta"],
                session=s,
            )

        # Optionally clear "to_persist" to indicate they've been flushed
        shared["last_persist_count"] = len(plan)
        return "ok"
