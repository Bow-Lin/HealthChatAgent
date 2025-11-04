# app/runtime/nodes/urgent_advice.py
from __future__ import annotations
from typing import Any, Dict
from pocketflow import AsyncNode


class UrgentAdviceNode(AsyncNode):
    """Triggered when triage level is urgent.
    Prep: verify triage context
    Exec: produce urgent advice text (pure)
    Post: commit to shared + route
    """

    def __init__(self, message: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.message = (
            message
            or "根据分诊结果建议尽快线下就医或联系急救。如症状加重，请立即寻求紧急医疗服务。"
        )

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        # Extract triage info and prepare message payload
        triage_level = shared.get("triage_level", "non-urgent")
        reasons = shared.get("triage_reasons", [])
        return {"triage_level": triage_level, "reasons": reasons, "message": self.message}

    async def exec_async(self, prep: Dict[str, Any]) -> Dict[str, Any]:
        # Pure compute: choose response text
        if prep["triage_level"] != "urgent":
            # Node shouldn't normally run, but handle gracefully
            reply = "No urgent advice necessary."
        else:
            reply = prep["message"]
            if prep["reasons"]:
                reply += f"（原因：{'; '.join(prep['reasons'][:3])}）"
        return {"reply": reply}

    async def post_async(self, shared: Dict[str, Any], prep: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        # Commit side effects and route out
        reply = exec_res["reply"]
        shared["assistant_reply"] = reply
        shared.setdefault("to_persist", []).append({"role": "assistant", "content": reply})
        shared.setdefault("warnings", [])
        # Always finish with "ok" so flow can end cleanly
        return "ok"
