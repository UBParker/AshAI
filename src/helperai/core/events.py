"""In-process async event bus."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    AGENT_CREATED = "agent.created"
    AGENT_STATUS_CHANGED = "agent.status_changed"
    AGENT_MESSAGE = "agent.message"
    AGENT_STREAM_CHUNK = "agent.stream_chunk"
    AGENT_STREAM_END = "agent.stream_end"
    AGENT_DESTROYED = "agent.destroyed"
    AGENT_ERROR = "agent.error"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_RESOLVED = "approval.resolved"


@dataclass
class Event:
    type: EventType
    agent_id: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


Listener = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Async pub/sub event bus for real-time agent updates."""

    def __init__(self) -> None:
        self._listeners: dict[EventType, list[Listener]] = {}
        self._global_listeners: list[Listener] = []

    def on(self, event_type: EventType, listener: Listener) -> None:
        self._listeners.setdefault(event_type, []).append(listener)

    def on_all(self, listener: Listener) -> None:
        self._global_listeners.append(listener)

    def off(self, event_type: EventType, listener: Listener) -> None:
        listeners = self._listeners.get(event_type, [])
        if listener in listeners:
            listeners.remove(listener)

    def off_all(self, listener: Listener) -> None:
        if listener in self._global_listeners:
            self._global_listeners.remove(listener)

    async def emit(self, event: Event) -> None:
        listeners = list(self._listeners.get(event.type, []))
        listeners.extend(self._global_listeners)
        for listener in listeners:
            try:
                await listener(event)
            except Exception:
                logger.exception("Error in event listener for %s", event.type)

    def emit_nowait(self, event: Event) -> None:
        """Fire-and-forget emit (schedules the coroutine)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event))
        except RuntimeError:
            pass
