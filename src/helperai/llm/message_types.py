"""Message types for LLM communication."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON string


@dataclass
class ToolResult:
    tool_call_id: str
    content: str


@dataclass
class Message:
    role: str  # system, user, assistant, tool
    content: str = ""
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None  # for role=tool

    def to_openai_dict(self) -> dict:
        """Convert to OpenAI API format."""
        msg: dict = {"role": self.role, "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        return msg


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    tool_type: str = "function"  # "function" or anthropic computer-use types
    extra: dict = field(default_factory=dict)  # extra fields for specialized tools

    def to_openai_dict(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class StreamChunk:
    """A chunk from a streaming LLM response."""

    delta_content: str = ""
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None
