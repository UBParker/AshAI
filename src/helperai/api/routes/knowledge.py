"""Knowledge base CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from helperai.agents.manager import AgentManager
from helperai.api.deps import get_agent_manager
from helperai.db.engine import get_session_factory
from helperai.db.models import KnowledgeEntry

router = APIRouter()


class KnowledgeCreateRequest(BaseModel):
    title: str
    content: str
    added_by: str | None = None


class KnowledgeUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None


def _entry_to_dict(entry: KnowledgeEntry) -> dict:
    return {
        "id": entry.id,
        "title": entry.title,
        "content": entry.content,
        "added_by": entry.added_by,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


@router.get("/api/knowledge")
async def list_knowledge():
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(KnowledgeEntry).order_by(KnowledgeEntry.created_at.desc())
        )
        entries = result.scalars().all()
        return [_entry_to_dict(e) for e in entries]


@router.post("/api/knowledge")
async def add_knowledge(
    req: KnowledgeCreateRequest,
    manager: AgentManager = Depends(get_agent_manager),
):
    session_factory = get_session_factory()
    async with session_factory() as session:
        entry = KnowledgeEntry(
            title=req.title,
            content=req.content,
            added_by=req.added_by,
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)

    # Refresh Ash's system prompt with updated knowledge
    await manager.refresh_knowledge()
    return _entry_to_dict(entry)


@router.put("/api/knowledge/{entry_id}")
async def update_knowledge(
    entry_id: str,
    req: KnowledgeUpdateRequest,
    manager: AgentManager = Depends(get_agent_manager),
):
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            raise HTTPException(status_code=404, detail="Knowledge entry not found")

        if req.title is not None:
            entry.title = req.title
        if req.content is not None:
            entry.content = req.content
        await session.commit()
        await session.refresh(entry)

    await manager.refresh_knowledge()
    return _entry_to_dict(entry)


@router.delete("/api/knowledge/{entry_id}")
async def delete_knowledge(
    entry_id: str,
    manager: AgentManager = Depends(get_agent_manager),
):
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            raise HTTPException(status_code=404, detail="Knowledge entry not found")

        await session.delete(entry)
        await session.commit()

    await manager.refresh_knowledge()
    return {"status": "deleted"}
