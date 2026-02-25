"""Tests for API routes — approvals endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from helperai.api.routes.approvals import router


# -- helpers ------------------------------------------------------------------


def _make_app(approval_mock: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[
        __import__("helperai.api.deps", fromlist=["get_approval_manager"]).get_approval_manager
    ] = lambda: approval_mock
    return app


def _client(approval_mock: MagicMock) -> TestClient:
    return TestClient(_make_app(approval_mock))


# -- GET /api/approvals -------------------------------------------------------


class TestListPending:
    def test_returns_pending_approvals(self):
        mock = MagicMock()
        mock.list_pending = AsyncMock(return_value=[
            {"id": "a1", "agent_id": "ag1", "tool_name": "run_command", "arguments": {"cmd": "ls"}, "created_at": None},
        ])
        resp = _client(mock).get("/api/approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "a1"
        assert data[0]["tool_name"] == "run_command"

    def test_returns_empty_list(self):
        mock = MagicMock()
        mock.list_pending = AsyncMock(return_value=[])
        resp = _client(mock).get("/api/approvals")
        assert resp.status_code == 200
        assert resp.json() == []


# -- POST /api/approvals/{id}/approve ----------------------------------------


class TestApprove:
    def test_approve_success(self):
        mock = MagicMock()
        mock.resolve = AsyncMock(return_value=None)
        resp = _client(mock).post("/api/approvals/a1/approve")
        assert resp.status_code == 200
        assert resp.json() == {"status": "approved"}
        mock.resolve.assert_awaited_once_with("a1", approved=True)

    def test_approve_not_found(self):
        mock = MagicMock()
        mock.resolve = AsyncMock(side_effect=ValueError("No pending approval with id a1"))
        resp = _client(mock).post("/api/approvals/a1/approve")
        assert resp.status_code == 404


# -- POST /api/approvals/{id}/deny -------------------------------------------


class TestDeny:
    def test_deny_success(self):
        mock = MagicMock()
        mock.resolve = AsyncMock(return_value=None)
        resp = _client(mock).post("/api/approvals/a1/deny")
        assert resp.status_code == 200
        assert resp.json() == {"status": "denied"}
        mock.resolve.assert_awaited_once_with("a1", approved=False)

    def test_deny_not_found(self):
        mock = MagicMock()
        mock.resolve = AsyncMock(side_effect=ValueError("No pending approval with id a1"))
        resp = _client(mock).post("/api/approvals/a1/deny")
        assert resp.status_code == 404
