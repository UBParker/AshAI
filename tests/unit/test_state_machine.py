"""Tests for agent state machine."""

import pytest

from helperai.agents.state import can_transition, validate_transition
from helperai.core.exceptions import InvalidTransitionError
from helperai.core.types import AgentStatus


def test_valid_transitions():
    assert can_transition(AgentStatus.CREATED, AgentStatus.RUNNING)
    assert can_transition(AgentStatus.CREATED, AgentStatus.DESTROYED)
    assert can_transition(AgentStatus.RUNNING, AgentStatus.IDLE)
    assert can_transition(AgentStatus.RUNNING, AgentStatus.COMPLETED)
    assert can_transition(AgentStatus.RUNNING, AgentStatus.ERROR)
    assert can_transition(AgentStatus.IDLE, AgentStatus.RUNNING)
    assert can_transition(AgentStatus.COMPLETED, AgentStatus.RUNNING)
    assert can_transition(AgentStatus.ERROR, AgentStatus.RUNNING)


def test_invalid_transitions():
    assert not can_transition(AgentStatus.CREATED, AgentStatus.COMPLETED)
    assert not can_transition(AgentStatus.DESTROYED, AgentStatus.RUNNING)
    assert not can_transition(AgentStatus.IDLE, AgentStatus.COMPLETED)


def test_validate_raises_on_invalid():
    with pytest.raises(InvalidTransitionError):
        validate_transition(AgentStatus.CREATED, AgentStatus.COMPLETED)


def test_validate_passes_on_valid():
    validate_transition(AgentStatus.CREATED, AgentStatus.RUNNING)


def test_destroyed_is_terminal():
    assert not can_transition(AgentStatus.DESTROYED, AgentStatus.RUNNING)
    assert not can_transition(AgentStatus.DESTROYED, AgentStatus.CREATED)
