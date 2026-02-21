"""POST /api/chat — Send message to Eve (or any agent), SSE stream response."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from helperai.agents.manager import AgentManager
from helperai.api.deps import get_agent_manager

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    agent_id: str | None = None  # defaults to Eve
    sender_name: str | None = None


@router.post("/api/chat")
async def chat(
    req: ChatRequest,
    manager: AgentManager = Depends(get_agent_manager),
):
    agent_id = req.agent_id or manager.eve_id
    if agent_id is None:
        return {"error": "Eve not initialized"}

    async def event_generator():
        async for event in manager.send_message_stream(
            agent_id, req.message, sender_name=req.sender_name
        ):
            yield {"event": event.get("type", "message"), "data": json.dumps(event)}

    return EventSourceResponse(event_generator())
