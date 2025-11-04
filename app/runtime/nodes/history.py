from __future__ import annotations
from typing import Any, Dict, List

class HistoryFetchNode:
    async def exec(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        repo = shared["repo"]
        tenant_id = shared["tenant_id"]
        encounter_id = shared["encounter_id"]
        summaries: List[str] = await repo.get_recent_encounter_summaries(tenant_id, encounter_id)
        shared["history_summaries"] = summaries
        return shared
