"""Extended tests for LLM registry — covers default_name and no-default edge case."""

import pytest

from helperai.core.exceptions import ProviderNotFoundError
from helperai.llm.registry import LLMRegistry


class FakeProvider:
    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

    async def stream(self, messages, model, **kwargs):
        yield  # pragma: no cover

    async def list_models(self):
        return []  # pragma: no cover


def test_default_name_property():
    reg = LLMRegistry()
    assert reg.default_name is None
    p = FakeProvider("test")
    reg.register(p)
    assert reg.default_name == "test"


def test_default_raises_when_no_providers():
    reg = LLMRegistry()
    with pytest.raises(ProviderNotFoundError):
        _ = reg.default


def test_register_multiple_defaults():
    """Last provider registered as default should win."""
    reg = LLMRegistry()
    reg.register(FakeProvider("a"), is_default=True)
    reg.register(FakeProvider("b"), is_default=True)
    assert reg.default.name == "b"


def test_register_without_default_keeps_first():
    """Registering without is_default should not change the default."""
    reg = LLMRegistry()
    reg.register(FakeProvider("first"))
    reg.register(FakeProvider("second"))
    assert reg.default.name == "first"
