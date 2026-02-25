"""Tests for API routes — tools endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from helperai.api.routes.tools import router


# -- helpers ------------------------------------------------------------------


def _make_tool(name: str, description: str = "A tool", requires_approval: bool = False):
    tool = MagicMock()
    tool.definition = MagicMock()
    tool.definition.description = description
    tool.requires_approval = requires_approval
    return name, tool


def _make_app(registry_mock: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[
        __import__("helperai.api.deps", fromlist=["get_tool_registry"]).get_tool_registry
    ] = lambda: registry_mock
    return app


def _client(registry_mock: MagicMock) -> TestClient:
    return TestClient(_make_app(registry_mock))


# -- GET /api/tools -----------------------------------------------------------


class TestListTools:
    def test_returns_tools(self):
        mock = MagicMock()
        t1_name, t1 = _make_tool("read_file", "Read a file")
        t2_name, t2 = _make_tool("run_command", "Run a command", requires_approval=True)
        mock.all.return_value = {t1_name: t1, t2_name: t2}

        resp = _client(mock).get("/api/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "read_file"
        assert data[0]["description"] == "Read a file"
        assert data[0]["requires_approval"] is False
        assert data[1]["name"] == "run_command"
        assert data[1]["requires_approval"] is True

    def test_empty_registry(self):
        mock = MagicMock()
        mock.all.return_value = {}
        resp = _client(mock).get("/api/tools")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_tool_without_requires_approval_attr(self):
        """Tools that lack requires_approval should default to False via getattr."""
        mock = MagicMock()
        tool = MagicMock(spec=[])  # empty spec — no attributes
        tool.definition = MagicMock()
        tool.definition.description = "bare tool"
        mock.all.return_value = {"bare": tool}

        resp = _client(mock).get("/api/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["requires_approval"] is False
