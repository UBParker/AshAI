"""Provider listing + models routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from helperai.core.exceptions import ProviderNotFoundError
from helperai.llm.registry import LLMRegistry
from helperai.api.deps import get_llm_registry

router = APIRouter()


@router.get("/api/providers")
async def list_providers(registry: LLMRegistry = Depends(get_llm_registry)):
    providers = registry.list_providers()
    return [
        {"name": name, "is_default": name == registry.default_name}
        for name in providers
    ]


@router.get("/api/providers/{name}/models")
async def list_models(name: str, registry: LLMRegistry = Depends(get_llm_registry)):
    try:
        provider = registry.get(name)
    except ProviderNotFoundError:
        raise HTTPException(status_code=404, detail=f"Provider '{name}' not found")

    models = await provider.list_models()
    return {"provider": name, "models": models}
