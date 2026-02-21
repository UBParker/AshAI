"""ConversationalAgent — the core agent run loop."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from helperai.core.events import Event, EventBus, EventType
from helperai.core.types import AgentStatus
from helperai.db.models import Agent as AgentModel
from helperai.llm.message_types import Message, StreamChunk, ToolCall, ToolDefinition
from helperai.llm.protocol import LLMProvider
from helperai.tools.protocol import Tool, ToolContext

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 35  # safety limit per step


class ConversationalAgent:
    """A single agent with its own conversation thread and tool access."""

    def __init__(
        self,
        agent_model: AgentModel,
        provider: LLMProvider,
        tools: dict[str, Tool],
        event_bus: EventBus,
        tool_context_factory: Any,  # callable(agent_id) -> ToolContext
    ) -> None:
        self.model = agent_model
        self._provider = provider
        self._tools = tools
        self._event_bus = event_bus
        self._tool_context_factory = tool_context_factory
        self._messages: list[Message] = []
        self._initialized = False

    @property
    def agent_id(self) -> str:
        return self.model.id

    def _tool_definitions(self) -> list[ToolDefinition]:
        return [t.definition for t in self._tools.values()]

    def load_history(self, messages: list[Message]) -> None:
        """Load conversation history from DB."""
        self._messages = list(messages)
        self._initialized = True

    def _ensure_system_message(self) -> None:
        if not self._messages or self._messages[0].role != "system":
            system_content = self.model.role or f"You are {self.model.name}."
            if self.model.goal:
                system_content += f"\n\nYour current goal: {self.model.goal}"
            self._messages.insert(0, Message(role="system", content=system_content))

    def update_system_prompt(self, new_role: str) -> None:
        """Update the system prompt in the message history."""
        system_content = new_role
        if self.model.goal:
            system_content += f"\n\nYour current goal: {self.model.goal}"
        if self._messages and self._messages[0].role == "system":
            self._messages[0] = Message(role="system", content=system_content)

    def add_user_message(self, content: str) -> None:
        self._ensure_system_message()
        self._messages.append(Message(role="user", content=content))

    def add_injected_message(self, role: str, content: str) -> None:
        """Add a message without triggering a response (e.g., report from sub-agent)."""
        self._ensure_system_message()
        self._messages.append(Message(role=role, content=content))

    async def step_stream(self) -> AsyncIterator[dict]:
        """Run one LLM call + tool execution loop. Yields SSE-style dicts.

        Yields dicts like:
            {"type": "content", "text": "..."}
            {"type": "tool_call", "name": "...", "arguments": {...}}
            {"type": "tool_result", "name": "...", "result": "..."}
            {"type": "done"}
        """
        self._ensure_system_message()
        tools_defs = self._tool_definitions() if self._tools else None

        for _round in range(MAX_TOOL_ROUNDS):
            # Stream LLM response
            full_content = ""
            tool_calls: list[ToolCall] = []

            async for chunk in self._provider.stream(
                messages=self._messages,
                model=self.model.model_name,
                temperature=self.model.temperature,
                tools=tools_defs,
            ):
                if chunk.delta_content:
                    full_content += chunk.delta_content
                    yield {"type": "content", "text": chunk.delta_content}

                    self._event_bus.emit_nowait(
                        Event(
                            type=EventType.AGENT_STREAM_CHUNK,
                            agent_id=self.agent_id,
                            data={"text": chunk.delta_content},
                        )
                    )

                if chunk.tool_calls:
                    tool_calls = chunk.tool_calls

            # Build assistant message
            assistant_msg = Message(
                role="assistant",
                content=full_content,
                tool_calls=tool_calls if tool_calls else None,
            )
            self._messages.append(assistant_msg)

            # If no tool calls, we're done
            if not tool_calls:
                self._event_bus.emit_nowait(
                    Event(
                        type=EventType.AGENT_STREAM_END,
                        agent_id=self.agent_id,
                        data={"content": full_content},
                    )
                )
                yield {"type": "done"}
                return

            # Execute tool calls
            for tc in tool_calls:
                yield {"type": "tool_call", "name": tc.name, "arguments": tc.arguments}

                tool = self._tools.get(tc.name)
                if tool is None:
                    result_str = json.dumps({"error": f"Unknown tool: {tc.name}"})
                else:
                    try:
                        args = json.loads(tc.arguments) if tc.arguments else {}
                        ctx = self._tool_context_factory(self.agent_id)

                        # Approval gate: if tool requires approval, ask the user
                        requires_approval = getattr(tool, "requires_approval", False)
                        if requires_approval and ctx.approval_manager is not None:
                            yield {
                                "type": "approval_requested",
                                "name": tc.name,
                                "arguments": args,
                            }
                            approved = await ctx.approval_manager.request_approval(
                                agent_id=self.agent_id,
                                tool_name=tc.name,
                                arguments=args,
                            )
                            if not approved:
                                result_str = json.dumps(
                                    {
                                        "error": f"User denied execution of {tc.name}",
                                        "denied": True,
                                    }
                                )
                                yield {
                                    "type": "tool_result",
                                    "name": tc.name,
                                    "result": result_str,
                                }
                                self._messages.append(
                                    Message(
                                        role="tool",
                                        content=result_str,
                                        tool_call_id=tc.id,
                                    )
                                )
                                continue

                        result_str = await tool.execute(args, ctx)
                    except Exception as e:
                        logger.exception("Tool %s failed", tc.name)
                        result_str = json.dumps({"error": str(e)})

                yield {"type": "tool_result", "name": tc.name, "result": result_str}

                # Add tool result message
                self._messages.append(
                    Message(role="tool", content=result_str, tool_call_id=tc.id)
                )

            # Loop continues — LLM will see tool results and respond

        # Exceeded tool rounds
        yield {"type": "content", "text": "\n[Reached maximum tool call rounds]"}
        yield {"type": "done"}

    def get_messages(self) -> list[Message]:
        return list(self._messages)
