"""Claude Session Provider - Uses browser cookies for authentication."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import AsyncIterator

import aiohttp
from yarl import URL

from helperai.llm.message_types import Message, StreamChunk, ToolDefinition

logger = logging.getLogger(__name__)


class ClaudeSessionProvider:
    """Provider that uses Claude.ai session cookies.

    This provider uses your $20/month Claude subscription through
    browser session cookies - no API keys needed!
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8080",
        cookies_file: str = "claude-cookies.json"
    ):
        self.name = "claude_session"
        self.api_url = api_url
        self.cookies_file = Path(cookies_file)
        self.conversation_id = None
        self.session = None
        self._check_service()

    def _check_service(self):
        """Check if the cookie-based API service is running."""
        try:
            import requests
            response = requests.get(f"{self.api_url}/api/status", timeout=2)
            if response.status_code == 200:
                status = response.json()
                if status.get('cookies_loaded'):
                    logger.info(f"Claude Session API ready: {status.get('cookie_count')} cookies loaded")
                else:
                    logger.warning("Claude Session API running but no cookies loaded")
            else:
                logger.warning(f"Claude Session API not responding properly: {response.status_code}")
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"Claude Session API not available at {self.api_url}: {e}")
            logger.info("Start it with: docker run -p 8080:8080 claude-session")

    async def stream(
        self,
        messages: list[Message],
        model: str,
        *,
        temperature: float = 0.7,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion using Claude session cookies."""

        # Convert messages to a single prompt for Claude
        prompt = self._format_messages(messages)

        # Send to our cookie-based API
        async with aiohttp.ClientSession() as session:
            payload = {
                "message": prompt,
                "conversation_id": self.conversation_id
            }

            try:
                async with session.post(
                    f"{self.api_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    if response.status == 200:
                        result = await response.json()

                        if result.get("success"):
                            # Update conversation ID for follow-ups
                            self.conversation_id = result.get("conversation_id")

                            # Stream the response
                            content = result.get("response", "")

                            # First chunk
                            yield StreamChunk(
                                id=f"msg_{os.urandom(8).hex()}",
                                object="chat.completion.chunk",
                                created=0,
                                model="claude-3-5-sonnet",
                                choices=[{
                                    "index": 0,
                                    "delta": {"role": "assistant", "content": content},
                                    "finish_reason": None
                                }]
                            )

                            # Final chunk
                            yield StreamChunk(
                                id=f"msg_{os.urandom(8).hex()}",
                                object="chat.completion.chunk",
                                created=0,
                                model="claude-3-5-sonnet",
                                choices=[{
                                    "index": 0,
                                    "delta": {},
                                    "finish_reason": "stop"
                                }]
                            )
                        else:
                            error_msg = result.get("error", "Unknown error")
                            logger.error(f"Claude Session API error: {error_msg}")
                            yield StreamChunk(
                                id=f"msg_{os.urandom(8).hex()}",
                                object="chat.completion.chunk",
                                created=0,
                                model="claude-3-5-sonnet",
                                choices=[{
                                    "index": 0,
                                    "delta": {"role": "assistant", "content": f"Error: {error_msg}"},
                                    "finish_reason": "stop"
                                }]
                            )
                    else:
                        error_text = await response.text()
                        logger.error(f"API request failed: {response.status} - {error_text}")
                        yield StreamChunk(
                            id=f"msg_{os.urandom(8).hex()}",
                            object="chat.completion.chunk",
                            created=0,
                            model="claude-3-5-sonnet",
                            choices=[{
                                "index": 0,
                                "delta": {"role": "assistant", "content": f"API Error: {response.status}"},
                                "finish_reason": "stop"
                            }]
                        )

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error(f"Failed to connect to Claude Session API: {e}")
                yield StreamChunk(
                    id=f"msg_{os.urandom(8).hex()}",
                    object="chat.completion.chunk",
                    created=0,
                    model="claude-3-5-sonnet",
                    choices=[{
                        "index": 0,
                        "delta": {"role": "assistant", "content": f"Connection error: {str(e)}"},
                        "finish_reason": "stop"
                    }]
                )

    async def list_models(self) -> list[str]:
        """Return available model names."""
        return ["claude-3-5-sonnet-20241022"]

    def _format_messages(self, messages: list[Message]) -> str:
        """Format messages into a single prompt for Claude."""
        formatted_parts = []

        for msg in messages:
            role = msg.role
            content = msg.content or ""

            if role == "system":
                formatted_parts.append(f"System: {content}")
            elif role == "user":
                formatted_parts.append(f"Human: {content}")
            elif role == "assistant":
                formatted_parts.append(f"Assistant: {content}")

        return "\n\n".join(formatted_parts)