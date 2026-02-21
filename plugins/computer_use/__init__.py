"""Computer use plugin — screenshot, mouse, keyboard, and scroll control."""

from __future__ import annotations

import logging

from helperai.plugins.protocol import Plugin
from helperai.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ComputerUsePlugin:
    @property
    def name(self) -> str:
        return "computer_use"

    @property
    def description(self) -> str:
        return "Computer control: screenshot, mouse, keyboard, and scroll"

    def register_tools(self, registry: ToolRegistry) -> None:
        try:
            from .tools import (
                KeyPressTool,
                KeyboardTypeTool,
                MouseClickTool,
                ScreenshotTool,
                ScrollTool,
            )

            registry.register(ScreenshotTool())
            registry.register(MouseClickTool())
            registry.register(KeyboardTypeTool())
            registry.register(KeyPressTool())
            registry.register(ScrollTool())
        except ImportError:
            logger.warning(
                "Computer use dependencies not installed. "
                "Install with: pip install -e '.[computer-use]'"
            )


plugin = ComputerUsePlugin()
