"""Tests for LLM registry."""

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


def test_register_and_get():
    reg = LLMRegistry()
    p = FakeProvider("test")
    reg.register(p)
    assert reg.get("test") is p


def test_default_provider():
    reg = LLMRegistry()
    p1 = FakeProvider("a")
    p2 = FakeProvider("b")
    reg.register(p1)
    reg.register(p2, is_default=True)
    assert reg.default is p2


def test_first_registered_is_default():
    reg = LLMRegistry()
    p = FakeProvider("first")
    reg.register(p)
    assert reg.default is p


def test_get_not_found():
    reg = LLMRegistry()
    with pytest.raises(ProviderNotFoundError):
        reg.get("missing")


def test_list_providers():
    reg = LLMRegistry()
    reg.register(FakeProvider("x"))
    reg.register(FakeProvider("y"))
    assert sorted(reg.list_providers()) == ["x", "y"]
