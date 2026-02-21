"""Tests for config module."""

from helperai.config import Settings


def test_default_settings():
    s = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        ollama_base_url="",
    )
    assert s.host == "127.0.0.1"
    assert s.port == 8000
    assert s.default_provider == "ollama"
    assert s.eve_name == "Eve"
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
