# app/runtime/nodes/history_lookup.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pocketflow import AsyncNode


class HistoryLookupNode(AsyncNode):
    """
    Check whether the user (tenant) has prior encounters and extract brief summaries.
    - prep_async: I/O to repo (fetch prior summaries), shape data for exec
    - exec_async: pure compute (decide routing token and normalize list)
    - post_async: write flags/results back to shared, return routing token
    """

    def __init__(self, *, limit: int = 3, **kwargs) -> None:
        super().__init__(**kwargs)
        self.limit = limit

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        repo = shared["repo"]
        tenant_id = shared["tenant_id"]
        current_enc_id = shared.get("encounter_id")


        fetcher = getattr(repo, "get_recent_encounter_summaries", None)
        summaries: List[str] = []

        if callable(fetcher):
            summaries = await fetcher(tenant_id, current_enc_id, limit=self.limit)
        else:
            alt = getattr(repo, "get_summaries", None)
            if callable(alt):
                all_summaries = await alt(tenant_id)
                summaries = list(all_summaries or [])[: self.limit]


        # Normalize to strings and strip blanks
        norm: List[str] = []
        for s in summaries or []:
            t = ("" if s is None else str(s)).strip()
            if t:
                norm.append(t)

        return {
            "summaries": norm[: self.limit],
        }

    async def exec_async(self, prep: Dict[str, Any]) -> Dict[str, Any]:
        summaries: List[str] = prep["summaries"]
        has_history = len(summaries) > 0
        # Routing suggestion: "has_history" vs "no_history"
        route = "has_history" if has_history else "no_history"
        return {"has_history": has_history, "summaries": summaries, "route": route}

    async def post_async(self, shared: Dict[str, Any], prep: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        shared["has_prior_history"] = exec_res["has_history"]
        shared["prior_summaries"] = exec_res["summaries"]
        return exec_res["route"]
