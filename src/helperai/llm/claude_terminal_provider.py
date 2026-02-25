"""Claude Terminal Provider - Uses Claude CLI in a Docker container."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, Optional
import aiohttp

from helperai.llm.message_types import Message, StreamChunk

logger = logging.getLogger(__name__)


class ClaudeTerminalProvider:
    """Provider that uses Claude CLI in a pre-configured Docker container.

    This provider connects to a Docker container running Claude CLI that has
    already been authenticated. It uses your $20/month Claude subscription
    instead of expensive API tokens, saving you $560+/month!
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8081",
        check_status: bool = True,
    ):
        self.name = "claude_terminal"
        self.model_names = ["claude-terminal"]
        self.api_url = api_url
        self.check_status = check_status
        self._session: Optional[aiohttp.ClientSession] = None
        self._is_ready = False

    async def _ensure_session(self):
        """Ensure we have an active aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30, connect=10)
            )

    async def _check_container_status(self) -> bool:
        """Check if the Claude CLI container is ready."""
        try:
            await self._ensure_session()
            async with self._session.get(f"{self.api_url}/api/status") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("claude_installed") and data.get("authenticated"):
                        logger.info("Claude CLI container is ready and authenticated")
                        return True
                    else:
                        logger.warning(f"Claude CLI container not ready: {data.get('message', 'Unknown status')}")
                        return False
                else:
                    logger.error(f"Failed to check container status: HTTP {response.status}")
                    return False
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Cannot connect to Claude CLI container at {self.api_url}: {e}")
            return False

    async def initialize(self):
        """Initialize the provider and check container status."""
        if self.check_status:
            self._is_ready = await self._check_container_status()
            if not self._is_ready:
                raise Exception(
                    f"Claude CLI container not ready at {self.api_url}. "
                    "Please ensure the container is running and Claude is authenticated."
                )
        else:
            self._is_ready = True

    async def stream(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        stream: bool = False,
        **kwargs,
    ) -> AsyncIterator[dict]:
        """Send messages to Claude CLI and stream the response."""

        if not self._is_ready:
            await self.initialize()

        await self._ensure_session()

        # Convert messages to simple text format for Claude CLI
        # Claude CLI will use its own built-in tools to read files in the container
        prompt = self._format_messages_as_text(messages, tools)

        # Send to container's API endpoint
        payload = {
            "message": prompt
        }

        try:
            async with self._session.post(
                f"{self.api_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=1200)  # Increased to 20 minutes
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Claude CLI API error (HTTP {response.status}): {error_text}")

                data = await response.json()

                if not data.get("success"):
                    raise Exception(f"Claude CLI error: {data.get('error', 'Unknown error')}")

                # Format response as expected by AshAI
                response_text = data.get("response", "")

                # Don't try to parse tool calls - Claude CLI handles its own tools internally
                # Regular text response
                if stream:
                    # Simulate streaming by yielding chunks
                    words = response_text.split()
                    for i, word in enumerate(words):
                        content = word + (" " if i < len(words) - 1 else "")
                        finish = None if i < len(words) - 1 else "stop"
                        yield StreamChunk(
                            delta_content=content,
                            finish_reason=finish
                        )
                        await asyncio.sleep(0.01)  # Small delay to simulate streaming
                else:
                    # Return complete response as a single chunk
                    yield StreamChunk(
                        delta_content=response_text,
                        finish_reason="stop"
                    )

        except asyncio.TimeoutError:
            raise Exception("Claude CLI request timed out after 1200 seconds (20 minutes)")
        except aiohttp.ClientError as e:
            logger.error(f"Error communicating with Claude CLI: {e}")
            raise

    def _parse_tool_calls(self, response: str) -> list | None:
        """Parse tool calls from Claude's response."""
        import re
        import json
        from helperai.llm.message_types import ToolCall

        # Look for tool call patterns in the response
        # Pattern: TOOL_CALL: tool_name({...}) or tool_name(...)
        pattern = r'TOOL_CALL:\s*(\w+)\(([^)]+)\)'
        matches = re.findall(pattern, response)

        if not matches:
            # Also check for natural language tool invocations
            # e.g., "I'll spawn an agent with..."
            if "spawn" in response.lower() and "agent" in response.lower():
                # Try to extract model and persona from context
                return [ToolCall(
                    id="call_" + str(hash(response))[:8],
                    name="spawn_agent",
                    arguments=json.dumps({
                        "name": "Assistant",
                        "role": "assistant",
                        "model": "claude-terminal",
                        "persona": "A helpful AI assistant"
                    })
                )]
            return None

        tool_calls = []
        for tool_name, args_str in matches:
            try:
                # Try to parse as JSON
                args = json.loads(args_str)
            except (json.JSONDecodeError, ValueError):
                # If not valid JSON, create a simple args dict
                args = {"input": args_str.strip()}

            tool_calls.append(ToolCall(
                id="call_" + str(hash(f"{tool_name}{args_str}"))[:8],
                name=tool_name,
                arguments=json.dumps(args)
            ))

        return tool_calls if tool_calls else None

    def _format_messages_as_text(self, messages: list[Message], tools: list[dict] | None = None) -> str:
        """Format messages into a text prompt for Claude CLI."""
        formatted_parts = []

        # Tell Claude CLI about the workspace and available tools
        formatted_parts.append(
            "System: You are Claude CLI in /app/workspace. Auto-approval is ON - execute immediately.\n\n"
            "CRITICAL - Inter-Agent Messaging:\n"
            "• LIST AGENTS: python3 message_agent.py --list  (always do this first to find Ash's ID)\n"
            "• REPORT TO ASH: python3 message_agent.py <ash_id> 'your report'\n"
            "• MESSAGE AGENT: python3 message_agent.py <agent_id> 'message'\n"
            "• SPAWN AGENT: python3 spawn_agent.py <name> [role] [model] [persona]\n\n"
            "Scripts are in: /app/workspace/ashai-tools/\n"
            "IMPORTANT: Always find Ash's ID by listing agents first. Ash is the coordinator - report back to Ash."
        )

        for msg in messages:
            if msg.role == "system":
                formatted_parts.append(f"System: {msg.content}")
            elif msg.role == "user":
                formatted_parts.append(f"Human: {msg.content}")
            elif msg.role == "assistant":
                formatted_parts.append(f"Assistant: {msg.content}")

            # Handle tool calls if present
            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    # tool_call is a ToolCall object, not a dict
                    formatted_parts.append(
                        f"Tool Call: {tool_call.name} "
                        f"with args {tool_call.arguments}"
                    )

            # Handle tool responses
            if msg.tool_call_id:
                formatted_parts.append(f"Tool Response: {msg.content}")

        # Join with double newlines for clarity
        prompt = "\n\n".join(formatted_parts)

        # Add final prompt indicator if last message was from user
        if messages and messages[-1].role == "user":
            prompt += "\n\nAssistant:"

        return prompt

    def _format_messages_as_text_with_bridge(self, messages: list[Message], tools: list[dict] | None = None) -> str:
        """Format messages with tool bridge instructions for Claude CLI."""
        formatted_parts = []

        # Tell Claude about the tool bridge
        if tools:
            formatted_parts.append(
                "System: You have access to AshAI tools through a bridge at http://localhost:8082. "
                "You can call tools by sending HTTP requests to the bridge API. "
                "Available tools and their usage:\n"
            )

            for tool in tools:
                if isinstance(tool, dict):
                    name = tool.get("name", "unknown")
                    desc = tool.get("description", "")
                else:
                    # Handle ToolDefinition objects
                    name = tool.name if hasattr(tool, 'name') else "unknown"
                    desc = tool.description if hasattr(tool, 'description') else ""

                formatted_parts.append(f"- {name}: {desc}")

            formatted_parts.append(
                "\nTo call a tool, use curl to POST to http://localhost:8082/api/tool/request "
                "with JSON containing tool_name and arguments. Example:\n"
                'curl -X POST http://localhost:8082/api/tool/request -H "Content-Type: application/json" '
                '-d \'{"tool_name": "spawn_agent", "arguments": {"name": "Helper", "role": "assistant"}}\''
            )

        for msg in messages:
            if msg.role == "system":
                formatted_parts.append(f"System: {msg.content}")
            elif msg.role == "user":
                formatted_parts.append(f"Human: {msg.content}")
            elif msg.role == "assistant":
                formatted_parts.append(f"Assistant: {msg.content}")

            # Handle tool calls if present
            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    formatted_parts.append(
                        f"Tool Call: {tool_call.name} "
                        f"with args {tool_call.arguments}"
                    )

            # Handle tool responses
            if msg.tool_call_id:
                formatted_parts.append(f"Tool Response: {msg.content}")

        # Join with double newlines for clarity
        prompt = "\n\n".join(formatted_parts)

        # Add final prompt indicator if last message was from user
        if messages and messages[-1].role == "user":
            prompt += "\n\nAssistant:"

        return prompt

    async def _monitor_tool_bridge(self):
        """Monitor the tool bridge for pending requests from Claude CLI."""
        bridge_url = "http://localhost:8082"

        while True:
            try:
                await asyncio.sleep(0.5)  # Check every 500ms

                # Check for pending tool requests
                async with self._session.get(
                    f"{bridge_url}/api/tool/pending",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        pending = data.get("pending", [])

                        for request in pending:
                            request_id = request.get("id")
                            tool_name = request.get("tool_name")
                            arguments = request.get("arguments")

                            # Execute tool through AshAI (this would need to be implemented)
                            # For now, just return a placeholder response
                            tool_response = f"Tool {tool_name} executed successfully"

                            # Send response back to bridge
                            await self._session.post(
                                f"{bridge_url}/api/tool/response",
                                json={"request_id": request_id, "response": tool_response},
                                timeout=aiohttp.ClientTimeout(total=30)
                            )

                            logger.info(f"Processed tool request {request_id}: {tool_name}")

            except asyncio.CancelledError:
                break
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error(f"Error monitoring tool bridge: {e}")
                await asyncio.sleep(2)  # Wait longer on error

    async def _check_for_tool_calls(self, response: str) -> list | None:
        """Check if Claude made tool calls through the bridge."""
        # Look for patterns indicating tool usage
        import re
        from helperai.llm.message_types import ToolCall

        # Check for curl commands to the bridge
        curl_pattern = r'curl.*http://localhost:8082/api/tool/request.*?({.*?})'
        matches = re.findall(curl_pattern, response, re.DOTALL)

        if matches:
            tool_calls = []
            for match in matches:
                try:
                    import json
                    data = json.loads(match)
                    tool_name = data.get("tool_name")
                    arguments = data.get("arguments", {})

                    tool_calls.append(ToolCall(
                        id=f"call_{hash(f'{tool_name}{arguments}')}",
                        name=tool_name,
                        arguments=json.dumps(arguments)
                    ))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

            return tool_calls if tool_calls else None

        return None

    async def list_models(self) -> list[dict]:
        """List available models (Claude CLI via subscription)."""
        return [
            {
                "id": "claude-terminal",
                "name": "Claude CLI (Terminal)",
                "description": "Claude via your $20/month subscription - NO API COSTS!",
                "context_window": 200000,
                "max_tokens": 4096,
                "cost_per_million": 0,  # FREE with subscription!
            }
        ]

    async def cleanup(self):
        """Clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    # Alias for backward compatibility
    send_message = stream