"""Tests for builtin tools definitions and basic behavior."""

from __future__ import annotations

from helperai.tools.builtin.list_agents import ListAgentsTool
from helperai.tools.builtin.message_agent import MessageAgentTool
from helperai.tools.builtin.report_to_eve import ReportToEveTool
from helperai.tools.builtin.spawn_agent import SpawnAgentTool


def test_spawn_agent_tool_definition():
    tool = SpawnAgentTool()
    d = tool.definition
    assert d.name == "spawn_agent"
    assert "name" in d.parameters["properties"]
    assert "role" in d.parameters["properties"]
    assert "goal" in d.parameters["properties"]
    assert set(d.parameters["required"]) == {"name", "role", "goal"}


def test_list_agents_tool_definition():
    tool = ListAgentsTool()
    d = tool.definition
    assert d.name == "list_agents"
    assert d.description


def test_message_agent_tool_definition():
    tool = MessageAgentTool()
    d = tool.definition
    assert d.name == "message_agent"
    assert d.description


def test_report_to_eve_tool_definition():
    tool = ReportToEveTool()
    d = tool.definition
    assert d.name == "report_to_eve"
    assert d.description


def test_all_builtin_tools_have_definitions():
    """All builtin tools should have well-formed definitions."""
    tools = [SpawnAgentTool(), ListAgentsTool(), MessageAgentTool(), ReportToEveTool()]
    for tool in tools:
        d = tool.definition
        assert d.name, f"Tool {tool} has empty name"
        assert d.description, f"Tool {tool.definition.name} has empty description"
        assert isinstance(d.parameters, dict), f"Tool {d.name} parameters should be a dict"
