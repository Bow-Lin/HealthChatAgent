# tests/test_deepseek_node_with_history.py
import pytest
from dataclasses import dataclass
from typing import List, Dict, Any

try:
    from pocketflow import AsyncFlow as Flow
except ImportError:
    from pocketflow import Flow

from app.runtime.nodes.deepseek import DeepSeekChatNode, SYSTEM_PROMPT


@dataclass
class Msg:
    role: str
    content_text: str


class FakeRepo:
    def __init__(self, history: List[Msg]) -> None:
        self._history = history

    async def get_messages(self, tenant_id: str, enc_id: str) -> List[Msg]:
        return self._history


class FakeDeepSeekClient:
    def __init__(self) -> None:
        self.last_args: Dict[str, Any] = {}

    async def chat(self, *, messages: List[Dict[str, str]], temperature: float) -> str:
        self.last_args = {"messages": messages, "temperature": temperature}
        return "MOCK_REPLY_WITH_HISTORY"


@pytest.mark.asyncio
async def test_deepseek_includes_prior_summaries_when_present():
    history = [Msg("user", "earlier dizziness"), Msg("assistant", "suggest rest")]
    repo = FakeRepo(history)
    ds = FakeDeepSeekClient()

    shared: Dict[str, Any] = {
        "tenant_id": "t1",
        "encounter_id": "e1",
        "user_text": "I have mild back pain today",
        "repo": repo,
        "deepseek_client": ds,
        "to_persist": [],
        "warnings": [],
        # Injected by HistoryLookupNode earlier in the flow:
        "has_prior_history": True,
        "prior_summaries": [
            "2025-10-02: 肩颈不适，建议热敷",
            "2025-08-17: 腰背酸痛，轻度拉伸",
        ],
    }

    node = DeepSeekChatNode(temperature=0.5, max_retries=1)
    node.successors = {}
    flow = Flow(start=node)

    action = await flow.run_async(shared)

    assert action == "ok"
    assert shared["assistant_reply"] == "MOCK_REPLY_WITH_HISTORY"

    called = ds.last_args
    msgs = called["messages"]
    # 1: system prompt
    assert msgs[0] == {"role": "system", "content": SYSTEM_PROMPT}
    # 2: system context with prior summaries
    assert msgs[1]["role"] == "system"
    assert "Context: Prior visit summaries" in msgs[1]["content"]
    assert "肩颈不适" in msgs[1]["content"]
    assert "腰背酸痛" in msgs[1]["content"]
    # 3..n: historical messages of current encounter (order preserved)
    assert msgs[2]["role"] == "user" and msgs[2]["content"] == "earlier dizziness"
    assert msgs[3]["role"] == "assistant" and msgs[3]["content"] == "suggest rest"
    # last: current user input
    assert msgs[-1] == {"role": "user", "content": shared["user_text"]}
    assert abs(called["temperature"] - 0.5) < 1e-9


@pytest.mark.asyncio
async def test_deepseek_without_prior_summaries():
    history = [Msg("user", "earlier dizziness"), Msg("assistant", "suggest rest")]
    repo = FakeRepo(history)
    ds = FakeDeepSeekClient()

    shared: Dict[str, Any] = {
        "tenant_id": "t1",
        "encounter_id": "e1",
        "user_text": "I have mild back pain today",
        "repo": repo,
        "deepseek_client": ds,
        "to_persist": [],
        "warnings": [],
        # No prior history injected
        "has_prior_history": False,
        "prior_summaries": [],
    }

    node = DeepSeekChatNode(temperature=0.3, max_retries=1)
    node.successors = {}
    flow = Flow(start=node)

    action = await flow.run_async(shared)

    assert action == "ok"
    # assert shared["assistant_reply"] == "MOCK_REPLY_NO_HISTORY"

    called = ds.last_args
    msgs = called["messages"]

    # Should start with system prompt, then directly current encounter history (no extra system context)
    assert msgs[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert msgs[1]["role"] == "user" and msgs[1]["content"] == "earlier dizziness"
    assert msgs[2]["role"] == "assistant" and msgs[2]["content"] == "suggest rest"
    assert msgs[-1] == {"role": "user", "content": shared["user_text"]}
    assert abs(called["temperature"] - 0.3) < 1e-9