"""Agent state machine."""

from __future__ import annotations

from helperai.core.exceptions import InvalidTransitionError
from helperai.core.types import VALID_TRANSITIONS, AgentStatus


def validate_transition(from_status: AgentStatus, to_status: AgentStatus) -> None:
    """Raise InvalidTransitionError if the transition is not allowed."""
    allowed = VALID_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise InvalidTransitionError(from_status.value, to_status.value)


def can_transition(from_status: AgentStatus, to_status: AgentStatus) -> bool:
    """Return True if the transition is valid."""
    return to_status in VALID_TRANSITIONS.get(from_status, set())
