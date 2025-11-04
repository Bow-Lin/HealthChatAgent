import pytest
from pocketflow import AsyncFlow
from app.runtime.nodes.triage import SafetyTriageNode
from pocketflow import AsyncNode

@pytest.mark.asyncio
async def test_triage_routes_ok_logic():
    shared = {"user_text": "mild back pain", "warnings": []}
    triage = SafetyTriageNode()
    flow = AsyncFlow(start=triage)
    triage.successors = {}  # end here for unit test
    action = await flow.run_async(shared)
    assert action == "ok"
    assert shared["triage_level"] == "non-urgent"



class DummyNext(AsyncNode):
    async def prep_async(self, shared): return shared
    async def exec_async(self, prep): return {"done": True}
    async def post_async(self, shared, prep, exec_res): 
        shared["after_dummy"] = True
        return "end"
    
@pytest.mark.asyncio
async def test_triage_routes_ok_path():
    shared = {"user_text": "mild back pain", "warnings": []}
    triage = SafetyTriageNode()
    next_node = DummyNext()
    flow = AsyncFlow(start=triage)

    triage.successors = {"ok": next_node}  
    next_node.successors = {}              

    action = await flow.run_async(shared)

    assert action == "end"
    assert shared["triage_level"] == "non-urgent"
    assert shared.get("after_dummy") is True