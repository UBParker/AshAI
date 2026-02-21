"""Tests for the event bus."""

import pytest

from helperai.core.events import Event, EventBus, EventType


@pytest.fixture
def bus():
    return EventBus()


async def test_listener_receives_event(bus):
    received = []

    async def listener(event):
        received.append(event)

    bus.on(EventType.AGENT_CREATED, listener)
    event = Event(type=EventType.AGENT_CREATED, agent_id="abc")
    await bus.emit(event)

    assert len(received) == 1
    assert received[0].agent_id == "abc"


async def test_global_listener(bus):
    received = []

    async def listener(event):
        received.append(event)

    bus.on_all(listener)
    await bus.emit(Event(type=EventType.AGENT_CREATED, agent_id="a"))
    await bus.emit(Event(type=EventType.AGENT_DESTROYED, agent_id="b"))

    assert len(received) == 2


async def test_off_removes_listener(bus):
    received = []

    async def listener(event):
        received.append(event)

    bus.on(EventType.AGENT_CREATED, listener)
    bus.off(EventType.AGENT_CREATED, listener)
    await bus.emit(Event(type=EventType.AGENT_CREATED, agent_id="x"))

    assert len(received) == 0


async def test_listener_error_does_not_break_others(bus):
    results = []

    async def bad_listener(event):
        raise ValueError("boom")

    async def good_listener(event):
        results.append(event)

    bus.on(EventType.AGENT_CREATED, bad_listener)
    bus.on(EventType.AGENT_CREATED, good_listener)
    await bus.emit(Event(type=EventType.AGENT_CREATED, agent_id="test"))

    assert len(results) == 1
