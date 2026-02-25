"""Tests for API routes — agents endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from helperai.api.routes.agents import router, _agent_to_dict, _message_to_dict
from helperai.core.exceptions import AgentNotFoundError


# -- helpers ------------------------------------------------------------------


def _make_mock_agent(**overrides):
    agent = MagicMock()
    agent.id = overrides.get("id", "agent-1")
    agent.name = overrides.get("name", "TestAgent")
    agent.role = overrides.get("role", "helper")
    agent.goal = overrides.get("goal", "help users")
    agent.status = overrides.get("status", "idle")
    agent.parent_id = overrides.get("parent_id", "parent-1")
    agent.provider_name = overrides.get("provider_name", "openai")
    agent.model_name = overrides.get("model_name", "gpt-4")
    agent.tool_names = overrides.get("tool_names", ["read_file"])
    agent.created_at = overrides.get("created_at", None)
    return agent


def _make_mock_message(**overrides):
    msg = MagicMock()
    msg.id = overrides.get("id", "msg-1")
    msg.role = overrides.get("role", "user")
    msg.content = overrides.get("content", "hello")
    msg.tool_calls = overrides.get("tool_calls", None)
    msg.tool_call_id = overrides.get("tool_call_id", None)
    msg.sender_name = overrides.get("sender_name", "User")
    msg.sequence = overrides.get("sequence", 0)
    msg.created_at = overrides.get("created_at", None)
    return msg


def _make_app(manager_mock: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[
        __import__("helperai.api.deps", fromlist=["get_agent_manager"]).get_agent_manager
    ] = lambda: manager_mock
    return app


def _client(manager_mock: MagicMock) -> TestClient:
    return TestClient(_make_app(manager_mock))


# -- unit helpers -------------------------------------------------------------


class TestAgentToDict:
    def test_basic(self):
        agent = _make_mock_agent()
        d = _agent_to_dict(agent)
        assert d["id"] == "agent-1"
        assert d["name"] == "TestAgent"
        assert d["tool_names"] == ["read_file"]

    def test_role_truncated_to_200(self):
        agent = _make_mock_agent(role="x" * 300)
        d = _agent_to_dict(agent)
        assert len(d["role"]) == 200

    def test_no_tool_names_attr(self):
        agent = _make_mock_agent()
        del agent.tool_names  # remove the attribute
        d = _agent_to_dict(agent)
        assert d["tool_names"] == []


class TestMessageToDict:
    def test_basic(self):
        msg = _make_mock_message()
        d = _message_to_dict(msg)
        assert d["id"] == "msg-1"
        assert d["content"] == "hello"
        assert d["sender_name"] == "User"


# -- route tests --------------------------------------------------------------


class TestListAgents:
    def test_list_agents(self):
        manager = AsyncMock()
        manager.list_agents.return_value = [_make_mock_agent(), _make_mock_agent(id="agent-2", name="Bob")]
        client = _client(manager)
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == "agent-1"
        assert data[1]["id"] == "agent-2"

    def test_list_agents_empty(self):
        manager = AsyncMock()
        manager.list_agents.return_value = []
        client = _client(manager)
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetAgent:
    def test_found(self):
        manager = AsyncMock()
        manager.get_agent.return_value = _make_mock_agent()
        client = _client(manager)
        resp = client.get("/api/agents/agent-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "agent-1"

    def test_not_found(self):
        manager = AsyncMock()
        manager.get_agent.return_value = None
        client = _client(manager)
        resp = client.get("/api/agents/missing")
        assert resp.status_code == 404


class TestCreateAgent:
    def test_creates_with_ash_parent(self):
        ash = _make_mock_agent(id="ash-id", name="Ash", parent_id=None)
        manager = AsyncMock()
        manager.list_agents.return_value = [ash]
        new_agent = _make_mock_agent(id="new-1", parent_id="ash-id")
        manager.create_agent.return_value = new_agent
        client = _client(manager)

        resp = client.post("/api/agents", json={
            "name": "Alice",
            "role": "coder",
        })
        assert resp.status_code == 200
        manager.create_agent.assert_called_once()
        call_kwargs = manager.create_agent.call_args.kwargs
        assert call_kwargs["parent_id"] == "ash-id"
        manager.start_agent.assert_called_once_with("new-1")

    def test_creates_with_explicit_parent(self):
        manager = AsyncMock()
        new_agent = _make_mock_agent(id="new-1", parent_id="explicit-parent")
        manager.create_agent.return_value = new_agent
        client = _client(manager)

        resp = client.post("/api/agents", json={
            "name": "Bob",
            "role": "assistant",
            "parent_id": "explicit-parent",
        })
        assert resp.status_code == 200
        call_kwargs = manager.create_agent.call_args.kwargs
        assert call_kwargs["parent_id"] == "explicit-parent"

    def test_invalid_name(self):
        manager = AsyncMock()
        client = _client(manager)
        resp = client.post("/api/agents", json={
            "name": "!!!invalid!!!",
            "role": "test",
        })
        assert resp.status_code == 422

    def test_empty_name(self):
        manager = AsyncMock()
        client = _client(manager)
        resp = client.post("/api/agents", json={
            "name": "",
            "role": "test",
        })
        assert resp.status_code == 422


class TestGetThread:
    def test_returns_messages(self):
        manager = AsyncMock()
        manager.get_thread.return_value = [_make_mock_message(), _make_mock_message(id="msg-2")]
        client = _client(manager)
        resp = client.get("/api/agents/agent-1/thread")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestCancelAgent:
    def test_cancel_running(self):
        manager = AsyncMock()
        manager.cancel_agent.return_value = True
        client = _client(manager)
        resp = client.post("/api/agents/agent-1/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_not_running(self):
        manager = AsyncMock()
        manager.cancel_agent.return_value = False
        client = _client(manager)
        resp = client.post("/api/agents/agent-1/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_running"

    def test_cancel_not_found(self):
        manager = AsyncMock()
        manager.cancel_agent.side_effect = AgentNotFoundError("agent-1")
        client = _client(manager)
        resp = client.post("/api/agents/missing/cancel")
        assert resp.status_code == 404


class TestDestroyAgent:
    def test_destroy_ok(self):
        manager = AsyncMock()
        client = _client(manager)
        resp = client.delete("/api/agents/agent-1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "destroyed"

    def test_destroy_not_found(self):
        manager = AsyncMock()
        manager.destroy_agent.side_effect = AgentNotFoundError("x")
        client = _client(manager)
        resp = client.delete("/api/agents/missing")
        assert resp.status_code == 404

    def test_destroy_value_error(self):
        manager = AsyncMock()
        manager.destroy_agent.side_effect = ValueError("Cannot delete master")
        client = _client(manager)
        resp = client.delete("/api/agents/agent-1")
        assert resp.status_code == 400
