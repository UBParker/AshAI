"""Claude Host Provider - Uses the host's Claude CLI directly."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import tempfile
import os
from typing import AsyncIterator

from helperai.core.exceptions import LLMError
from helperai.llm.message_types import Message

logger = logging.getLogger(__name__)


class ClaudeHostProvider:
    """Provider that uses the host's Claude CLI directly.

    This provider uses your Claude subscription through the CLI installed on your host.
    No Docker containers needed - just your $20/month Claude subscription!
    """

    def __init__(self):
        self.name = "claude_host"
        self.model_names = ["claude-cli"]
        self._check_claude_cli()

    def _check_claude_cli(self):
        """Check if Claude CLI is installed and authenticated."""
        try:
            import subprocess
            result = subprocess.run(['claude', 'auth', 'status'],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("Claude CLI not authenticated. Run: claude auth login")
            else:
                auth_data = json.loads(result.stdout)
                if auth_data.get('loggedIn'):
                    logger.info(f"Claude CLI authenticated as {auth_data.get('email')}")
                else:
                    logger.warning("Claude CLI not authenticated. Run: claude auth login")
        except FileNotFoundError:
            logger.error("Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code")
        except (json.JSONDecodeError, subprocess.SubprocessError, OSError) as e:
            logger.error(f"Error checking Claude CLI: {e}")

    async def stream(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[dict]:
        """Send messages to Claude CLI."""

        # Get the last user message for Claude CLI
        last_message = ""
        for msg in reversed(messages):
            if msg.role == "user":
                last_message = msg.content or ""
                break

        if not last_message:
            last_message = "Please respond."

        # Create temp file with message
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(last_message)
            temp_file = f.name

        try:
            # Call Claude CLI
            process = await asyncio.create_subprocess_exec(
                'claude', 'chat', '--file', temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=300
                )
            except asyncio.TimeoutError:
                process.kill()
                raise LLMError("Claude CLI request timed out after 300 seconds")

            if process.returncode == 0:
                response_text = stdout.decode('utf-8').strip()
            else:
                logger.error(f"Claude CLI error: {stderr.decode('utf-8')}")
                response_text = "Error: Failed to get response from Claude CLI"

            # Return response in streaming format
            if stream:
                # Send content in streaming format
                yield {
                    "id": f"msg_{os.urandom(8).hex()}",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": "claude-cli",
                    "choices": [{
                        "index": 0,
                        "delta": {"content": response_text},
                        "finish_reason": None
                    }]
                }
                # Send finish chunk
                yield {
                    "id": f"msg_{os.urandom(8).hex()}",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": "claude-cli",
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
            else:
                # Non-streaming format
                yield {
                    "id": f"msg_{os.urandom(8).hex()}",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "claude-cli",
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": response_text
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": len(last_message.split()),
                        "completion_tokens": len(response_text.split()),
                        "total_tokens": len(last_message.split()) + len(response_text.split())
                    }
                }

        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file)
            except OSError:
                pass

    async def list_models(self) -> list[dict]:
        """List available models."""
        return [
            {
                "id": "claude-cli",
                "name": "Claude CLI (Host)",
                "description": "Claude via your subscription on host - NO API COSTS!",
                "context_window": 200000,
                "max_tokens": 4096,
                "cost_per_million": 0,  # FREE with subscription!
            }
        ]

    async def cleanup_agent(self, agent_id: str):
        """No cleanup needed for host CLI."""
        pass

    async def cleanup_all(self):
        """No cleanup needed for host CLI."""
        pass