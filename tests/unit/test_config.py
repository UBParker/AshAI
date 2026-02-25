"""Tests for config module."""

from helperai.config import Settings


def test_default_settings(monkeypatch, tmp_path):
    import os

    for k in list(os.environ):
        if k.startswith("HELPERAI_"):
            monkeypatch.delenv(k, raising=False)

    # Change to a temp dir so pydantic-settings won't read .env from workspace
    monkeypatch.chdir(tmp_path)

    s = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        ollama_base_url="",
    )
    assert s.host == "127.0.0.1"
    assert s.port == 8000
    assert s.default_provider == "ollama"
    assert s.eve_name == "Ash"
    assert s.log_level == "info"


def test_custom_settings():
    s = Settings(
        host="0.0.0.0",
        port=9000,
        default_provider="openai",
        default_model="gpt-4",
        eve_name="Alice",
        database_url="sqlite+aiosqlite:///:memory:",
        ollama_base_url="",
    )
    assert s.host == "0.0.0.0"
    assert s.port == 9000
    assert s.default_provider == "openai"
    assert s.default_model == "gpt-4"
    assert s.eve_name == "Alice"
