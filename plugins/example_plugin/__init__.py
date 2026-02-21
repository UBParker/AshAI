"""Example helperAI plugin — provides a 'current_time' tool."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from helperai.llm.message_types import ToolDefinition
from helperai.tools.protocol import ToolContext
from helperai.tools.registry import ToolRegistry


class CurrentTimeTool:
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="current_time",
            description="Get the current UTC time.",
            parameters={"type": "object", "properties": {}},
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        return datetime.now(timezone.utc).isoformat()


class ExamplePlugin:
    @property
    def name(self) -> str:
        return "example"

    @property
    def description(self) -> str:
        return "Example plugin providing a current_time tool"

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(CurrentTimeTool())


plugin = ExamplePlugin()
