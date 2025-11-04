# app/runtime/flow.py
from __future__ import annotations
from typing import Any, Dict
from pocketflow import Flow
from app.runtime.nodes.triage import SafetyTriageNode
from app.runtime.nodes.history import HistoryFetchNode
from app.runtime.nodes.deepseek import DeepSeekChatNode
from app.runtime.nodes.reply_extract import ReplyExtractNode
from app.runtime.nodes.persist import PersistNode

def make_clinical_flow() -> Flow:
    return Flow(
        start=SafetyTriageNode(),
        chain=[
            HistoryFetchNode(),
            DeepSeekChatNode(),
            ReplyExtractNode(),
            PersistNode(),
        ],
    )

async def run_flow(shared: Dict[str, Any]) -> Dict[str, Any]:
    flow = make_clinical_flow()
    return await flow.run(shared)
