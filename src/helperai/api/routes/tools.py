"""Tools listing endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from helperai.api.deps import get_tool_registry
from helperai.tools.registry import ToolRegistry

router = APIRouter()


@router.get("/api/tools")
async def list_tools(registry: ToolRegistry = Depends(get_tool_registry)):
    tools = registry.all()
    return [
        {
            "name": name,
            "description": tool.definition.description,
            "requires_approval": getattr(tool, "requires_approval", False),
        }
        for name, tool in tools.items()
    ]
