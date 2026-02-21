"""Plugin protocol."""

from __future__ import annotations

from typing import Protocol

from helperai.tools.registry import ToolRegistry


class Plugin(Protocol):
    """Interface for helperAI plugins."""

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    def register_tools(self, registry: ToolRegistry) -> None:
        """Register the plugin's tools into the global tool registry."""
        ...
