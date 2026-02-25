"""Tests for the exception hierarchy."""

from helperai.core.exceptions import (
    AgentNotFoundError,
    HelperAIError,
    InvalidTransitionError,
    LLMError,
    ProviderNotFoundError,
    ToolExecutionError,
    ToolNotFoundError,
)


def test_all_exceptions_inherit_base():
    for exc_cls in [
        InvalidTransitionError,
        AgentNotFoundError,
        ProviderNotFoundError,
        ToolNotFoundError,
        ToolExecutionError,
        LLMError,
    ]:
        assert issubclass(exc_cls, HelperAIError)


def test_invalid_transition_error():
    e = InvalidTransitionError("created", "completed")
    assert e.from_status == "created"
    assert e.to_status == "completed"
    assert "created" in str(e)
    assert "completed" in str(e)


def test_agent_not_found_error():
    e = AgentNotFoundError("abc-123")
    assert e.agent_id == "abc-123"
    assert "abc-123" in str(e)


def test_provider_not_found_error():
    e = ProviderNotFoundError("openai")
    assert e.name == "openai"
    assert "openai" in str(e)


def test_tool_not_found_error():
    e = ToolNotFoundError("my_tool")
    assert e.name == "my_tool"
    assert "my_tool" in str(e)
