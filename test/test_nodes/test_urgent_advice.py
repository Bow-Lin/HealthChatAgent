# tests/test_urgent_advice_node.py
import pytest
from typing import Dict, Any

try:
    from pocketflow import AsyncFlow as Flow
except ImportError:
    from pocketflow import Flow

from app.runtime.nodes.urgent_advice import UrgentAdviceNode


@pytest.mark.asyncio
async def test_urgent_advice_node_on_urgent_triage():
    shared: Dict[str, Any] = {
        "triage_level": "urgent",
        "triage_reasons": ["出现严重胸痛", "呼吸困难"],
        "to_persist": [],
        "warnings": [],
    }

    node = UrgentAdviceNode()
    node.successors = {}
    flow = Flow(start=node)

    action = await flow.run_async(shared)

    assert action == "ok"
    assert "assistant_reply" in shared
    reply = shared["assistant_reply"]
    # Must include default message and at least one reason
    assert "尽快线下就医" in reply
    assert "出现严重胸痛" in reply
    # Persisted correctly
    assert shared["to_persist"][-1] == {"role": "assistant", "content": reply}


@pytest.mark.asyncio
async def test_urgent_advice_node_on_non_urgent_triage():
    shared: Dict[str, Any] = {
        "triage_level": "non-urgent",
        "triage_reasons": [],
        "to_persist": [],
        "warnings": [],
    }

    node = UrgentAdviceNode()
    node.successors = {}
    flow = Flow(start=node)

    action = await flow.run_async(shared)

    assert action == "ok"
    reply = shared["assistant_reply"]
    assert "No urgent advice" in reply
    assert shared["to_persist"][-1]["content"] == reply
