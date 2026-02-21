"""Shared test fixtures."""

from __future__ import annotations

import pytest

from helperai.config import Settings
from helperai.core.events import EventBus
from helperai.llm.registry import LLMRegistry
from helperai.tools.registry import ToolRegistry


@pytest.fixture
def settings():
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        default_provider="test",
        default_model="test-model",
        ollama_base_url="",
    )


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def llm_registry():
    return LLMRegistry()


@pytest.fixture
def tool_registry():
    return ToolRegistry()
