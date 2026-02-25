"""Tests for Eve constants."""

from __future__ import annotations

from helperai.agents.eve import EVE_SYSTEM_PROMPT, EVE_TOOL_NAMES


def test_eve_system_prompt_is_nonempty():
    assert isinstance(EVE_SYSTEM_PROMPT, str)
    assert len(EVE_SYSTEM_PROMPT) > 100


def test_eve_system_prompt_mentions_ash():
    assert "Ash" in EVE_SYSTEM_PROMPT


def test_eve_tool_names():
    assert "spawn_agent" in EVE_TOOL_NAMES
    assert "list_agents" in EVE_TOOL_NAMES
    assert "message_agent" in EVE_TOOL_NAMES
    assert len(EVE_TOOL_NAMES) == 3


def test_eve_prompt_describes_tools():
    for tool in EVE_TOOL_NAMES:
        assert tool in EVE_SYSTEM_PROMPT, f"{tool} not mentioned in EVE_SYSTEM_PROMPT"
