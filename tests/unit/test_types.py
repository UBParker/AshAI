"""Tests for core types and enums."""

from __future__ import annotations

from helperai.core.types import AgentStatus, VALID_TRANSITIONS


def test_agent_status_values():
    assert AgentStatus.CREATED == "created"
    assert AgentStatus.RUNNING == "running"
    assert AgentStatus.IDLE == "idle"
    assert AgentStatus.WAITING_FOR_USER == "waiting_for_user"
    assert AgentStatus.COMPLETED == "completed"
    assert AgentStatus.ERROR == "error"
    assert AgentStatus.DESTROYED == "destroyed"


def test_agent_status_is_str():
    """AgentStatus members are usable as strings."""
    assert isinstance(AgentStatus.CREATED, str)
    assert f"status={AgentStatus.RUNNING}" == "status=running"


def test_all_statuses_have_transitions():
    """Every AgentStatus must appear as a key in VALID_TRANSITIONS."""
    for status in AgentStatus:
        assert status in VALID_TRANSITIONS, f"{status} missing from VALID_TRANSITIONS"


def test_destroyed_is_terminal():
    assert VALID_TRANSITIONS[AgentStatus.DESTROYED] == set()


def test_created_transitions():
    expected = {AgentStatus.RUNNING, AgentStatus.IDLE, AgentStatus.DESTROYED}
    assert VALID_TRANSITIONS[AgentStatus.CREATED] == expected


def test_running_transitions():
    expected = {
        AgentStatus.IDLE,
        AgentStatus.WAITING_FOR_USER,
        AgentStatus.COMPLETED,
        AgentStatus.ERROR,
        AgentStatus.DESTROYED,
    }
    assert VALID_TRANSITIONS[AgentStatus.RUNNING] == expected


def test_idle_transitions():
    expected = {AgentStatus.RUNNING, AgentStatus.DESTROYED}
    assert VALID_TRANSITIONS[AgentStatus.IDLE] == expected


def test_transition_targets_are_valid_statuses():
    """All transition targets must be valid AgentStatus values."""
    for source, targets in VALID_TRANSITIONS.items():
        for target in targets:
            assert isinstance(target, AgentStatus), f"Invalid target {target} for {source}"
