"""Tests for tool registry."""

import pytest

from helperai.core.exceptions import ToolNotFoundError
from helperai.llm.message_types import ToolDefinition
from helperai.tools.registry import ToolRegistry


class DummyTool:
    def __init__(self, name="dummy"):
        self._name = name

    @property
    def definition(self):
        return ToolDefinition(name=self._name, description="A dummy tool")

    async def execute(self, arguments, ctx):
        return "ok"


def test_register_and_get():
    registry = ToolRegistry()
    tool = DummyTool("test_tool")
    registry.register(tool)
    assert registry.get("test_tool") is tool


def test_get_not_found():
    registry = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        registry.get("nonexistent")


def test_list_tools():
    registry = ToolRegistry()
    registry.register(DummyTool("a"))
    registry.register(DummyTool("b"))
    assert sorted(registry.list_tools()) == ["a", "b"]


def test_get_many():
    registry = ToolRegistry()
    t1 = DummyTool("x")
    t2 = DummyTool("y")
    registry.register(t1)
    registry.register(t2)
    result = registry.get_many(["x", "y"])
    assert result == [t1, t2]
