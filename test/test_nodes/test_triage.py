# tests/test_nodes/test_triage.py
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import re
import pytest

from app.runtime.nodes.triage import SafetyTriageNode, TriageRule

pytestmark = pytest.mark.asyncio


class _DummyNode:
    """A no-op next node that records whether it was executed and with which branch."""
    def __init__(self, tag: str):
        self.tag = tag
        self.calls = 0
        self.last_shared = None

    async def exec(self, shared: dict):
        self.calls += 1
        self.last_shared = dict(shared)  # shallow copy for assertions
        shared["branch"] = self.tag
        return None


async def test_triage_urgent_branch_and_shared_fields():
    triage = SafetyTriageNode()
    urgent_node = _DummyNode("urgent")
    ok_node = _DummyNode("ok")

    triage.on("urgent", urgent_node).on("ok", ok_node)

    shared = {
        "user_text": "I have severe chest pain and I'm short of breath.",
        "tenant_id": "t1",
        "encounter_id": "e1",
    }

    await triage.exec(shared)

    # branched to urgent
    assert shared["triage_level"] == "urgent"
    assert shared["branch"] == "urgent"
    assert urgent_node.calls == 1
    assert ok_node.calls == 0

    # reasons and disclaimer
    assert isinstance(shared.get("triage_reasons"), list)
    assert shared["triage_reasons"]  # should not be empty for such text
    assert "warnings" in shared and len(shared["warnings"]) >= 1

    # triage note present
    assert "triage_note" in shared
    assert shared["triage_note"].lower().startswith("triage:")


async def test_triage_non_urgent_branch_when_no_match():
    triage = SafetyTriageNode()
    urgent_node = _DummyNode("urgent")
    ok_node = _DummyNode("ok")

    triage.on("urgent", urgent_node).on("ok", ok_node)

    shared = {
        "user_text": "Mild seasonal allergy with occasional sneezing.",
        "tenant_id": "t1",
        "encounter_id": "e2",
    }

    await triage.exec(shared)

    assert shared["triage_level"] == "non-urgent"
    assert shared["branch"] == "ok"
    assert urgent_node.calls == 0
    assert ok_node.calls == 1
    assert isinstance(shared.get("triage_reasons"), list)
    assert not shared["triage_reasons"]  # no red flags
    assert "triage_note" in shared


async def test_triage_custom_rules_override_defaults():
    # Provide custom rules only; defaults should not apply.
    custom_rules = [
        TriageRule(pattern=re.compile(r"\bmild headache\b", re.I), level="urgent", reason="mild headache flagged")
    ]
    triage = SafetyTriageNode(rules=custom_rules)
    urgent_node = _DummyNode("urgent")
    ok_node = _DummyNode("ok")
    triage.on("urgent", urgent_node).on("ok", ok_node)

    shared = {
        "user_text": "I have a mild headache for two hours.",
        "tenant_id": "t1",
        "encounter_id": "e3",
    }

    await triage.exec(shared)

    assert shared["triage_level"] == "urgent"
    assert shared["branch"] == "urgent"
    assert urgent_node.calls == 1
    assert ok_node.calls == 0
    assert "mild headache flagged" in shared["triage_reasons"]


async def test_disclaimer_appended_once():
    triage = SafetyTriageNode()
    ok_node = _DummyNode("ok")
    triage.on("ok", ok_node)

    shared = {
        "user_text": "Sore throat for two days.",
        "warnings": [],  # pre-existing list to check duplication behavior
    }

    await triage.exec(shared)
    first_len = len(shared["warnings"])

    # run again; disclaimer should not duplicate
    await triage.exec(shared)
    second_len = len(shared["warnings"])

    assert first_len >= 1
    assert second_len == first_len  # no duplicates


async def test_branching_without_wiring_returns_gracefully():
    # If no next node is wired, exec should not raise.
    triage = SafetyTriageNode()
    shared = {"user_text": "No obvious red flags mentioned."}
    await triage.exec(shared)

    assert shared["triage_level"] in ("urgent", "non-urgent")
    assert "triage_note" in shared
