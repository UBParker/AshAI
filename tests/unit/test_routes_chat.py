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

    def test_null_byte_in_message_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="null bytes"):
            ChatRequest(message="hello\x00")

    def test_null_byte_in_sender_name_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="null bytes"):
            ChatRequest(message="hi", sender_name="\x00bad")

    def test_agent_id_valid_hex(self):
        req = ChatRequest(message="hi", agent_id="a1b2c3d4e5f6")
        assert req.agent_id == "a1b2c3d4e5f6"

    def test_agent_id_valid_with_hyphen(self):
        req = ChatRequest(message="hi", agent_id="custom-agent")
        assert req.agent_id == "custom-agent"

    def test_agent_id_invalid_special_chars(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ChatRequest(message="hi", agent_id="agent with spaces!")

    def test_agent_id_too_long(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ChatRequest(message="hi", agent_id="a" * 65)

    def test_agent_id_none_allowed(self):
        req = ChatRequest(message="hi", agent_id=None)
        assert req.agent_id is None

    def test_unicode_nfc_normalization_in_message(self):
        decomposed = "e\u0301"  # e + combining accent
        req = ChatRequest(message=decomposed)
        assert req.message == "\u00e9"  # NFC composed form


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
