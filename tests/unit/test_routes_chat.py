"""Tests for API routes — chat endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from helperai.api.routes.chat import router, ChatRequest


def _make_app(manager_mock: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    from helperai.api.deps import get_agent_manager
    app.dependency_overrides[get_agent_manager] = lambda: manager_mock
    return app


def _client(manager_mock: MagicMock) -> TestClient:
    return TestClient(_make_app(manager_mock))


class TestChatRequestValidation:
    def test_valid(self):
        req = ChatRequest(message="hello")
        assert req.message == "hello"
        assert req.agent_id is None

    def test_empty_message_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ChatRequest(message="")

    def test_whitespace_only_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ChatRequest(message="   ")

    def test_message_too_long(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ChatRequest(message="x" * 100_001)

    def test_sender_name_too_long(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ChatRequest(message="hi", sender_name="x" * 101)


class TestChatEndpoint:
    def test_eve_not_initialized(self):
        manager = AsyncMock()
        manager.eve_id = None
        client = _client(manager)
        resp = client.post("/api/chat", json={"message": "hello"})
        assert resp.status_code == 200
        assert resp.json()["error"] == "Eve not initialized"

    def test_chat_defaults_to_eve(self):
        manager = AsyncMock()
        manager.eve_id = "eve-1"

        async def fake_stream(agent_id, message, sender_name=None):
            yield {"type": "message", "content": "hi"}

        manager.send_message_stream = fake_stream
        client = _client(manager)
        resp = client.post("/api/chat", json={"message": "hello"})
        # SSE response — status should be 200
        assert resp.status_code == 200

    def test_chat_with_explicit_agent_id(self):
        manager = AsyncMock()
        manager.eve_id = "eve-1"

        async def fake_stream(agent_id, message, sender_name=None):
            assert agent_id == "custom-agent"
            yield {"type": "message", "content": "reply"}

        manager.send_message_stream = fake_stream
        client = _client(manager)
        resp = client.post("/api/chat", json={"message": "hello", "agent_id": "custom-agent"})
        assert resp.status_code == 200
