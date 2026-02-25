"""Tests for API routes — WebSocket endpoint."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from helperai.api.routes.ws import router
from helperai.core.events import Event, EventBus, EventType


def _make_app(event_bus: EventBus) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


class TestWebSocket:
    def test_receives_events(self):
        bus = EventBus()

        app = FastAPI()
        app.include_router(router)

        with patch("helperai.api.routes.ws.get_event_bus", return_value=bus):
            client = TestClient(app)
            with client.websocket_connect("/api/ws") as ws:
                # Emit an event — the listener was registered on connect
                import asyncio

                event = Event(
                    type=EventType.AGENT_MESSAGE,
                    agent_id="a1",
                    data={"content": "hello"},
                    timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
                )

                # The event bus is async, so we run emit in the loop
                async def _emit():
                    await bus.emit(event)

                asyncio.get_event_loop().run_until_complete(_emit())

                msg = ws.receive_text()
                parsed = json.loads(msg)
                assert parsed["type"] == "agent.message"
                assert parsed["agent_id"] == "a1"
                assert parsed["data"]["content"] == "hello"

    def test_disconnect_unsubscribes(self):
        bus = EventBus()

        app = FastAPI()
        app.include_router(router)

        with patch("helperai.api.routes.ws.get_event_bus", return_value=bus):
            client = TestClient(app)
            with client.websocket_connect("/api/ws") as ws:
                # There should be 1 global listener now
                assert len(bus._global_listeners) == 1

            # After disconnect, the listener should be removed
            assert len(bus._global_listeners) == 0
