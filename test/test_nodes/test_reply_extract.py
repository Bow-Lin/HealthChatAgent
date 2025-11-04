# tests/test_nodes/test_reply_extract.py
import pytest
from app.runtime.nodes.reply_extract import ReplyExtractNode

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.mark.asyncio
async def test_extract_from_json_object_with_keys():
    node = ReplyExtractNode()
    shared = {
        "assistant_reply": '{"followups": ["测量体温", "复查血压"], "warnings": ["不是医疗诊断"]}',
        "warnings": [],
    }
    out = await node.exec(shared)
    assert out["followups"] == ["测量体温", "复查血压"]
    assert out["warnings"] == ["不是医疗诊断"]

@pytest.mark.asyncio
async def test_extract_from_list_json():
    node = ReplyExtractNode()
    shared = {
        "assistant_reply": '["多喝水", "注意休息"]',
        "warnings": [],
    }
    out = await node.exec(shared)
    assert out["followups"] == ["多喝水", "注意休息"]
    assert out["warnings"] == []

@pytest.mark.asyncio
async def test_extract_heuristic_bullets_and_inline():
    node = ReplyExtractNode()
    text = "- 监测体温\n- 减少剧烈运动\nFollow-ups: 复诊; 补充病史"
    shared = {
        "assistant_reply": text,
        "warnings": [],
    }
    out = await node.exec(shared)
    assert set(out["followups"]) == {"监测体温", "减少剧烈运动", "复诊", "补充病史"}

@pytest.mark.asyncio
async def test_merge_existing_warnings_and_dedup():
    node = ReplyExtractNode()
    shared = {
        "assistant_reply": '{"warnings": ["不是医疗建议", "不是医疗建议"]}',
        "warnings": ["仅供参考"],
    }
    out = await node.exec(shared)
    assert set(out["warnings"]) == {"仅供参考", "不是医疗建议"}

@pytest.mark.asyncio
async def test_no_followups_no_warnings():
    node = ReplyExtractNode()
    shared = {
        "assistant_reply": "请保持良好作息。",
        "warnings": [],
    }
    out = await node.exec(shared)
    assert out["followups"] == []
    assert out["warnings"] == []
