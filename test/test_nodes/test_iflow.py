"""
Tests for iFlow Chat Node
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.runtime.nodes.iflow import IFlowChatNode


@pytest.mark.asyncio
async def test_iflow_chat_node_prep_async():
    """Test the prep_async method of IFlowChatNode"""
    # Create a mock shared dictionary
    shared = {
        "repo": AsyncMock(),
        "tenant_id": "test_tenant",
        "encounter_id": "test_encounter",
        "user_text": "Hello, I have a question about my health.",
        "prior_summaries": ["Previous visit: General checkup", "Previous visit: Blood test"]
    }
    
    # Mock the repo.get_messages method
    mock_message = MagicMock()
    mock_message.role = "user"
    mock_message.content_json = "Previous message"
    shared["repo"].get_messages.return_value = [mock_message]
    
    node = IFlowChatNode()
    result = await node.prep_async(shared)
    
    # Check that the result is a dictionary with the expected keys
    assert "messages" in result
    assert "client" in result
    assert "temperature" in result
    
    # Check that the messages list was constructed correctly
    messages = result["messages"]
    assert len(messages) >= 4  # system prompt + prior summaries + history + user query
    
    # Check that the first message is the system prompt
    assert messages[0]["role"] == "system"
    assert "你是一位经验丰富的中医推拿专家，擅长运用中医理论进行辨证指导与推拿调理。" in messages[0]["content"]
    
    # Check that prior summaries are included
    prior_summary_msg = next((m for m in messages if "Prior visit summaries" in m["content"]), None)
    assert prior_summary_msg is not None
    
    # Check that the user query is the last message
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "Hello, I have a question about my health."


@pytest.mark.asyncio
async def test_iflow_chat_node_prep_async_no_prior_summaries():
    """Test prep_async when no prior summaries are provided"""
    shared = {
        "repo": AsyncMock(),
        "tenant_id": "test_tenant",
        "encounter_id": "test_encounter",
        "user_text": "Hello",
    }
    
    # Mock the repo.get_messages method
    mock_message = MagicMock()
    mock_message.role = "user"
    mock_message.content_json = "Previous message"
    shared["repo"].get_messages.return_value = [mock_message]
    
    node = IFlowChatNode()
    result = await node.prep_async(shared)
    
    # Check that messages were constructed without prior summaries
    messages = result["messages"]
    # Should have system prompt + history + user query (3 messages minimum)
    assert len(messages) >= 3
    
    # Ensure no prior summaries section exists
    prior_summary_msg = next((m for m in messages if "Prior visit summaries" in m["content"]), None)
    assert prior_summary_msg is None


@pytest.mark.asyncio
async def test_iflow_chat_node_exec_async():
    """Test the exec_async method of IFlowChatNode"""
    # Create mock prep result
    prep_result = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"}
        ],
        "client": AsyncMock(),
        "temperature": 0.2
    }
    
    # Mock the client's achat_completion method
    prep_result["client"].achat_completion.return_value = "I'm doing well, thank you for asking!"
    
    node = IFlowChatNode()
    result = await node.exec_async(prep_result)
    
    # Verify the result
    assert "reply" in result
    assert result["reply"] == "I'm doing well, thank you for asking!"
    
    # Verify the client method was called with correct parameters
    prep_result["client"].achat_completion.assert_called_once_with(
        messages=prep_result["messages"],
        temperature=prep_result["temperature"],
        model = "qwen3-max",
        stream = True
    )


@pytest.mark.asyncio
async def test_iflow_chat_node_exec_fallback_async():
    """Test the exec_fallback_async method of IFlowChatNode"""
    prep_result = {
        "messages": [{"role": "user", "content": "test"}],
        "client": MagicMock(),
        "temperature": 0.2
    }
    
    exception = Exception("Test error")
    
    node = IFlowChatNode()
    result = await node.exec_fallback_async(prep_result, exception)
    
    # Verify fallback result structure
    assert "reply" in result
    assert "error" in result
    assert "degraded" in result
    
    # Verify error message is included
    assert "Test error" in result["error"]
    
    # Verify degraded flag is set
    assert result["degraded"] is True


@pytest.mark.asyncio
async def test_iflow_chat_node_post_async():
    """Test the post_async method of IFlowChatNode"""
    shared = {"to_persist": []}
    prep = {}
    exec_res = {"reply": "This is the assistant's reply."}
    
    node = IFlowChatNode()
    result = await node.post_async(shared, prep, exec_res)
    
    # Verify the return value
    assert result == "ok"
    
    # Verify shared state was updated
    assert shared["assistant_reply"] == "This is the assistant's reply."
    assert len(shared["to_persist"]) == 1
    assert shared["to_persist"][0]["role"] == "assistant"
    assert shared["to_persist"][0]["content"] == "This is the assistant's reply."


@pytest.mark.asyncio
async def test_iflow_chat_node_post_async_existing_to_persist():
    """Test post_async when to_persist already has items"""
    shared = {"to_persist": [{"role": "user", "content": "Previous message"}]}
    prep = {}
    exec_res = {"reply": "New assistant reply"}
    
    node = IFlowChatNode()
    result = await node.post_async(shared, prep, exec_res)
    
    # Verify the return value
    assert result == "ok"
    
    # Verify shared state was updated correctly
    assert shared["assistant_reply"] == "New assistant reply"
    assert len(shared["to_persist"]) == 2
    assert shared["to_persist"][0]["role"] == "user"
    assert shared["to_persist"][1]["role"] == "assistant"
    assert shared["to_persist"][1]["content"] == "New assistant reply"
