"""LLM provider protocol."""

from __future__ import annotations

from typing import AsyncIterator, Protocol

from helperai.llm.message_types import Message, StreamChunk, ToolDefinition


class LLMProvider(Protocol):
    """Interface that all LLM providers must implement."""

    @property
    def name(self) -> str: ...

    async def stream(
        self,
        messages: list[Message],
        model: str,
        *,
        temperature: float = 0.7,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion. Yields StreamChunk objects."""
        ...

    async def list_models(self) -> list[str]:
        """Return available model names."""
        ...
