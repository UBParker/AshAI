"""Tool: report back to Ash (the master agent)."""

from __future__ import annotations

import json
from typing import Any

from helperai.llm.message_types import ToolDefinition
from helperai.tools.protocol import ToolContext


class ReportToEveTool:
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="report_to_eve",
            description=(
                "Report your progress or results back to Ash, the master agent. "
                "Use this when you have completed a task, need help, or want to share findings."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "report": {
                        "type": "string",
                        "description": "The report content to send to Ash.",
                    },
                },
                "required": ["report"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        report = arguments["report"]
        eve_id = ctx.agent_manager.eve_id
        if eve_id is None:
            return json.dumps({"error": "Ash is not running"})

        # Get reporting agent's name
        agent = await ctx.agent_manager.get_agent(ctx.agent_id)
        agent_name = agent.name if agent else "Unknown"

        # Inject report as a user message into Ash's thread
        report_message = f"[Report from sub-agent '{agent_name}' ({ctx.agent_id})]: {report}"
        await ctx.agent_manager.inject_message(eve_id, "user", report_message)

        return json.dumps({"status": "reported", "to": "eve"})
