# tests/test_flow_integration.py
import pytest
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.runtime.flow import make_clinical_flow
from app.runtime.nodes.deepseek import SYSTEM_PROMPT


# -----------------------------
# Fakes
# -----------------------------
@dataclass
class Msg:
    role: str
    content_text: str


class _FakeTxnCtx:
    def __init__(self, repo):
        self.repo = repo
    async def __aenter__(self):
        return self.repo
    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeRepo:
    """In-memory fake repo with transaction semantics."""
    def __init__(self, history: List[Msg], prior_summaries: List[str] | None = None) -> None:
        self._history = history
        self._prior = prior_summaries or []
        self.messages: List[Dict[str, Any]] = []
        self.audits: List[Dict[str, Any]] = []

    # Flow nodes expect these:
    async def get_messages(self, tenant_id: str, enc_id: str) -> List[Msg]:
        return self._history

    async def get_recent_encounter_summaries(self, tenant_id: str, encounter_id: str, *, session=None, limit: int = 5) -> List[str]:
        return self._prior[:limit]

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
        assert session is self, "append_message must be called inside transaction"
        self.messages.append(
            {
                "tenant_id": tenant_id,
                "encounter_id": encounter_id,
                "role": role,
                "content": content,
                "content_json": content_json,
            }
        )

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
        assert session is self, "audit must be called inside transaction"
        self.audits.append(
            {
                "tenant_id": tenant_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "meta_json": meta_json or {},
            }
        )


class FakeDeepSeekClient:
    """Captures last call and returns a deterministic JSON reply to exercise reply_extract."""
    def __init__(self) -> None:
        self.last_args: Dict[str, Any] | None = None

    async def chat(self, *, messages: List[Dict[str, str]], temperature: float) -> str:
        self.last_args = {"messages": messages, "temperature": temperature}
        # JSON block so ReplyExtractNode can parse deterministically
        return '{"followups":["Recheck in 48h"], "warnings":["See doctor if worse"]}'


# -----------------------------
# Tests
# -----------------------------
@pytest.mark.asyncio
async def test_flow_ok_path_persists_and_extracts():
    # history of the current encounter
    history = [Msg("user", "earlier dizziness"), Msg("assistant", "suggest rest")]

    repo = FakeRepo(
        history=history,
        prior_summaries=["2025-10-02: 肩颈不适，建议热敷", "2025-08-17: 腰背酸痛，轻度拉伸"],
    )
    ds = FakeDeepSeekClient()

    shared: Dict[str, Any] = {
        "tenant_id": "t1",
        "encounter_id": "e1",
        "user_text": "I have mild back pain today",
        "repo": repo,
        "deepseek_client": ds,
        "warnings": [],       # triage 会追加免责声明
        "to_persist": [],     # deepseek -> post 会把 assistant 回复追加进来
    }

    flow = make_clinical_flow()
    action = await flow.run_async(shared)

    # Flow result
    assert action == "ok"

    # DeepSeek was called with system prompt, prior summaries context, history, and current user
    assert ds.last_args is not None
    messages = ds.last_args["messages"]
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert messages[1]["role"] == "system" and "Prior visit summaries" in messages[1]["content"]
    assert messages[-1] == {"role": "user", "content": shared["user_text"]}

    # ReplyExtract picked up followups + merged warnings
    assert shared["followups"] == ["Recheck in 48h"]
    # triage 免责声明 + deepseek JSON warnings
    assert any("not a medical diagnosis" in w or "seek in-person care" in w for w in shared["warnings"])
    assert any("See doctor if worse" in w for w in shared["warnings"])

    # Persist wrote user + assistant（deepseek）两条消息，并做了审计
    assert [m["role"] for m in repo.messages] == ["user", "assistant"]
    assert repo.messages[0]["content"] == shared["user_text"]
    # assistant content来自 deepseek 的 post（这里是 JSON 字符串本体）
    assert repo.audits and repo.audits[0]["meta_json"]["count"] == 2


@pytest.mark.asyncio
async def test_flow_urgent_path_skips_deepseek_and_persists():
    # 输入触发 urgent（SafetyTriageNode 的规则中含 severe chest pain）
    history = [Msg("user", "previous note"), Msg("assistant", "ok")]
    repo = FakeRepo(history=history, prior_summaries=[])

    ds = FakeDeepSeekClient()

    shared: Dict[str, Any] = {
        "tenant_id": "t2",
        "encounter_id": "e2",
        "user_text": "I have severe chest pain and difficulty breathing",
        "repo": repo,
        "deepseek_client": ds,
        "warnings": [],
        "to_persist": [],
    }

    flow = make_clinical_flow()
    action = await flow.run_async(shared)

    assert action == "ok"

    # DeepSeek should NOT be called on urgent path
    assert ds.last_args is None

    # UrgentAdviceNode should have produced an assistant reply and it should be persisted
    assert [m["role"] for m in repo.messages] == ["user", "assistant"]
    assert "尽快线下就医" in repo.messages[1]["content"]  # Chinese urgent advice content

    # Audit count == 2 (user + urgent advice)
    assert repo.audits and repo.audits[0]["meta_json"]["count"] == 2

    # Warnings should contain triage disclaimer at least
    assert any("not a medical diagnosis" in w or "seek in-person care" in w for w in shared["warnings"])
