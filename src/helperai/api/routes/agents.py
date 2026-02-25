"""Agent CRUD + thread + message routes."""

from __future__ import annotations

import json

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sse_starlette.sse import EventSourceResponse

from helperai.agents.manager import AgentManager
from helperai.api.deps import get_agent_manager
from helperai.core.exceptions import AgentNotFoundError

router = APIRouter()


class MessageRequest(BaseModel):
    message: str
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


_NAME_RE = re.compile(r"^[a-zA-Z0-9_\- ]{1,100}$")


class CreateAgentRequest(BaseModel):
    name: str
    role: str
    goal: str = ""
    provider_name: str = ""
    model_name: str = ""
    tool_names: list[str] = []
    parent_id: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Agent name must not be empty")
        if len(v) > 100:
            raise ValueError("Agent name must be 100 characters or fewer")
        if not _NAME_RE.match(v):
            raise ValueError("Agent name may only contain letters, digits, spaces, hyphens, and underscores")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if len(v) > 10_000:
            raise ValueError("Role must be 10 000 characters or fewer")
        return v

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, v: str) -> str:
        if len(v) > 10_000:
            raise ValueError("Goal must be 10 000 characters or fewer")
        return v

    @field_validator("tool_names")
    @classmethod
    def validate_tool_names(cls, v: list[str]) -> list[str]:
        if len(v) > 50:
            raise ValueError("Cannot specify more than 50 tools")
        for name in v:
            if not re.match(r"^[a-zA-Z0-9_]{1,100}$", name):
                raise ValueError(f"Invalid tool name: {name!r}")
        return v

    @field_validator("provider_name")
    @classmethod
    def validate_provider_name(cls, v: str) -> str:
        if v and not re.match(r"^[a-zA-Z0-9_\-]{1,50}$", v):
            raise ValueError("Invalid provider name")
        return v

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        if v and not re.match(r"^[a-zA-Z0-9_\-.:]{1,100}$", v):
            raise ValueError("Invalid model name")
        return v


class UpdateAgentRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    goal: str | None = None
    provider_name: str | None = None
    model_name: str | None = None
    tool_names: list[str] | None = None
    parent_id: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Agent name must not be empty")
        if len(v) > 100:
            raise ValueError("Agent name must be 100 characters or fewer")
        if not _NAME_RE.match(v):
            raise ValueError("Agent name may only contain letters, digits, spaces, hyphens, and underscores")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 10_000:
            raise ValueError("Role must be 10 000 characters or fewer")
        return v

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 10_000:
            raise ValueError("Goal must be 10 000 characters or fewer")
        return v

    @field_validator("tool_names")
    @classmethod
    def validate_tool_names(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        if len(v) > 50:
            raise ValueError("Cannot specify more than 50 tools")
        for name in v:
            if not re.match(r"^[a-zA-Z0-9_]{1,100}$", name):
                raise ValueError(f"Invalid tool name: {name!r}")
        return v

    @field_validator("provider_name")
    @classmethod
    def validate_provider_name(cls, v: str | None) -> str | None:
        if v and not re.match(r"^[a-zA-Z0-9_\-]{1,50}$", v):
            raise ValueError("Invalid provider name")
        return v

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, v: str | None) -> str | None:
        if v and not re.match(r"^[a-zA-Z0-9_\-.:]{1,100}$", v):
            raise ValueError("Invalid model name")
        return v


def _agent_to_dict(agent) -> dict:
    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role[:200] if agent.role else "",
        "goal": agent.goal,
        "status": agent.status,
        "parent_id": agent.parent_id,
        "provider_name": agent.provider_name,
        "model_name": agent.model_name,
        "tool_names": agent.tool_names if hasattr(agent, 'tool_names') else [],
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }


def _message_to_dict(msg) -> dict:
    return {
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "tool_calls": msg.tool_calls,
        "tool_call_id": msg.tool_call_id,
        "sender_name": msg.sender_name,
        "sequence": msg.sequence,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


@router.get("/api/agents")
async def list_agents(manager: AgentManager = Depends(get_agent_manager)):
    agents = await manager.list_agents()
    return [_agent_to_dict(a) for a in agents]


@router.post("/api/agents")
async def create_agent(
    req: CreateAgentRequest,
    manager: AgentManager = Depends(get_agent_manager),
):
    # If no parent_id specified, make it a child of Ash (the master agent)
    parent_id = req.parent_id
    if parent_id is None:
        # Find Ash's ID (the agent with no parent)
        agents = await manager.list_agents()
        ash = next((a for a in agents if a.parent_id is None and a.name == "Ash"), None)
        if ash:
            parent_id = ash.id

    agent = await manager.create_agent(
        name=req.name,
        role=req.role,
        goal=req.goal,
        parent_id=parent_id,
        provider_name=req.provider_name or "",
        model_name=req.model_name or "",
        tool_names=req.tool_names,
    )
    # Auto-start the agent so it's ready for messages
    await manager.start_agent(agent.id)
    return _agent_to_dict(agent)


@router.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str, manager: AgentManager = Depends(get_agent_manager)):
    agent = await manager.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _agent_to_dict(agent)


@router.put("/api/agents/{agent_id}")
async def update_agent(
    agent_id: str,
    req: UpdateAgentRequest,
    manager: AgentManager = Depends(get_agent_manager),
):
    # Get the agent from DB
    from helperai.db.engine import get_session_factory
    from sqlalchemy import select
    from helperai.db.models import Agent as AgentModel

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(AgentModel).where(AgentModel.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Don't allow editing Ash/Eve's basic properties, but allow changing parent_id
        if agent.parent_id is None and req.parent_id is None:
            # Only block if trying to edit Ash and NOT changing parent_id
            if req.name is not None or req.role is not None or req.goal is not None:
                raise HTTPException(status_code=403, detail="Cannot edit master agent properties")

        # Update fields if provided
        if req.name is not None:
            agent.name = req.name
        if req.role is not None:
            agent.role = req.role
        if req.goal is not None:
            agent.goal = req.goal
        if req.provider_name is not None:
            agent.provider_name = req.provider_name
        if req.model_name is not None:
            agent.model_name = req.model_name
        if req.tool_names is not None:
            agent.tool_names = req.tool_names
        if req.parent_id is not None:
            agent.parent_id = req.parent_id

        await session.commit()
        await session.refresh(agent)

        # If agent is in memory, restart it to apply changes
        if manager.is_agent_started(agent_id):
            await manager.restart_agent(agent_id)

        return _agent_to_dict(agent)


@router.get("/api/agents/{agent_id}/thread")
async def get_thread(agent_id: str, manager: AgentManager = Depends(get_agent_manager)):
    messages = await manager.get_thread(agent_id)
    return [_message_to_dict(m) for m in messages]


@router.post("/api/agents/{agent_id}/message")
async def message_agent(
    agent_id: str,
    req: MessageRequest,
    manager: AgentManager = Depends(get_agent_manager),
):
    try:
        # Auto-start agent if not already started in memory
        if not manager.is_agent_started(agent_id):
            await manager.start_agent(agent_id)

        async def event_generator():
            async for event in manager.send_message_stream(
                agent_id, req.message, sender_name=req.sender_name
            ):
                yield {"event": event.get("type", "message"), "data": json.dumps(event)}

        return EventSourceResponse(event_generator())
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="Agent not found")


@router.post("/api/agents/{agent_id}/cancel")
async def cancel_agent(agent_id: str, manager: AgentManager = Depends(get_agent_manager)):
    """Cancel the current operation for an agent (like ESC in Claude Code)."""
    try:
        was_cancelled = await manager.cancel_agent(agent_id)
        if was_cancelled:
            return {"status": "cancelled", "message": "Agent operation cancelled"}
        else:
            return {"status": "not_running", "message": "Agent was not running"}
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="Agent not found")


@router.delete("/api/agents/{agent_id}")
async def destroy_agent(agent_id: str, manager: AgentManager = Depends(get_agent_manager)):
    try:
        await manager.destroy_agent(agent_id)
        return {"status": "destroyed"}
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="Agent not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
