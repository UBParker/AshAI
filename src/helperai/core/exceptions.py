"""Exception hierarchy for helperAI."""

from __future__ import annotations


class HelperAIError(Exception):
    """Base exception for all helperAI errors."""


class InvalidTransitionError(HelperAIError):
    """Raised when an agent state transition is not allowed."""

    def __init__(self, from_status: str, to_status: str) -> None:
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"Cannot transition from {from_status} to {to_status}")


class AgentNotFoundError(HelperAIError):
    """Raised when a requested agent does not exist."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        super().__init__(f"Agent not found: {agent_id}")


class ProviderNotFoundError(HelperAIError):
    """Raised when a requested LLM provider is not configured."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Provider not found: {name}")


class ToolNotFoundError(HelperAIError):
    """Raised when a requested tool is not registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Tool not found: {name}")


class ToolExecutionError(HelperAIError):
    """Raised when a tool fails during execution."""


class LLMError(HelperAIError):
    """Raised for LLM provider errors."""
