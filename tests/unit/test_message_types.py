"""Tests for LLM message types."""

from helperai.llm.message_types import Message, ToolCall, ToolDefinition


def test_message_to_openai_dict():
    msg = Message(role="user", content="hello")
    d = msg.to_openai_dict()
    assert d == {"role": "user", "content": "hello"}


def test_message_with_tool_calls():
    msg = Message(
        role="assistant",
        content="",
        tool_calls=[ToolCall(id="tc1", name="test", arguments='{"a": 1}')],
    )
    d = msg.to_openai_dict()
    assert len(d["tool_calls"]) == 1
    assert d["tool_calls"][0]["function"]["name"] == "test"


def test_tool_message():
    msg = Message(role="tool", content="result", tool_call_id="tc1")
    d = msg.to_openai_dict()
    assert d["tool_call_id"] == "tc1"


def test_tool_definition_to_openai():
    td = ToolDefinition(
        name="my_tool",
        description="Does stuff",
        parameters={"type": "object", "properties": {"x": {"type": "string"}}},
    )
    d = td.to_openai_dict()
    assert d["type"] == "function"
    assert d["function"]["name"] == "my_tool"
    assert d["function"]["parameters"]["properties"]["x"]["type"] == "string"
