"""Dependency injection for FastAPI routes."""

from __future__ import annotations

from fastapi import HTTPException, Request

from helperai.agents.manager import AgentManager
from helperai.api.rate_limiter import SlidingWindowRateLimiter
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

# Rate limiters — set to None to disable limiting entirely
_per_client_limiter: SlidingWindowRateLimiter | None = None
_global_limiter: SlidingWindowRateLimiter | None = None


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


def set_rate_limiters(
    per_client: SlidingWindowRateLimiter | None,
    global_: SlidingWindowRateLimiter | None,
) -> None:
    """Register rate limiter instances (called from app factory)."""
    global _per_client_limiter, _global_limiter
    _per_client_limiter = per_client
    _global_limiter = global_


async def check_message_rate_limit(request: Request) -> None:
    """FastAPI dependency: enforce rate limits on message endpoints.

    Raises HTTP 429 with a ``Retry-After`` header when a client exceeds the
    per-client or global request budget.  If both limiters are ``None`` (e.g.
    rate limiting is disabled in settings) the check is a no-op.
    """
    client_ip: str = request.client.host if request.client else "unknown"

    if _global_limiter is not None:
        allowed, retry_after = _global_limiter.check("global")
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Global rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

    if _per_client_limiter is not None:
        allowed, retry_after = _per_client_limiter.check(client_ip)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please wait before retrying.",
                headers={"Retry-After": str(int(retry_after) + 1)},
            )


def get_agent_manager() -> AgentManager:
    if _agent_manager is None:
        raise RuntimeError("AgentManager not initialized")
    return _agent_manager


def get_event_bus() -> EventBus:
    if _event_bus is None:
        raise RuntimeError("EventBus not initialized")
    return _event_bus


def get_llm_registry() -> LLMRegistry:
    if _llm_registry is None:
        raise RuntimeError("LLMRegistry not initialized")
    return _llm_registry


def get_tool_registry() -> ToolRegistry:
    if _tool_registry is None:
        raise RuntimeError("ToolRegistry not initialized")
    return _tool_registry


def get_approval_manager() -> ApprovalManager:
    if _approval_manager is None:
        raise RuntimeError("ApprovalManager not initialized")
    return _approval_manager
