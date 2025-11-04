# tests/test_reply_extract_node.py
import pytest
from typing import Dict, Any

try:
    from pocketflow import AsyncFlow as Flow
except ImportError:
    from pocketflow import Flow

from app.runtime.nodes.reply_extract import ReplyExtractNode


@pytest.mark.asyncio
async def test_reply_extract_from_json_object_and_merge_warnings():
    shared: Dict[str, Any] = {
        "assistant_reply": '{"followups":["Recheck in 48h","Hydration"],"warnings":["High fever","Severe pain"]}',
        "warnings": ["System disclaimer"],   # base warnings already present
    }

    node = ReplyExtractNode()
    node.successors = {}
    flow = Flow(start=node)

    action = await flow.run_async(shared)

    assert action == "ok"
    assert shared["followups"] == ["Recheck in 48h", "Hydration"]
    # merged + dedup
    assert shared["warnings"] == ["System disclaimer", "High fever", "Severe pain"]


@pytest.mark.asyncio
async def test_reply_extract_from_heuristics_bullets_and_inline():
    # No JSON, rely on heuristic:
    # - bullet lines
    # - inline "Follow-ups: ..." split by separators
    reply_text = """
    Assessment: likely muscle strain.
    Follow-ups: gentle stretching; apply warm compress 2x/day
    - Avoid heavy lifting for 48 hours
    • Schedule a follow-up visit in 1 week
    """

    shared: Dict[str, Any] = {
        "assistant_reply": reply_text,
        "warnings": [],   # none yet
    }

    node = ReplyExtractNode()
    node.successors = {}
    flow = Flow(start=node)

    action = await flow.run_async(shared)
    assert action == "ok"

    fups = shared["followups"]
    # Order matters as extracted; check subset presence
    assert "gentle stretching" in fups
    assert "apply warm compress 2x/day" in fups
    assert "Avoid heavy lifting for 48 hours" in fups
    assert "Schedule a follow-up visit in 1 week" in fups

    # No extra warnings extracted from free text in current heuristics
    assert shared["warnings"] == []


@pytest.mark.asyncio
async def test_reply_extract_handles_empty_reply_gracefully():
    shared: Dict[str, Any] = {
        "assistant_reply": "",
        "warnings": ["System disclaimer"],
    }
    node = ReplyExtractNode()
    node.successors = {}
    flow = Flow(start=node)

    action = await flow.run_async(shared)
    assert action == "ok"
    assert shared["followups"] == []
    assert shared["warnings"] == ["System disclaimer"]
