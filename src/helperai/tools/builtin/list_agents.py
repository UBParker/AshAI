"""Tool: list active agents."""

from __future__ import annotations

import json
from typing import Any

from helperai.llm.message_types import ToolDefinition
from helperai.tools.protocol import ToolContext


class ListAgentsTool:
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_agents",
            description="List all currently active sub-agents with their status and goals.",
            parameters={"type": "object", "properties": {}},
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        agents = await ctx.agent_manager.list_agents()
        result = []
        for a in agents:
            if a.id == ctx.agent_id:
                continue  # don't list self
            result.append(
                {
                    "id": a.id,
                    "name": a.name,
                    "status": a.status,
                    "goal": a.goal,
                    "parent_id": a.parent_id,
                }
            )
        return json.dumps(result)
