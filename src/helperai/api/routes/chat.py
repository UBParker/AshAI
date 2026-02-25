"""POST /api/chat — Send message to Eve (or any agent), SSE stream response."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sse_starlette.sse import EventSourceResponse

from helperai.agents.manager import AgentManager
from helperai.api.deps import get_agent_manager

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    agent_id: str | None = None  # defaults to Eve
    sender_name: str | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message must not be empty")
        if len(v) > 100_000:
            raise ValueError("Message must be 100 000 characters or fewer")
        return v

    @field_validator("sender_name")
    @classmethod
    def validate_sender_name(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 100:
            raise ValueError("Sender name must be 100 characters or fewer")
        return v


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
