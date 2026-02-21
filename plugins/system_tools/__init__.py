"""System tools plugin — shell, files, and directory operations."""

from __future__ import annotations

from helperai.plugins.protocol import Plugin
from helperai.tools.registry import ToolRegistry

from .tools import (
    ListDirectoryTool,
    ReadFileTool,
    RunCommandTool,
    SearchFilesTool,
    WriteFileTool,
)


class SystemToolsPlugin:
    @property
    def name(self) -> str:
        return "system_tools"

    @property
    def description(self) -> str:
        return "Shell commands, file read/write, directory listing, and file search"

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(RunCommandTool())
        registry.register(ReadFileTool())
        registry.register(WriteFileTool())
        registry.register(ListDirectoryTool())
        registry.register(SearchFilesTool())


plugin = SystemToolsPlugin()
