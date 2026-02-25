"""Tests for the ConversationalAgent class."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from helperai.agents.agent import ConversationalAgent
from helperai.core.events import EventBus
from helperai.llm.message_types import Message, StreamChunk, ToolCall, ToolDefinition
from helperai.tools.protocol import ToolContext


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

@dataclass
class FakeAgentModel:
    id: str = "agent-1"
    name: str = "TestAgent"
    role: str = "You are a test agent."
    goal: str = "Do testing."
    status: str = "idle"
    model_name: str = "test-model"
    temperature: float = 0.7
    tool_names: list = None

    def __post_init__(self):
        if self.tool_names is None:
            self.tool_names = []


class SimpleProvider:
    """Provider that returns a fixed text with no tool calls."""

    def __init__(self, text: str = "Hello!"):
        self._text = text
        self._name = "test"

    @property
    def name(self):
        return self._name

    async def stream(self, messages, model, **kwargs):
        for ch in self._text:
            yield StreamChunk(delta_content=ch)
        yield StreamChunk(finish_reason="stop")

    async def list_models(self):
        return ["test-model"]


class ToolCallingProvider:
    """Provider that returns a tool call on the first call, then text on the second."""

    def __init__(self, tool_name: str, tool_args: dict, followup_text: str = "Done."):
        self._tool_name = tool_name
        self._tool_args = tool_args
        self._followup_text = followup_text
        self._call_count = 0
        self._name = "test"

    @property
    def name(self):
        return self._name

    async def stream(self, messages, model, **kwargs):
        self._call_count += 1
        if self._call_count == 1:
            yield StreamChunk(
                tool_calls=[
                    ToolCall(id="tc-1", name=self._tool_name, arguments=json.dumps(self._tool_args))
                ]
            )
            yield StreamChunk(finish_reason="stop")
        else:
            for ch in self._followup_text:
                yield StreamChunk(delta_content=ch)
            yield StreamChunk(finish_reason="stop")

    async def list_models(self):
        return ["test-model"]


class FakeTool:
    def __init__(self, name: str, result: str = "ok"):
        self._name = name
        self._result = result

    @property
    def definition(self):
        return ToolDefinition(name=self._name, description="A test tool")

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        return self._result


def _make_agent(
    provider=None,
    tools=None,
    model=None,
) -> ConversationalAgent:
    return ConversationalAgent(
        agent_model=model or FakeAgentModel(),
        provider=provider or SimpleProvider(),
        tools=tools or {},
        event_bus=EventBus(),
        tool_context_factory=lambda aid: None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_agent_id():
    agent = _make_agent(model=FakeAgentModel(id="abc"))
    assert agent.agent_id == "abc"


def test_add_user_message_inserts_system_prompt():
    agent = _make_agent()
    agent.add_user_message("hi")
    msgs = agent.get_messages()
    assert msgs[0].role == "system"
    assert "test agent" in msgs[0].content.lower()
    assert msgs[1].role == "user"
    assert msgs[1].content == "hi"


def test_load_history():
    agent = _make_agent()
    history = [
        Message(role="system", content="sys"),
        Message(role="user", content="hello"),
        Message(role="assistant", content="world"),
    ]
    agent.load_history(history)
    assert len(agent.get_messages()) == 3


def test_update_system_prompt():
    agent = _make_agent()
    agent.add_user_message("hi")
    agent.update_system_prompt("New system prompt")
    msgs = agent.get_messages()
    assert msgs[0].content == "New system prompt\n\nYour current goal: Do testing."


def test_add_injected_message():
    agent = _make_agent()
    agent.add_injected_message("user", "injected content")
    msgs = agent.get_messages()
    assert any(m.content == "injected content" for m in msgs)


async def test_step_stream_simple_response():
    """Agent should stream content and end with done."""
    agent = _make_agent(provider=SimpleProvider("Hi"))
    agent.add_user_message("test")

    events = []
    async for event in agent.step_stream():
        events.append(event)

    content_events = [e for e in events if e["type"] == "content"]
    assert len(content_events) > 0
    full_text = "".join(e["text"] for e in content_events)
    assert full_text == "Hi"

    assert events[-1]["type"] == "done"


async def test_step_stream_with_tool_call():
    """Agent should execute a tool call and then return the followup."""
    tool = FakeTool("my_tool", result="tool_result")
    provider = ToolCallingProvider("my_tool", {"x": 1}, followup_text="After tool.")

    agent = _make_agent(
        provider=provider,
        tools={"my_tool": tool},
    )
    agent.add_user_message("use my tool")

    events = []
    async for event in agent.step_stream():
        events.append(event)

    types = [e["type"] for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "done" in types

    # Check tool result
    tool_result_event = next(e for e in events if e["type"] == "tool_result")
    assert tool_result_event["result"] == "tool_result"

    # Check final content
    content_events = [e for e in events if e["type"] == "content"]
    full_text = "".join(e["text"] for e in content_events)
    assert full_text == "After tool."


async def test_step_stream_unknown_tool():
    """Agent should handle an unknown tool call gracefully."""
    provider = ToolCallingProvider("nonexistent_tool", {}, followup_text="ok")
    agent = _make_agent(provider=provider, tools={})
    agent.add_user_message("test")

    events = []
    async for event in agent.step_stream():
        events.append(event)

    tool_result = next(e for e in events if e["type"] == "tool_result")
    result_data = json.loads(tool_result["result"])
    assert "error" in result_data
    assert "Unknown tool" in result_data["error"]


async def test_step_stream_tool_raises():
    """Agent should handle a tool that raises an exception."""

    class FailingTool:
        @property
        def definition(self):
            return ToolDefinition(name="fail_tool", description="fails")

        async def execute(self, arguments, ctx):
            raise RuntimeError("tool crashed")

    provider = ToolCallingProvider("fail_tool", {}, followup_text="recovered")
    agent = _make_agent(
        provider=provider,
        tools={"fail_tool": FailingTool()},
    )
    agent.add_user_message("test")

    events = []
    async for event in agent.step_stream():
        events.append(event)

    tool_result = next(e for e in events if e["type"] == "tool_result")
    result_data = json.loads(tool_result["result"])
    assert "error" in result_data
    assert "tool crashed" in result_data["error"]


def test_tool_definitions():
    tool = FakeTool("t1")
    agent = _make_agent(tools={"t1": tool})
    defs = agent._tool_definitions()
    assert len(defs) == 1
    assert defs[0].name == "t1"


def test_system_message_includes_goal():
    model = FakeAgentModel(role="You are a coder.", goal="Write tests.")
    agent = _make_agent(model=model)
    agent.add_user_message("hi")
    sys_msg = agent.get_messages()[0]
    assert "Write tests." in sys_msg.content
