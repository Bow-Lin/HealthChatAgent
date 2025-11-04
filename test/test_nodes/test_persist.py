# tests/test_persist_node.py
import pytest
from typing import Any, Dict, List, Optional

try:
    from pocketflow import AsyncFlow as Flow
except ImportError:
    from pocketflow import Flow

from app.runtime.nodes.persist import PersistNode


# ---- Fakes ------------------------------------------------------------------

class _FakeTxnCtx:
    def __init__(self, repo):
        self.repo = repo
    async def __aenter__(self):
        # mimic session object by passing repo itself to methods
        return self.repo
    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeRepo:
    """A minimal in-memory repo capturing writes and audits, with a txn context."""
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.audits: List[Dict[str, Any]] = []
        self._in_txn = False

    def transaction(self):
        return _FakeTxnCtx(self)

    async def append_message(
        self,
        tenant_id: str,
        encounter_id: str,
        role: str,
        content: str,
        content_json: Optional[dict] = None,
        *,
        session=None,
    ):
        assert session is self  # ensure we are inside "transaction"
        self.messages.append({
            "tenant_id": tenant_id,
            "encounter_id": encounter_id,
            "role": role,
            "content": content,
            "content_json": content_json,
        })

    async def audit(
        self,
        tenant_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        meta_json: Optional[dict] = None,
        *,
        session=None,
    ):
        assert session is self
        self.audits.append({
            "tenant_id": tenant_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "meta_json": meta_json or {},
        })


# ---- Tests ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_persist_node_writes_user_and_assistant_and_audit():
    repo = FakeRepo()
    shared: Dict[str, Any] = {
        "repo": repo,
        "tenant_id": "t1",
        "encounter_id": "e1",
        "user_text": "I have mild back pain today",
        "to_persist": [
            {"role": "assistant", "content": "Ok, noted."},
            {"role": "assistant", "content": "Apply warm compress 2x/day"},
        ],
    }

    node = PersistNode()
    node.successors = {}
    flow = Flow(start=node)

    action = await flow.run_async(shared)

    assert action == "ok"
    # Order: user first, then assistant items
    assert [m["role"] for m in repo.messages] == ["user", "assistant", "assistant"]
    assert repo.messages[0]["content"] == "I have mild back pain today"
    assert repo.messages[1]["content"] == "Ok, noted."
    assert repo.messages[2]["content"] == "Apply warm compress 2x/day"

    # Audit with correct count
    assert len(repo.audits) == 1
    assert repo.audits[0]["action"] == "chat.append"
    assert repo.audits[0]["resource_type"] == "encounter"
    assert repo.audits[0]["resource_id"] == "e1"
    assert repo.audits[0]["meta_json"]["count"] == 3

    # Shared updated
    assert shared["last_persist_count"] == 3


@pytest.mark.asyncio
async def test_persist_node_handles_empty_to_persist():
    repo = FakeRepo()
    shared: Dict[str, Any] = {
        "repo": repo,
        "tenant_id": "t1",
        "encounter_id": "e2",
        "user_text": "Hello",
        "to_persist": [],
    }

    node = PersistNode()
    node.successors = {}
    flow = Flow(start=node)

    action = await flow.run_async(shared)

    assert action == "ok"
    # Only the user message is stored
    assert len(repo.messages) == 1
    assert repo.messages[0]["role"] == "user"
    assert repo.messages[0]["content"] == "Hello"

    # Audit count = 1
    assert repo.audits and repo.audits[0]["meta_json"]["count"] == 1
    assert shared["last_persist_count"] == 1
