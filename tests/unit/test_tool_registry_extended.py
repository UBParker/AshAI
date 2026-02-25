"""Extended tests for tool registry — covers all() and re-registration."""

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


def test_all_returns_copy():
    registry = ToolRegistry()
    t1 = DummyTool("a")
    registry.register(t1)
    all_tools = registry.all()
    assert "a" in all_tools
    # Mutating the returned dict should not affect the registry
    all_tools.pop("a")
    assert "a" in registry.all()


def test_register_overwrites():
    registry = ToolRegistry()
    t1 = DummyTool("x")
    t2 = DummyTool("x")
    registry.register(t1)
    registry.register(t2)
    assert registry.get("x") is t2


def test_get_many_raises_on_missing():
    registry = ToolRegistry()
    registry.register(DummyTool("a"))
    with pytest.raises(ToolNotFoundError):
        registry.get_many(["a", "missing"])


def test_list_tools_order():
    registry = ToolRegistry()
    for name in ["c", "a", "b"]:
        registry.register(DummyTool(name))
    assert set(registry.list_tools()) == {"a", "b", "c"}
