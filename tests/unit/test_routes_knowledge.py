"""Tests for API routes — knowledge endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from helperai.api.routes.knowledge import router, _entry_to_dict


# -- helpers ------------------------------------------------------------------


def _make_entry(**overrides):
    entry = MagicMock()
    entry.id = overrides.get("id", "k1")
    entry.title = overrides.get("title", "Test Entry")
    entry.content = overrides.get("content", "Some content")
    entry.added_by = overrides.get("added_by", "user")
    entry.created_at = overrides.get("created_at", datetime(2025, 1, 1, tzinfo=timezone.utc))
    entry.updated_at = overrides.get("updated_at", None)
    return entry


def _make_app(manager_mock: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[
        __import__("helperai.api.deps", fromlist=["get_agent_manager"]).get_agent_manager
    ] = lambda: manager_mock
    return app


def _client(manager_mock: MagicMock) -> TestClient:
    return TestClient(_make_app(manager_mock))


# -- _entry_to_dict -----------------------------------------------------------


class TestEntryToDict:
    def test_basic(self):
        entry = _make_entry()
        d = _entry_to_dict(entry)
        assert d["id"] == "k1"
        assert d["title"] == "Test Entry"
        assert d["content"] == "Some content"
        assert d["added_by"] == "user"
        assert d["created_at"] == "2025-01-01T00:00:00+00:00"
        assert d["updated_at"] is None

    def test_no_created_at(self):
        entry = _make_entry(created_at=None)
        d = _entry_to_dict(entry)
        assert d["created_at"] is None


# -- mock DB session helper ---------------------------------------------------


def _mock_session_factory(entries=None):
    """Create a mock session factory that returns entries for select queries."""
    session = AsyncMock()
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = entries or []

    # For scalar_one_or_none (used by get/update/delete)
    result.scalar_one_or_none.return_value = entries[0] if entries else None
    result.scalars.return_value = scalars

    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


# -- GET /api/knowledge -------------------------------------------------------


class TestListKnowledge:
    @patch("helperai.api.routes.knowledge.get_session_factory")
    def test_returns_entries(self, mock_gsf):
        entry = _make_entry()
        factory, _ = _mock_session_factory([entry])
        mock_gsf.return_value = factory
        manager = MagicMock()

        resp = _client(manager).get("/api/knowledge")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Entry"

    @patch("helperai.api.routes.knowledge.get_session_factory")
    def test_empty_list(self, mock_gsf):
        factory, _ = _mock_session_factory([])
        mock_gsf.return_value = factory
        manager = MagicMock()

        resp = _client(manager).get("/api/knowledge")
        assert resp.status_code == 200
        assert resp.json() == []


# -- POST /api/knowledge ------------------------------------------------------


class TestAddKnowledge:
    @patch("helperai.api.routes.knowledge.get_session_factory")
    def test_create_entry(self, mock_gsf):
        factory, session = _mock_session_factory([])
        mock_gsf.return_value = factory

        # After refresh, the entry should have attributes
        new_entry = _make_entry(id="k-new", title="New", content="Body")

        async def fake_refresh(obj):
            obj.id = new_entry.id
            obj.title = new_entry.title
            obj.content = new_entry.content
            obj.added_by = new_entry.added_by
            obj.created_at = new_entry.created_at
            obj.updated_at = new_entry.updated_at

        session.refresh = AsyncMock(side_effect=fake_refresh)

        manager = MagicMock()
        manager.refresh_knowledge = AsyncMock()

        resp = _client(manager).post(
            "/api/knowledge",
            json={"title": "New", "content": "Body"},
        )
        assert resp.status_code == 200
        manager.refresh_knowledge.assert_awaited_once()


# -- DELETE /api/knowledge/{id} -----------------------------------------------


class TestDeleteKnowledge:
    @patch("helperai.api.routes.knowledge.get_session_factory")
    def test_delete_success(self, mock_gsf):
        entry = _make_entry()
        factory, session = _mock_session_factory([entry])
        mock_gsf.return_value = factory
        manager = MagicMock()
        manager.refresh_knowledge = AsyncMock()

        resp = _client(manager).delete("/api/knowledge/k1")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted"}
        manager.refresh_knowledge.assert_awaited_once()

    @patch("helperai.api.routes.knowledge.get_session_factory")
    def test_delete_not_found(self, mock_gsf):
        factory, _ = _mock_session_factory([])
        mock_gsf.return_value = factory
        manager = MagicMock()
        manager.refresh_knowledge = AsyncMock()

        resp = _client(manager).delete("/api/knowledge/missing")
        assert resp.status_code == 404
