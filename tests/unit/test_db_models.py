"""Tests for DB ORM models — JSON property round-trips and helpers."""

from __future__ import annotations

import json

from helperai.db.models import (
    Agent,
    KnowledgeEntry,
    PendingApproval,
    ProviderConfig,
    ThreadMessage,
    _new_id,
    _utcnow,
)


def test_new_id_length_and_uniqueness():
    ids = {_new_id() for _ in range(100)}
    assert len(ids) == 100  # all unique
    for i in ids:
        assert len(i) == 12
        assert i.isalnum()


def test_utcnow_has_timezone():
    now = _utcnow()
    assert now.tzinfo is not None


# -- Agent tool_names JSON round-trip --


def test_agent_tool_names_getter():
    agent = Agent(name="test", tool_names_json='["a", "b"]')
    assert agent.tool_names == ["a", "b"]


def test_agent_tool_names_setter():
    agent = Agent(name="test")
    agent.tool_names = ["x", "y", "z"]
    assert json.loads(agent.tool_names_json) == ["x", "y", "z"]


def test_agent_tool_names_empty():
    agent = Agent(name="test", tool_names_json="[]")
    assert agent.tool_names == []


# -- ThreadMessage tool_calls JSON round-trip --


def test_thread_message_tool_calls_none():
    msg = ThreadMessage(agent_id="a", role="user", tool_calls_json=None)
    assert msg.tool_calls is None


def test_thread_message_tool_calls_getter():
    msg = ThreadMessage(
        agent_id="a", role="assistant",
        tool_calls_json='[{"id": "tc1", "name": "test"}]',
    )
    assert msg.tool_calls == [{"id": "tc1", "name": "test"}]


def test_thread_message_tool_calls_setter():
    msg = ThreadMessage(agent_id="a", role="assistant")
    msg.tool_calls = [{"id": "tc2", "name": "foo"}]
    assert json.loads(msg.tool_calls_json) == [{"id": "tc2", "name": "foo"}]


def test_thread_message_tool_calls_setter_none():
    msg = ThreadMessage(agent_id="a", role="assistant")
    msg.tool_calls = None
    assert msg.tool_calls_json is None


# -- PendingApproval arguments JSON round-trip --


def test_pending_approval_arguments_getter():
    pa = PendingApproval(agent_id="a", tool_name="t", arguments_json='{"key": "value"}')
    assert pa.arguments == {"key": "value"}


def test_pending_approval_arguments_setter():
    pa = PendingApproval(agent_id="a", tool_name="t")
    pa.arguments = {"a": 1, "b": "two"}
    assert json.loads(pa.arguments_json) == {"a": 1, "b": "two"}


# -- ProviderConfig extra_config JSON round-trip --


def test_provider_config_extra_config_getter():
    pc = ProviderConfig(name="test", base_url="http://x", extra_config_json='{"timeout": 30}')
    assert pc.extra_config == {"timeout": 30}


def test_provider_config_extra_config_setter():
    pc = ProviderConfig(name="test", base_url="http://x")
    pc.extra_config = {"foo": "bar"}
    assert json.loads(pc.extra_config_json) == {"foo": "bar"}


def test_provider_config_extra_config_empty():
    pc = ProviderConfig(name="test", base_url="http://x", extra_config_json="{}")
    assert pc.extra_config == {}
