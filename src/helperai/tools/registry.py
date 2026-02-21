"""Tool registry."""

from __future__ import annotations

from helperai.core.exceptions import ToolNotFoundError
from helperai.tools.protocol import Tool


class ToolRegistry:
    """Maps tool names to Tool instances."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.definition.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def get_many(self, names: list[str]) -> list[Tool]:
        return [self.get(n) for n in names]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def all(self) -> dict[str, Tool]:
        return dict(self._tools)
