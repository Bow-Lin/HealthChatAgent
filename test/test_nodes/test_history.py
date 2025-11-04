# tests/test_history_lookup_node.py
import pytest
from typing import Any, Dict, List, Optional

from pocketflow import AsyncFlow as Flow

from app.runtime.nodes.history import HistoryLookupNode


class FakeRepoWithPrior:
    def __init__(self, prior: List[str]) -> None:
        self._prior = prior

    async def get_recent_encounter_summaries(self, tenant_id: str, current_enc_id: str, limit: int) -> List[str]:
        # Simulate prior encounters excluding the current one
        return self._prior[:limit]


class FakeRepoWithoutPrior:
    async def get_recent_encounter_summaries(self, tenant_id: str, current_enc_id: str, limit: int) -> List[str]:
        return []


@pytest.mark.asyncio
async def test_history_lookup_has_history_path():
    shared: Dict[str, Any] = {
        "tenant_id": "t1",
        "encounter_id": "e123",
        "repo": FakeRepoWithPrior(["2025-10-02: 肩颈不适，建议热敷", "2025-08-17: 腰背酸痛，轻度拉伸"]),
    }

    node = HistoryLookupNode(limit=3)
    node.successors = {}  # end here for unit test
    flow = Flow(start=node)

    action = await flow.run_async(shared)

    assert action == "has_history"
    assert shared["has_prior_history"] is True
    assert shared["prior_summaries"] == ["2025-10-02: 肩颈不适，建议热敷", "2025-08-17: 腰背酸痛，轻度拉伸"]


@pytest.mark.asyncio
async def test_history_lookup_no_history_path():
    shared: Dict[str, Any] = {
        "tenant_id": "t1",
        "encounter_id": "e999",
        "repo": FakeRepoWithoutPrior(),
    }

    node = HistoryLookupNode(limit=5)
    node.successors = {}
    flow = Flow(start=node)

    action = await flow.run_async(shared)

    assert action == "no_history"
    assert shared["has_prior_history"] is False
    assert shared["prior_summaries"] == []
