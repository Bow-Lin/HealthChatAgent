# tests/test_nodes/test_history.py
import pytest
from app.runtime.nodes.history import HistoryFetchNode

class DummyRepo:
    def __init__(self, data):
        self.data = data
        self.calls = []

    async def get_recent_encounter_summaries(self, tenant_id, encounter_id, limit: int = 5):
        self.calls.append((tenant_id, encounter_id, limit))
        return self.data

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.mark.asyncio
async def test_history_empty():
    node = HistoryFetchNode()
    repo = DummyRepo([])
    shared = {
        "repo": repo,
        "tenant_id": "t1",
        "encounter_id": "e1",
    }
    out = await node.exec(shared)
    assert out["history_summaries"] == []
    assert repo.calls[0][0] == "t1"
    assert repo.calls[0][1] == "e1"

@pytest.mark.asyncio
async def test_history_multiple_and_order():
    node = HistoryFetchNode()
    repo = DummyRepo(["s1", "s2", "s3"])
    shared = {
        "repo": repo,
        "tenant_id": "t2",
        "encounter_id": "e9",
    }
    out = await node.exec(shared)
    assert out["history_summaries"] == ["s1", "s2", "s3"]
    assert repo.calls[0] == ("t2", "e9", 5)
