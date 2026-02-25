"""Tests for API request model validators."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from helperai.api.routes.agents import CreateAgentRequest, MessageRequest, UpdateAgentRequest


class TestMessageRequest:
    def test_valid_message(self):
        req = MessageRequest(message="Hello")
        assert req.message == "Hello"

    def test_empty_message_rejected(self):
        with pytest.raises(ValidationError):
            MessageRequest(message="")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError):
            MessageRequest(message="   ")

    def test_long_message_rejected(self):
        with pytest.raises(ValidationError):
            MessageRequest(message="x" * 100_001)

    def test_max_length_message_accepted(self):
        req = MessageRequest(message="x" * 100_000)
        assert len(req.message) == 100_000

    def test_sender_name_optional(self):
        req = MessageRequest(message="hi")
        assert req.sender_name is None

    def test_sender_name_too_long(self):
        with pytest.raises(ValidationError):
            MessageRequest(message="hi", sender_name="x" * 101)

    def test_sender_name_valid(self):
        req = MessageRequest(message="hi", sender_name="Alice")
        assert req.sender_name == "Alice"


class TestCreateAgentRequest:
    def test_valid_minimal(self):
        req = CreateAgentRequest(name="Agent1", role="helper")
        assert req.name == "Agent1"
        assert req.role == "helper"
        assert req.goal == ""

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            CreateAgentRequest(name="", role="x")

    def test_invalid_name_chars_rejected(self):
        with pytest.raises(ValidationError):
            CreateAgentRequest(name="agent@!", role="x")

    def test_valid_name_with_spaces_hyphens(self):
        req = CreateAgentRequest(name="My Agent-1", role="x")
        assert req.name == "My Agent-1"

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            CreateAgentRequest(name="x" * 101, role="x")

    def test_role_too_long(self):
        with pytest.raises(ValidationError):
            CreateAgentRequest(name="Agent", role="x" * 10_001)

    def test_goal_too_long(self):
        with pytest.raises(ValidationError):
            CreateAgentRequest(name="Agent", role="x", goal="x" * 10_001)

    def test_tool_names_validated(self):
        req = CreateAgentRequest(name="Agent", role="x", tool_names=["read_file", "run_command"])
        assert req.tool_names == ["read_file", "run_command"]

    def test_invalid_tool_name(self):
        with pytest.raises(ValidationError):
            CreateAgentRequest(name="Agent", role="x", tool_names=["invalid tool!"])

    def test_too_many_tools(self):
        with pytest.raises(ValidationError):
            CreateAgentRequest(name="Agent", role="x", tool_names=["t"] * 51)

    def test_invalid_provider_name(self):
        with pytest.raises(ValidationError):
            CreateAgentRequest(name="Agent", role="x", provider_name="bad provider!")

    def test_valid_provider_name(self):
        req = CreateAgentRequest(name="Agent", role="x", provider_name="openai")
        assert req.provider_name == "openai"

    def test_invalid_model_name(self):
        with pytest.raises(ValidationError):
            CreateAgentRequest(name="Agent", role="x", model_name="model with spaces")

    def test_valid_model_name(self):
        req = CreateAgentRequest(name="Agent", role="x", model_name="gpt-4:latest")
        assert req.model_name == "gpt-4:latest"


class TestUpdateAgentRequest:
    def test_all_fields_optional(self):
        req = UpdateAgentRequest()
        assert req.name is None
        assert req.role is None
        assert req.goal is None

    def test_partial_update(self):
        req = UpdateAgentRequest(name="NewName")
        assert req.name == "NewName"
        assert req.role is None

    def test_invalid_name(self):
        with pytest.raises(ValidationError):
            UpdateAgentRequest(name="@invalid")

    def test_role_too_long(self):
        with pytest.raises(ValidationError):
            UpdateAgentRequest(role="x" * 10_001)
