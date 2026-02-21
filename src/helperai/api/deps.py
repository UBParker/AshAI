"""Dependency injection for FastAPI routes."""

from __future__ import annotations

from helperai.agents.manager import AgentManager
from helperai.core.approval import ApprovalManager
from helperai.core.events import EventBus
from helperai.llm.registry import LLMRegistry
from helperai.tools.registry import ToolRegistry

# These are set during app lifespan startup
_agent_manager: AgentManager | None = None
_event_bus: EventBus | None = None
_llm_registry: LLMRegistry | None = None
_tool_registry: ToolRegistry | None = None
_approval_manager: ApprovalManager | None = None


def set_services(
    agent_manager: AgentManager,
    event_bus: EventBus,
    llm_registry: LLMRegistry,
    tool_registry: ToolRegistry,
    approval_manager: ApprovalManager | None = None,
) -> None:
    global _agent_manager, _event_bus, _llm_registry, _tool_registry, _approval_manager
    _agent_manager = agent_manager
    _event_bus = event_bus
    _llm_registry = llm_registry
    _tool_registry = tool_registry
    _approval_manager = approval_manager


def get_agent_manager() -> AgentManager:
    assert _agent_manager is not None, "AgentManager not initialized"
    return _agent_manager


def get_event_bus() -> EventBus:
    assert _event_bus is not None, "EventBus not initialized"
    return _event_bus


def get_llm_registry() -> LLMRegistry:
    assert _llm_registry is not None, "LLMRegistry not initialized"
    return _llm_registry


def get_tool_registry() -> ToolRegistry:
    assert _tool_registry is not None, "ToolRegistry not initialized"
    return _tool_registry


def get_approval_manager() -> ApprovalManager:
    assert _approval_manager is not None, "ApprovalManager not initialized"
    return _approval_manager
