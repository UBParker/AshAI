"""Tool: spawn a new sub-agent."""

from __future__ import annotations

import json
from typing import Any

from helperai.llm.message_types import ToolDefinition
from helperai.tools.protocol import ToolContext


class SpawnAgentTool:
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="spawn_agent",
            description=(
                "Create and start a new sub-agent with a specific role and goal. "
                "The agent will run autonomously in the background. "
                "If initial_message is provided, the agent will immediately start working on it."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "A short descriptive name for the agent.",
                    },
                    "role": {
                        "type": "string",
                        "description": "System prompt defining the agent's persona and capabilities.",
                    },
                    "goal": {
                        "type": "string",
                        "description": "The specific goal or task for this agent to accomplish.",
                    },
                    "tool_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tools to give the agent (e.g. ['claude_code', 'run_command']). Always includes report_to_eve.",
                    },
                    "initial_message": {
                        "type": "string",
                        "description": "Optional first message to send the agent, starting it on its task immediately.",
                    },
                    "model": {
                        "type": "string",
                        "description": "Optional model name override. Leave empty for default.",
                    },
                    "provider": {
                        "type": "string",
                        "description": "Optional provider name override. Leave empty for default.",
                    },
                },
                "required": ["name", "role", "goal"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        # Build tool list — always include report_to_eve
        tool_names = list(arguments.get("tool_names") or [])
        if "report_to_eve" not in tool_names:
            tool_names.append("report_to_eve")

        agent = await ctx.agent_manager.create_agent(
            name=arguments["name"],
            role=arguments["role"],
            goal=arguments["goal"],
            parent_id=ctx.agent_id,
            model_name=arguments.get("model", ""),
            provider_name=arguments.get("provider", ""),
            tool_names=tool_names,
        )
        await ctx.agent_manager.start_agent(agent.id)

        # If initial_message provided, kick off the agent in the background
        initial_message = arguments.get("initial_message")
        if initial_message:
            import asyncio

            async def _run_agent():
                async for _ in ctx.agent_manager.send_message_stream(
                    agent.id, initial_message
                ):
                    pass  # consume the stream in the background

            asyncio.create_task(_run_agent())

        return json.dumps({
            "agent_id": agent.id,
            "name": agent.name,
            "status": agent.status,
            "started": bool(initial_message),
        })
