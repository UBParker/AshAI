"""Agent CRUD + thread + message routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from helperai.agents.manager import AgentManager
from helperai.api.deps import get_agent_manager
from helperai.core.exceptions import AgentNotFoundError

router = APIRouter()


class MessageRequest(BaseModel):
    message: str
    sender_name: str | None = None


class CreateAgentRequest(BaseModel):
    name: str
    role: str
    goal: str = ""
    provider_name: str = ""
    model_name: str = ""
    tool_names: list[str] = []


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
    agent = await manager.create_agent(
        name=req.name,
        role=req.role,
        goal=req.goal,
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
        async def event_generator():
            async for event in manager.send_message_stream(
                agent_id, req.message, sender_name=req.sender_name
            ):
                yield {"event": event.get("type", "message"), "data": json.dumps(event)}

        return EventSourceResponse(event_generator())
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
