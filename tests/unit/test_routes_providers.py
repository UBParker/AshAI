"""Tests for API routes — providers endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from helperai.api.routes.providers import router
from helperai.core.exceptions import ProviderNotFoundError


def _make_app(registry_mock: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    from helperai.api.deps import get_llm_registry
    app.dependency_overrides[get_llm_registry] = lambda: registry_mock
    return app


def _client(registry_mock: MagicMock) -> TestClient:
    return TestClient(_make_app(registry_mock))


class TestListProviders:
    def test_returns_providers_with_default(self):
        registry = MagicMock()
        registry.list_providers.return_value = ["anthropic", "openai"]
        registry.default_name = "anthropic"
        client = _client(registry)

        resp = client.get("/api/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0] == {"name": "anthropic", "is_default": True}
        assert data[1] == {"name": "openai", "is_default": False}

    def test_empty_list(self):
        registry = MagicMock()
        registry.list_providers.return_value = []
        registry.default_name = None
        client = _client(registry)

        resp = client.get("/api/providers")
        assert resp.status_code == 200
        assert resp.json() == []


class TestListModels:
    def test_returns_models(self):
        registry = MagicMock()
        provider = AsyncMock()
        provider.list_models.return_value = ["gpt-4", "gpt-3.5"]
        registry.get.return_value = provider
        client = _client(registry)

        resp = client.get("/api/providers/openai/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "openai"
        assert data["models"] == ["gpt-4", "gpt-3.5"]

    def test_provider_not_found(self):
        registry = MagicMock()
        registry.get.side_effect = ProviderNotFoundError("bad")
        client = _client(registry)

        resp = client.get("/api/providers/bad/models")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]
