"""Tests for ConversationalAgent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from helperai.agents.agent import ConversationalAgent, MAX_TOOL_ROUNDS
from helperai.core.events import EventBus
from helperai.llm.message_types import Message, StreamChunk, ToolCall, ToolDefinition
from helperai.tools.protocol import ToolContext


# -- helpers ------------------------------------------------------------------


def _make_agent_model(**overrides):
    """Create a minimal mock agent model."""
    model = MagicMock()
    model.id = overrides.get("id", "test-agent-1")
    model.name = overrides.get("name", "TestAgent")
    model.role = overrides.get("role", "You are a test agent.")
    model.goal = overrides.get("goal", "")
    model.model_name = overrides.get("model_name", "test-model")
    model.temperature = overrides.get("temperature", 0.7)
    return model


class FakeTool:
    def __init__(self, name: str = "fake_tool", result: str = "ok", requires_approval: bool = False):
        self._name = name
        self._result = result
        self.requires_approval = requires_approval
        self.called_with: list[dict] = []

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(name=self._name, description="A fake tool")

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        self.called_with.append(arguments)
        return self._result


class ErrorTool:
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(name="error_tool", description="Always fails")

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        raise RuntimeError("tool exploded")


def _make_ctx_factory():
    """Create a tool context factory that returns a mock context."""
    def factory(agent_id):
        ctx = MagicMock(spec=ToolContext)
        ctx.agent_id = agent_id
        ctx.approval_manager = None
        return ctx
    return factory


async def _fake_stream_simple(messages, model, **kwargs):
    """Simulate a simple LLM response with no tool calls."""
    yield StreamChunk(delta_content="Hello ")
    yield StreamChunk(delta_content="world!")
    yield StreamChunk(finish_reason="stop")


async def _fake_stream_with_tool_call(messages, model, **kwargs):
    """Simulate LLM response that calls a tool."""
    yield StreamChunk(
        delta_content="Let me use a tool.",
        tool_calls=[ToolCall(id="tc1", name="fake_tool", arguments='{"x": 1}')],
    )
    yield StreamChunk(finish_reason="tool_calls")


async def _fake_stream_done_after_tool(messages, model, **kwargs):
    """Simulate LLM final response after tool result."""
    yield StreamChunk(delta_content="Done with tool.")
    yield StreamChunk(finish_reason="stop")


# -- tests --------------------------------------------------------------------


def test_agent_id_from_model():
    model = _make_agent_model(id="abc123")
    agent = ConversationalAgent(model, MagicMock(), {}, EventBus(), _make_ctx_factory())
    assert agent.agent_id == "abc123"


def test_load_history():
    model = _make_agent_model()
    agent = ConversationalAgent(model, MagicMock(), {}, EventBus(), _make_ctx_factory())

    msgs = [Message(role="system", content="sys"), Message(role="user", content="hi")]
    agent.load_history(msgs)
    assert len(agent.get_messages()) == 2
    assert agent._initialized is True


def test_add_user_message_inserts_system():
    model = _make_agent_model(role="You are X.", goal="Do Y.")
    agent = ConversationalAgent(model, MagicMock(), {}, EventBus(), _make_ctx_factory())

    agent.add_user_message("hello")
    messages = agent.get_messages()
    assert messages[0].role == "system"
    assert "You are X." in messages[0].content
    assert "Do Y." in messages[0].content
    assert messages[1].role == "user"
    assert messages[1].content == "hello"


def test_add_user_message_uses_name_fallback():
    model = _make_agent_model(role="", goal="")
    agent = ConversationalAgent(model, MagicMock(), {}, EventBus(), _make_ctx_factory())

    agent.add_user_message("hello")
    messages = agent.get_messages()
    assert "TestAgent" in messages[0].content


def test_ensure_system_message_not_duplicated():
    model = _make_agent_model()
    agent = ConversationalAgent(model, MagicMock(), {}, EventBus(), _make_ctx_factory())

    agent.add_user_message("first")
    agent.add_user_message("second")
    messages = agent.get_messages()
    system_msgs = [m for m in messages if m.role == "system"]
    assert len(system_msgs) == 1


def test_add_injected_message():
    model = _make_agent_model()
    agent = ConversationalAgent(model, MagicMock(), {}, EventBus(), _make_ctx_factory())

    agent.add_injected_message("user", "[Report]: done")
    messages = agent.get_messages()
    assert messages[-1].role == "user"
    assert messages[-1].content == "[Report]: done"


def test_update_system_prompt():
    model = _make_agent_model(goal="My goal")
    agent = ConversationalAgent(model, MagicMock(), {}, EventBus(), _make_ctx_factory())

    agent.add_user_message("hi")
    agent.update_system_prompt("New system prompt")
    messages = agent.get_messages()
    assert "New system prompt" in messages[0].content
    assert "My goal" in messages[0].content


def test_tool_definitions():
    tool = FakeTool("alpha")
    model = _make_agent_model()
    agent = ConversationalAgent(model, MagicMock(), {"alpha": tool}, EventBus(), _make_ctx_factory())
    defs = agent._tool_definitions()
    assert len(defs) == 1
    assert defs[0].name == "alpha"


async def test_step_stream_simple_response():
    """Agent streams content and emits done when no tool calls."""
    provider = MagicMock()
    provider.stream = _fake_stream_simple

    model = _make_agent_model()
    agent = ConversationalAgent(model, provider, {}, EventBus(), _make_ctx_factory())
    agent.add_user_message("say hi")

    events = []
    async for event in agent.step_stream():
        events.append(event)

    content_events = [e for e in events if e["type"] == "content"]
    assert len(content_events) == 2
    assert events[-1]["type"] == "done"

    # Assistant message should be appended
    messages = agent.get_messages()
    assert messages[-1].role == "assistant"
    assert "Hello world!" in messages[-1].content


async def test_step_stream_with_tool_execution():
    """Agent calls a tool and then gets final response."""
    call_count = 0

    async def provider_stream(messages, model, **kwargs):
        nonlocal call_count
        if call_count == 0:
            call_count += 1
            yield StreamChunk(
                delta_content="Using tool.",
                tool_calls=[ToolCall(id="tc1", name="fake_tool", arguments='{"x": 1}')],
            )
            yield StreamChunk(finish_reason="tool_calls")
        else:
            yield StreamChunk(delta_content="Tool result processed.")
            yield StreamChunk(finish_reason="stop")

    provider = MagicMock()
    provider.stream = provider_stream

    tool = FakeTool("fake_tool", result='{"status": "ok"}')
    model = _make_agent_model()
    agent = ConversationalAgent(
        model, provider, {"fake_tool": tool}, EventBus(), _make_ctx_factory()
    )
    agent.add_user_message("use tool")

    events = []
    async for event in agent.step_stream():
        events.append(event)

    types = [e["type"] for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "done" in types

    # Tool was called with correct args
    assert len(tool.called_with) == 1
    assert tool.called_with[0] == {"x": 1}


async def test_step_stream_unknown_tool():
    """Unknown tool calls produce error results."""
    async def provider_stream(messages, model, **kwargs):
        yield StreamChunk(
            delta_content="",
            tool_calls=[ToolCall(id="tc1", name="nonexistent", arguments="{}")],
        )
        yield StreamChunk(finish_reason="tool_calls")

    provider = MagicMock()
    provider.stream = provider_stream

    model = _make_agent_model()
    agent = ConversationalAgent(model, provider, {}, EventBus(), _make_ctx_factory())
    agent.add_user_message("call missing tool")

    events = []
    # The agent will loop, so we need to handle the second iteration
    # After unknown tool result, LLM will be called again - make it return simple response
    call_count = 0
    orig_stream = provider.stream

    async def multi_stream(messages, model, **kwargs):
        nonlocal call_count
        if call_count == 0:
            call_count += 1
            async for chunk in orig_stream(messages, model, **kwargs):
                yield chunk
        else:
            yield StreamChunk(delta_content="ok")
            yield StreamChunk(finish_reason="stop")

    provider.stream = multi_stream

    async for event in agent.step_stream():
        events.append(event)

    tool_results = [e for e in events if e["type"] == "tool_result"]
    assert len(tool_results) == 1
    result_data = json.loads(tool_results[0]["result"])
    assert "error" in result_data
    assert "Unknown tool" in result_data["error"]


async def test_step_stream_tool_exception():
    """Tool execution errors are caught and returned as error results."""
    call_count = 0

    async def provider_stream(messages, model, **kwargs):
        nonlocal call_count
        if call_count == 0:
            call_count += 1
            yield StreamChunk(
                delta_content="",
                tool_calls=[ToolCall(id="tc1", name="error_tool", arguments="{}")],
            )
            yield StreamChunk(finish_reason="tool_calls")
        else:
            yield StreamChunk(delta_content="handled")
            yield StreamChunk(finish_reason="stop")

    provider = MagicMock()
    provider.stream = provider_stream

    model = _make_agent_model()
    agent = ConversationalAgent(
        model, provider, {"error_tool": ErrorTool()}, EventBus(), _make_ctx_factory()
    )
    agent.add_user_message("use error tool")

    events = []
    async for event in agent.step_stream():
        events.append(event)

    tool_results = [e for e in events if e["type"] == "tool_result"]
    assert len(tool_results) == 1
    result_data = json.loads(tool_results[0]["result"])
    assert "error" in result_data
    assert "tool exploded" in result_data["error"]


def test_get_messages_returns_copy():
    model = _make_agent_model()
    agent = ConversationalAgent(model, MagicMock(), {}, EventBus(), _make_ctx_factory())
    agent.add_user_message("hi")

    msgs1 = agent.get_messages()
    msgs2 = agent.get_messages()
    assert msgs1 is not msgs2
    assert len(msgs1) == len(msgs2)


def test_max_tool_rounds_constant():
    assert MAX_TOOL_ROUNDS == 35
