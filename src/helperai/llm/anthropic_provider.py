"""Native Anthropic SDK provider using anthropic.AsyncAnthropic."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import anthropic

from helperai.core.exceptions import LLMError
from helperai.llm.message_types import Message, StreamChunk, ToolCall, ToolDefinition

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """Native Anthropic provider using the official SDK with streaming."""

    def __init__(self, api_key: str) -> None:
        self._name = "anthropic"
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    @property
    def name(self) -> str:
        return self._name

    # ---- message conversion ----

    @staticmethod
    def _build_anthropic_messages(
        messages: list[Message],
    ) -> tuple[str, list[dict]]:
        """Convert our Message list to Anthropic format.

        Returns (system_prompt, messages_list).
        Anthropic requires:
        - system as a top-level param, not in messages
        - tool results as role=user with tool_result content blocks
        - assistant tool_calls as tool_use content blocks
        """
        system_prompt = ""
        anthropic_msgs: list[dict] = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
                continue

            if msg.role == "assistant":
                content_blocks: list[dict] = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        args = json.loads(tc.arguments) if tc.arguments else {}
                        content_blocks.append(
                            {
                                "type": "tool_use",
                                "id": tc.id,
                                "name": tc.name,
                                "input": args,
                            }
                        )
                if not content_blocks:
                    content_blocks.append({"type": "text", "text": ""})
                anthropic_msgs.append({"role": "assistant", "content": content_blocks})

            elif msg.role == "tool":
                # Anthropic expects tool results as role=user with tool_result blocks
                block = {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content,
                }
                # Merge with previous user message if it's already a tool result list
                if (
                    anthropic_msgs
                    and anthropic_msgs[-1]["role"] == "user"
                    and isinstance(anthropic_msgs[-1]["content"], list)
                    and anthropic_msgs[-1]["content"]
                    and anthropic_msgs[-1]["content"][0].get("type") == "tool_result"
                ):
                    anthropic_msgs[-1]["content"].append(block)
                else:
                    anthropic_msgs.append({"role": "user", "content": [block]})

            elif msg.role == "user":
                anthropic_msgs.append({"role": "user", "content": msg.content})

        return system_prompt, anthropic_msgs

    @staticmethod
    def _build_tool_definitions(tools: list[ToolDefinition]) -> list[dict]:
        """Convert tool definitions to Anthropic format.

        Standard tools → {name, description, input_schema}
        Computer use tools → {type: "computer_20241022", ...} with extra fields
        """
        defs = []
        for tool in tools:
            if tool.tool_type != "function":
                # Computer use tool — pass type + extra fields directly
                tool_def: dict = {"type": tool.tool_type}
                tool_def.update(tool.extra)
                defs.append(tool_def)
            else:
                defs.append(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.parameters,
                    }
                )
        return defs

    async def stream(
        self,
        messages: list[Message],
        model: str,
        *,
        temperature: float = 0.7,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        system_prompt, anthropic_msgs = self._build_anthropic_messages(messages)

        kwargs: dict = {
            "model": model,
            "messages": anthropic_msgs,
            "temperature": temperature,
            "max_tokens": 4096,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        tool_defs = []
        has_computer_use = False
        if tools:
            tool_defs = self._build_tool_definitions(tools)
            kwargs["tools"] = tool_defs
            has_computer_use = any(t.tool_type != "function" for t in tools)

        if has_computer_use:
            kwargs["betas"] = ["computer-use-2024-10-22"]

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                # Track current content block for tool use accumulation
                current_tool_id: str | None = None
                current_tool_name: str | None = None
                accumulated_json = ""
                tool_calls: list[ToolCall] = []

                async for event in stream:
                    event_type = event.type

                    if event_type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            current_tool_id = block.id
                            current_tool_name = block.name
                            accumulated_json = ""

                    elif event_type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            yield StreamChunk(delta_content=delta.text)
                        elif delta.type == "input_json_delta":
                            accumulated_json += delta.partial_json

                    elif event_type == "content_block_stop":
                        if current_tool_id is not None:
                            tool_calls.append(
                                ToolCall(
                                    id=current_tool_id,
                                    name=current_tool_name or "",
                                    arguments=accumulated_json or "{}",
                                )
                            )
                            current_tool_id = None
                            current_tool_name = None
                            accumulated_json = ""

                    elif event_type == "message_stop":
                        if tool_calls:
                            yield StreamChunk(
                                tool_calls=tool_calls, finish_reason="tool_calls"
                            )
                            tool_calls = []
                        else:
                            yield StreamChunk(finish_reason="stop")

        except anthropic.APIError as e:
            raise LLMError(f"Anthropic API error: {e}") from e
        except anthropic.APIConnectionError as e:
            raise LLMError(f"Error connecting to Anthropic: {e}") from e

    async def list_models(self) -> list[str]:
        """Return commonly available Anthropic models."""
        return [
            "claude-sonnet-4-20250514",
            "claude-haiku-4-20250414",
            "claude-opus-4-20250514",
        ]

    async def close(self) -> None:
        await self._client.close()
