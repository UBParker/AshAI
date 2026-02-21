"""LLM provider registry."""

from __future__ import annotations

from helperai.core.exceptions import ProviderNotFoundError
from helperai.llm.protocol import LLMProvider


class LLMRegistry:
    """Maps provider names to LLMProvider instances."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._default_name: str | None = None

    def register(self, provider: LLMProvider, *, is_default: bool = False) -> None:
        self._providers[provider.name] = provider
        if is_default or self._default_name is None:
            self._default_name = provider.name

    def get(self, name: str) -> LLMProvider:
        if name not in self._providers:
            raise ProviderNotFoundError(name)
        return self._providers[name]

    @property
    def default(self) -> LLMProvider:
        if self._default_name is None:
            raise ProviderNotFoundError("(no default)")
        return self._providers[self._default_name]

    @property
    def default_name(self) -> str | None:
        return self._default_name

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())
