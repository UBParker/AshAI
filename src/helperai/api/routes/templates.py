"""Agent config template CRUD routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from helperai.db.engine import get_session_factory
from helperai.db.models import Agent, AgentTemplate

router = APIRouter()


class TemplateCreateRequest(BaseModel):
    display_name: str
    description: str = ""
    role: str = ""
    goal: str = ""
    provider_name: str = ""
    model_name: str = ""
    temperature: float = 0.7
    tool_names: list[str] = []


class TemplateUpdateRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    role: str | None = None
    goal: str | None = None
    provider_name: str | None = None
    model_name: str | None = None
    temperature: float | None = None
    tool_names: list[str] | None = None


class SaveAsTemplateRequest(BaseModel):
    display_name: str
    description: str = ""


def _template_to_dict(t: AgentTemplate) -> dict:
    return {
        "id": t.id,
        "display_name": t.display_name,
        "description": t.description,
        "role": t.role,
        "goal": t.goal,
        "provider_name": t.provider_name,
        "model_name": t.model_name,
        "temperature": t.temperature,
        "tool_names": t.tool_names,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("/api/templates")
async def list_templates():
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(AgentTemplate).order_by(AgentTemplate.created_at.desc())
        )
        templates = result.scalars().all()
        return [_template_to_dict(t) for t in templates]


@router.post("/api/templates")
async def create_template(req: TemplateCreateRequest):
    session_factory = get_session_factory()
    async with session_factory() as session:
        template = AgentTemplate(
            display_name=req.display_name,
            description=req.description,
            role=req.role,
            goal=req.goal,
            provider_name=req.provider_name,
            model_name=req.model_name,
            temperature=req.temperature,
        )
        template.tool_names = req.tool_names
        session.add(template)
        await session.commit()
        await session.refresh(template)
        return _template_to_dict(template)


@router.post("/api/templates/from-agent/{agent_id}")
async def save_agent_as_template(agent_id: str, req: SaveAsTemplateRequest):
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")

        template = AgentTemplate(
            display_name=req.display_name,
            description=req.description,
            role=agent.role,
            goal=agent.goal,
            provider_name=agent.provider_name,
            model_name=agent.model_name,
            temperature=agent.temperature,
            tool_names_json=agent.tool_names_json,
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        return _template_to_dict(template)


@router.get("/api/templates/export")
async def export_templates():
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(AgentTemplate).order_by(AgentTemplate.created_at.desc())
        )
        templates = result.scalars().all()

    export_data = {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "templates": [
            {
                "display_name": t.display_name,
                "description": t.description,
                "role": t.role,
                "goal": t.goal,
                "provider_name": t.provider_name,
                "model_name": t.model_name,
                "temperature": t.temperature,
                "tool_names": t.tool_names,
            }
            for t in templates
        ],
    }
    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": "attachment; filename=agent_templates.json"
        },
    )


@router.post("/api/templates/import")
async def import_templates(file: UploadFile):
    import json

    content = await file.read()
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    if not isinstance(data, dict) or "templates" not in data:
        raise HTTPException(status_code=400, detail="Invalid template export format")

    session_factory = get_session_factory()
    imported = 0
    skipped = 0

    async with session_factory() as session:
        # Get existing display names to skip duplicates
        result = await session.execute(select(AgentTemplate.display_name))
        existing_names = {row[0] for row in result.all()}

        for t in data["templates"]:
            if not isinstance(t, dict) or "display_name" not in t:
                continue
            if t["display_name"] in existing_names:
                skipped += 1
                continue

            template = AgentTemplate(
                display_name=t["display_name"],
                description=t.get("description", ""),
                role=t.get("role", ""),
                goal=t.get("goal", ""),
                provider_name=t.get("provider_name", ""),
                model_name=t.get("model_name", ""),
                temperature=t.get("temperature", 0.7),
            )
            template.tool_names = t.get("tool_names", [])
            session.add(template)
            existing_names.add(t["display_name"])
            imported += 1

        await session.commit()

    return {"imported": imported, "skipped": skipped}


@router.get("/api/templates/{template_id}")
async def get_template(template_id: str):
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(AgentTemplate).where(AgentTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if template is None:
            raise HTTPException(status_code=404, detail="Template not found")
        return _template_to_dict(template)


@router.put("/api/templates/{template_id}")
async def update_template(template_id: str, req: TemplateUpdateRequest):
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(AgentTemplate).where(AgentTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if template is None:
            raise HTTPException(status_code=404, detail="Template not found")

        if req.display_name is not None:
            template.display_name = req.display_name
        if req.description is not None:
            template.description = req.description
        if req.role is not None:
            template.role = req.role
        if req.goal is not None:
            template.goal = req.goal
        if req.provider_name is not None:
            template.provider_name = req.provider_name
        if req.model_name is not None:
            template.model_name = req.model_name
        if req.temperature is not None:
            template.temperature = req.temperature
        if req.tool_names is not None:
            template.tool_names = req.tool_names

        await session.commit()
        await session.refresh(template)
        return _template_to_dict(template)


@router.delete("/api/templates/{template_id}")
async def delete_template(template_id: str):
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(AgentTemplate).where(AgentTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if template is None:
            raise HTTPException(status_code=404, detail="Template not found")

        await session.delete(template)
        await session.commit()

    return {"status": "deleted"}
