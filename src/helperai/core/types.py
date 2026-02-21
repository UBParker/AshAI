"""Core types and enums."""

from __future__ import annotations

from enum import Enum


class AgentStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    IDLE = "idle"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    ERROR = "error"
    DESTROYED = "destroyed"


# Valid state transitions: from_status → set of allowed to_statuses
VALID_TRANSITIONS: dict[AgentStatus, set[AgentStatus]] = {
    AgentStatus.CREATED: {AgentStatus.RUNNING, AgentStatus.IDLE, AgentStatus.DESTROYED},
    AgentStatus.RUNNING: {
        AgentStatus.IDLE,
        AgentStatus.WAITING_FOR_USER,
        AgentStatus.COMPLETED,
        AgentStatus.ERROR,
        AgentStatus.DESTROYED,
    },
    AgentStatus.IDLE: {AgentStatus.RUNNING, AgentStatus.DESTROYED},
    AgentStatus.WAITING_FOR_USER: {AgentStatus.RUNNING, AgentStatus.DESTROYED},
    AgentStatus.COMPLETED: {AgentStatus.RUNNING, AgentStatus.DESTROYED},
    AgentStatus.ERROR: {AgentStatus.RUNNING, AgentStatus.DESTROYED},
    AgentStatus.DESTROYED: set(),  # terminal
}
