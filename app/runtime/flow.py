# app/runtime/flow.py
from __future__ import annotations

from pocketflow import AsyncFlow
from app.runtime.nodes.triage import SafetyTriageNode
from app.runtime.nodes.history import HistoryLookupNode
from app.runtime.nodes.deepseek import DeepSeekChatNode
from app.runtime.nodes.qwen import QwenChatNode
from app.runtime.nodes.reply_extract import ReplyExtractNode
from app.runtime.nodes.persist import PersistNode
from app.runtime.nodes.urgent_advice import UrgentAdviceNode


def make_clinical_flow() -> AsyncFlow:
    """Clinical chat flow:
    triage → (urgent → urgent_advice → persist)
            → (ok → history_lookup → deepseek → reply_extract → persist)
    """

    # Instantiate all nodes
    triage = SafetyTriageNode()
    history_lookup = HistoryLookupNode()
    deepseek = DeepSeekChatNode()
    reply_extract = ReplyExtractNode()
    persist = PersistNode()
    urgent = UrgentAdviceNode()

    # --- Routing setup ---

    # 1. triage routes
    triage.successors = {
        "urgent": urgent,
        "ok": history_lookup,
    }

    # 2. normal (ok) path
    history_lookup.successors = {
        "has_history": deepseek,   # has prior history → deepseek
        "no_history": deepseek,    # no prior history → still deepseek
    }
    deepseek.successors = {"ok": reply_extract}
    reply_extract.successors = {"ok": persist}

    # 3. urgent path
    urgent.successors = {"ok": persist}

    # --- Flow entry point ---
    return AsyncFlow(start=triage)


def make_clinical_flow_qwen() -> AsyncFlow:
    """Clinical chat flow:
    triage → (urgent → urgent_advice → persist)
            → (ok → history_lookup → deepseek → reply_extract → persist)
    """

    # Instantiate all nodes
    triage = SafetyTriageNode()
    history_lookup = HistoryLookupNode()
    qwen = QwenChatNode()
    reply_extract = ReplyExtractNode()
    persist = PersistNode()
    urgent = UrgentAdviceNode()

    # --- Routing setup ---

    # 1. triage routes
    triage.successors = {
        "urgent": urgent,
        "ok": history_lookup,
    }

    # 2. normal (ok) path
    history_lookup.successors = {
        "has_history": qwen,   # has prior history → qwen
        "no_history": qwen,    # no prior history → still qwen
    }
    qwen.successors = {"ok": reply_extract}
    reply_extract.successors = {"ok": persist}

    # 3. urgent path
    urgent.successors = {"ok": persist}

    # --- Flow entry point ---
    return AsyncFlow(start=triage)
