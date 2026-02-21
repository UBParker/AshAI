"""Tool: send a message to another agent."""

from __future__ import annotations

import json
from typing import Any

from helperai.llm.message_types import ToolDefinition
from helperai.tools.protocol import ToolContext


class MessageAgentTool:
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="message_agent",
            description="Send a message to a specific sub-agent and get its response.",
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "The ID of the agent to message.",
                    },
                    "message": {
                        "type": "string",
                        "description": "The message to send to the agent.",
                    },
                },
                "required": ["agent_id", "message"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        agent_id = arguments["agent_id"]
        message = arguments["message"]

        # Collect the full response from the agent
        chunks: list[str] = []
        async for chunk in ctx.agent_manager.send_message_stream(agent_id, message):
            if chunk.get("type") == "content":
                chunks.append(chunk.get("text", ""))

        response = "".join(chunks)
        return json.dumps({"agent_id": agent_id, "response": response})
