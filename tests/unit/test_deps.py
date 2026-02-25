"""Tests for API dependency injection module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from helperai.api import deps


def _reset_deps():
    """Reset all module-level globals to None."""
    deps._agent_manager = None
    deps._event_bus = None
    deps._llm_registry = None
    deps._tool_registry = None
    deps._approval_manager = None


def test_set_services():
    _reset_deps()
    am = MagicMock()
    eb = MagicMock()
    lr = MagicMock()
    tr = MagicMock()
    ap = MagicMock()

    deps.set_services(am, eb, lr, tr, ap)

    assert deps.get_agent_manager() is am
    assert deps.get_event_bus() is eb
    assert deps.get_llm_registry() is lr
    assert deps.get_tool_registry() is tr
    assert deps.get_approval_manager() is ap


def test_set_services_without_approval():
    _reset_deps()
    am = MagicMock()
    eb = MagicMock()
    lr = MagicMock()
    tr = MagicMock()

    deps.set_services(am, eb, lr, tr)

    assert deps.get_agent_manager() is am
    with pytest.raises(RuntimeError):
        deps.get_approval_manager()


def test_get_agent_manager_uninitialized():
    _reset_deps()
    with pytest.raises(RuntimeError, match="AgentManager not initialized"):
        deps.get_agent_manager()


def test_get_event_bus_uninitialized():
    _reset_deps()
    with pytest.raises(RuntimeError, match="EventBus not initialized"):
        deps.get_event_bus()


def test_get_llm_registry_uninitialized():
    _reset_deps()
    with pytest.raises(RuntimeError, match="LLMRegistry not initialized"):
        deps.get_llm_registry()


def test_get_tool_registry_uninitialized():
    _reset_deps()
    with pytest.raises(RuntimeError, match="ToolRegistry not initialized"):
        deps.get_tool_registry()


def test_get_approval_manager_uninitialized():
    _reset_deps()
    with pytest.raises(RuntimeError, match="ApprovalManager not initialized"):
        deps.get_approval_manager()
