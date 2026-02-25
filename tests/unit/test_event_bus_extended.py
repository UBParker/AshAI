"""Extended tests for EventBus — covers off_all and emit_nowait."""

import asyncio

import pytest

from helperai.core.events import Event, EventBus, EventType


async def test_off_all_removes_global_listener():
    bus = EventBus()
    received = []

    async def listener(event):
        received.append(event)

    bus.on_all(listener)
    bus.off_all(listener)
    await bus.emit(Event(type=EventType.AGENT_CREATED, agent_id="x"))
    assert len(received) == 0


async def test_off_nonexistent_listener():
    """Removing a listener that was never added should not raise."""
    bus = EventBus()

    async def listener(event):
        pass

    bus.off(EventType.AGENT_CREATED, listener)  # should not raise


async def test_off_all_nonexistent_listener():
    """Removing a global listener that was never added should not raise."""
    bus = EventBus()

    async def listener(event):
        pass

    bus.off_all(listener)  # should not raise


async def test_emit_nowait_schedules_event():
    bus = EventBus()
    received = []

    async def listener(event):
        received.append(event)

    bus.on(EventType.AGENT_CREATED, listener)
    bus.emit_nowait(Event(type=EventType.AGENT_CREATED, agent_id="test"))

    # Give the event loop a chance to process the task
    await asyncio.sleep(0.05)
    assert len(received) == 1


async def test_multiple_listeners_same_event():
    bus = EventBus()
    r1, r2 = [], []

    async def l1(event):
        r1.append(event)

    async def l2(event):
        r2.append(event)

    bus.on(EventType.AGENT_CREATED, l1)
    bus.on(EventType.AGENT_CREATED, l2)
    await bus.emit(Event(type=EventType.AGENT_CREATED, agent_id="x"))

    assert len(r1) == 1
    assert len(r2) == 1


async def test_event_has_timestamp():
    event = Event(type=EventType.AGENT_CREATED, agent_id="x")
    assert event.timestamp is not None
