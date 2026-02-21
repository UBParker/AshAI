"""Tool protocol and context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from helperai.llm.message_types import ToolDefinition

if TYPE_CHECKING:
    from helperai.agents.manager import AgentManager
    from helperai.core.approval import ApprovalManager
    from helperai.core.events import EventBus


@dataclass
class ToolContext:
    """Runtime context passed to every tool invocation."""

    agent_id: str
    agent_manager: AgentManager
    event_bus: EventBus
    approval_manager: ApprovalManager | None = field(default=None)


class Tool(Protocol):
    """Interface for all tools."""

    @property
    def definition(self) -> ToolDefinition: ...

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        """Execute the tool. Returns a string result."""
        ...
