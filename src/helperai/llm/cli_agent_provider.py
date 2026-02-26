"""CLI Agent Provider — generic provider that wraps any CLI backend.

Talks to the cli-terminal-controller API (port 8081) which dispatches to
the right CLI binary (claude, gemini, …) based on the requested model name.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Optional

import aiohttp

from helperai.llm.message_types import Message, StreamChunk

logger = logging.getLogger(__name__)


class CLIAgentProvider:
    """Provider that routes requests to CLI backends via the controller API."""

    def __init__(
        self,
        api_url: str = "http://localhost:8081",
        check_status: bool = True,
    ):
        self.name = "cli_agent"
        self.model_names: list[str] = []  # populated by _sync_models
        self.api_url = api_url
        self.check_status = check_status
        self._session: Optional[aiohttp.ClientSession] = None
        self._is_ready = False

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30, connect=10)
            )

    # ------------------------------------------------------------------
    # Initialisation & status
    # ------------------------------------------------------------------

    async def _check_controller_status(self) -> bool:
        try:
            await self._ensure_session()
            async with self._session.get(f"{self.api_url}/api/status") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("ready"):
                        clis = data.get("installed_clis", [])
                        logger.info("CLI Agent controller ready — installed CLIs: %s", clis)
                        return True
                    logger.warning("CLI Agent controller not ready: %s", data)
                    return False
                logger.error("Controller status HTTP %d", resp.status)
                return False
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error("Cannot reach CLI Agent controller at %s: %s", self.api_url, e)
            return False

    async def initialize(self):
        if self.check_status:
            self._is_ready = await self._check_controller_status()
            if not self._is_ready:
                raise Exception(
                    f"CLI Agent controller not ready at {self.api_url}. "
                    "Ensure the container is running."
                )
        else:
            self._is_ready = True
        # Populate model list from controller
        await self._sync_models()

    async def _sync_models(self):
        """Fetch available models from the controller."""
        try:
            await self._ensure_session()
            async with self._session.get(f"{self.api_url}/api/models") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.model_names = [m["id"] for m in data]
                    logger.info("CLI Agent models: %s", self.model_names)
        except Exception as e:
            logger.warning("Could not fetch models from controller: %s", e)

    # ------------------------------------------------------------------
    # Streaming chat
    # ------------------------------------------------------------------

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
        if not self._is_ready:
            await self.initialize()

        await self._ensure_session()

        prompt = self._format_messages_as_text(messages, tools)

        # Use first available model as fallback
        if not model and self.model_names:
            model = self.model_names[0]

        payload = {"model": model, "message": prompt}

        try:
            async with self._session.post(
                f"{self.api_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=1200),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"CLI Agent API error (HTTP {response.status}): {error_text}"
                    )

                data = await response.json()

                if not data.get("success"):
                    raise Exception(
                        f"CLI Agent error: {data.get('error', 'Unknown error')}"
                    )

                response_text = data.get("response", "")

                if stream:
                    words = response_text.split()
                    for i, word in enumerate(words):
                        content = word + (" " if i < len(words) - 1 else "")
                        finish = None if i < len(words) - 1 else "stop"
                        yield StreamChunk(
                            delta_content=content,
                            finish_reason=finish,
                        )
                        await asyncio.sleep(0.01)
                else:
                    yield StreamChunk(
                        delta_content=response_text,
                        finish_reason="stop",
                    )

        except asyncio.TimeoutError:
            raise Exception("CLI Agent request timed out after 1200 s")
        except aiohttp.ClientError as e:
            logger.error("Error communicating with CLI Agent controller: %s", e)
            raise

    # ------------------------------------------------------------------
    # Message formatting (reused from the old provider)
    # ------------------------------------------------------------------

    def _format_messages_as_text(
        self, messages: list[Message], tools: list[dict] | None = None
    ) -> str:
        formatted_parts = []

        formatted_parts.append(
            "System: You are an AI agent in /app/workspace. Auto-approval is ON — execute immediately.\n\n"
            "CRITICAL — Inter-Agent Messaging:\n"
            "• REPORT TO ASH: python3 /app/workspace/ashai-tools/report_to_eve.py 'your report' --sender YourName\n"
            "• MESSAGE AGENT: python3 /app/workspace/ashai-tools/message_agent.py <agent_id> 'message'\n"
            "• LIST AGENTS: python3 /app/workspace/ashai-tools/message_agent.py --list\n"
            "• SPAWN AGENT: python3 /app/workspace/ashai-tools/spawn_agent.py <name> [--role <role>]\n\n"
            "IMPORTANT: When you finish your task, ALWAYS report results back to Ash using report_to_eve.py."
        )

        for msg in messages:
            if msg.role == "system":
                formatted_parts.append(f"System: {msg.content}")
            elif msg.role == "user":
                formatted_parts.append(f"Human: {msg.content}")
            elif msg.role == "assistant":
                formatted_parts.append(f"Assistant: {msg.content}")

            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    formatted_parts.append(
                        f"Tool Call: {tool_call.name} with args {tool_call.arguments}"
                    )

            if msg.tool_call_id:
                formatted_parts.append(f"Tool Response: {msg.content}")

        prompt = "\n\n".join(formatted_parts)

        if messages and messages[-1].role == "user":
            prompt += "\n\nAssistant:"

        return prompt

    # ------------------------------------------------------------------
    # Model listing
    # ------------------------------------------------------------------

    async def list_models(self) -> list[dict]:
        """Fetch available models from the controller."""
        try:
            await self._ensure_session()
            async with self._session.get(f"{self.api_url}/api/models") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return [
                        {
                            "id": m["id"],
                            "name": f"{m['id']} ({m['cli']} CLI)",
                            "description": f"Runs via {m['cli']} CLI",
                            "context_window": 200000,
                            "max_tokens": 4096,
                        }
                        for m in data
                    ]
        except Exception as e:
            logger.warning("Could not list models from controller: %s", e)

        return []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def cleanup(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    # Backward compatibility alias
    send_message = stream
