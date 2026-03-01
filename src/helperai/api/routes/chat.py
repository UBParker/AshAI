"""POST /api/chat — Send message to Eve (or any agent), SSE stream response."""

from __future__ import annotations

import json
import re
import unicodedata

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sse_starlette.sse import EventSourceResponse

from helperai.agents.manager import AgentManager
from helperai.api.deps import check_message_rate_limit, get_agent_manager

router = APIRouter()

# Allowlist for agent_id values supplied in the request body.
# Agent IDs are 12-char hex strings; we also allow common separators so that
# test values like "custom-agent" or "eve-1" still pass validation.
_AGENT_ID_RE = re.compile(r"^[0-9a-zA-Z_\-]{1,64}$")


class ChatRequest(BaseModel):
    message: str
    agent_id: str | None = None  # defaults to Eve
    sender_name: str | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        if "\x00" in v:
            raise ValueError("Message must not contain null bytes")
        # Normalize unicode to NFC form to prevent homoglyph / encoding attacks
        v = unicodedata.normalize("NFC", v)
        if not v or not v.strip():
            raise ValueError("Message must not be empty")
        if len(v) > 100_000:
            raise ValueError("Message must be 100 000 characters or fewer")
        return v

    @field_validator("agent_id")
    @classmethod
    def validate_agent_id(cls, v: str | None) -> str | None:
        if v is not None and not _AGENT_ID_RE.match(v):
            raise ValueError(
                "agent_id must contain only alphanumeric characters, hyphens, or underscores "
                "(max 64 characters)"
            )
        return v

    @field_validator("sender_name")
    @classmethod
    def validate_sender_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if "\x00" in v:
            raise ValueError("Sender name must not contain null bytes")
        v = unicodedata.normalize("NFC", v)
        if len(v) > 100:
            raise ValueError("Sender name must be 100 characters or fewer")
        return v


@router.post("/api/chat")
async def chat(
    req: ChatRequest,
    manager: AgentManager = Depends(get_agent_manager),
    _: None = Depends(check_message_rate_limit),
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
