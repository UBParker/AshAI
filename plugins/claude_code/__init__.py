"""Claude Code CLI plugin — delegates coding tasks to the Claude Code CLI."""

from __future__ import annotations

from helperai.plugins.protocol import Plugin
from helperai.tools.registry import ToolRegistry

from .tool import ClaudeCodeTool


class ClaudeCodePlugin:
    @property
    def name(self) -> str:
        return "claude_code"

    @property
    def description(self) -> str:
        return "Delegate coding tasks to Claude Code CLI"

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(ClaudeCodeTool())


plugin = ClaudeCodePlugin()
