"""Tests for API routes — settings endpoints."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from helperai.api.routes.settings import (
    router,
    _read_env_dict,
    _write_env_dict,
)


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# -- internal helpers ---------------------------------------------------------


class TestReadEnvDict:
    def test_reads_key_value_pairs(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n")
        with patch("helperai.api.routes.settings._env_file_path", return_value=env_file):
            result = _read_env_dict()
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_skips_comments_and_empty_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nKEY=val\n")
        with patch("helperai.api.routes.settings._env_file_path", return_value=env_file):
            result = _read_env_dict()
        assert result == {"KEY": "val"}

    def test_missing_file(self, tmp_path):
        env_file = tmp_path / ".env"
        with patch("helperai.api.routes.settings._env_file_path", return_value=env_file):
            result = _read_env_dict()
        assert result == {}


class TestWriteEnvDict:
    def test_writes_sorted_keys(self, tmp_path):
        env_file = tmp_path / ".env"
        with patch("helperai.api.routes.settings._env_file_path", return_value=env_file):
            _write_env_dict({"ZZZ": "1", "AAA": "2"})
        content = env_file.read_text()
        lines = content.strip().split("\n")
        assert lines[0] == "AAA=2"
        assert lines[1] == "ZZZ=1"


# -- endpoint tests -----------------------------------------------------------


class TestGetSettings:
    def test_returns_masked_keys(self, client):
        mock_settings = MagicMock()
        mock_settings.default_provider = "anthropic"
        mock_settings.default_model = "claude-3"
        mock_settings.anthropic_api_key.get_secret_value.return_value = "sk-ant-xxx"
        mock_settings.openai_api_key.get_secret_value.return_value = ""
        mock_settings.gemini_api_key.get_secret_value.return_value = ""
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.eve_name = "Eve"

        with (
            patch("helperai.api.routes.settings.get_settings", return_value=mock_settings),
            patch("helperai.api.routes.settings._read_env_dict", return_value={}),
            patch("helperai.api.routes.settings._env_file_path", return_value=Path("/tmp/.env")),
        ):
            resp = client.get("/api/settings")

        assert resp.status_code == 200
        data = resp.json()
        assert data["has_anthropic_key"] is True
        assert data["has_openai_key"] is False
        assert data["has_any_key"] is True
        assert data["default_provider"] == "anthropic"


class TestPutSettings:
    def test_writes_env_and_updates_os_env(self, client, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("")

        with (
            patch("helperai.api.routes.settings._env_file_path", return_value=env_file),
            patch("helperai.api.routes.settings._read_env_dict", return_value={}),
            patch("helperai.api.routes.settings._write_env_dict") as mock_write,
        ):
            resp = client.put("/api/settings", json={"default_provider": "openai"})

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        mock_write.assert_called_once()
        # Verify the key was uppercased and prefixed
        written_data = mock_write.call_args[0][0]
        assert "HELPERAI_DEFAULT_PROVIDER" in written_data

    def test_already_prefixed_keys_not_double_prefixed(self, client, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("")

        with (
            patch("helperai.api.routes.settings._env_file_path", return_value=env_file),
            patch("helperai.api.routes.settings._read_env_dict", return_value={}),
            patch("helperai.api.routes.settings._write_env_dict") as mock_write,
        ):
            resp = client.put("/api/settings", json={"HELPERAI_FOO": "bar"})

        assert resp.status_code == 200
        written_data = mock_write.call_args[0][0]
        assert "HELPERAI_FOO" in written_data
        assert "HELPERAI_HELPERAI_FOO" not in written_data


class TestClaudeCliCheck:
    def test_available(self, client):
        with patch("helperai.api.routes.settings.shutil.which", return_value="/usr/bin/claude"):
            resp = client.get("/api/settings/claude-cli")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["path"] == "/usr/bin/claude"

    def test_not_available(self, client):
        with patch("helperai.api.routes.settings.shutil.which", return_value=None):
            resp = client.get("/api/settings/claude-cli")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["path"] is None
