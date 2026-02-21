"""WebSocket endpoint for real-time agent events."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from helperai.core.events import Event, EventBus
from helperai.api.deps import get_event_bus

router = APIRouter()


@router.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    event_bus = get_event_bus()

    queue: asyncio.Queue[Event] = asyncio.Queue()

    async def listener(event: Event) -> None:
        await queue.put(event)

    event_bus.on_all(listener)

    try:
        while True:
            event = await queue.get()
            await websocket.send_text(
                json.dumps(
                    {
                        "type": event.type.value,
                        "agent_id": event.agent_id,
                        "data": event.data,
                        "timestamp": event.timestamp.isoformat(),
                    }
                )
            )
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.off_all(listener)
