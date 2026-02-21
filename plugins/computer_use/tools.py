"""Computer use tools — screenshot, mouse, keyboard, scroll."""

from __future__ import annotations

import base64
import io
import json
from typing import Any

import pyautogui
from PIL import ImageGrab

from helperai.llm.message_types import ToolDefinition
from helperai.tools.protocol import ToolContext

# Disable pyautogui failsafe (mouse to corner) — we have our own approval system
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1


class ScreenshotTool:
    """Capture a screenshot of the entire screen."""

    requires_approval = True

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="screenshot",
            description="Capture a screenshot of the entire screen. Returns a base64-encoded PNG image.",
            parameters={"type": "object", "properties": {}},
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        try:
            img = ImageGrab.grab()
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            return json.dumps(
                {
                    "image_base64": b64,
                    "width": img.width,
                    "height": img.height,
                    "format": "png",
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e)})


class MouseClickTool:
    """Click the mouse at a specific screen position."""

    requires_approval = True

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="mouse_click",
            description="Click the mouse at a specific x, y screen position. Supports left, right, and middle buttons.",
            parameters={
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate on screen"},
                    "y": {"type": "integer", "description": "Y coordinate on screen"},
                    "button": {
                        "type": "string",
                        "enum": ["left", "right", "middle"],
                        "description": "Mouse button (default: left)",
                    },
                },
                "required": ["x", "y"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        x = arguments["x"]
        y = arguments["y"]
        button = arguments.get("button", "left")
        try:
            pyautogui.click(x, y, button=button)
            return json.dumps({"status": "clicked", "x": x, "y": y, "button": button})
        except Exception as e:
            return json.dumps({"error": str(e)})


class KeyboardTypeTool:
    """Type text using the keyboard."""

    requires_approval = True

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="keyboard_type",
            description="Type text using the keyboard. Optionally press Enter after typing.",
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to type",
                    },
                    "press_enter": {
                        "type": "boolean",
                        "description": "Press Enter after typing (default: false)",
                    },
                },
                "required": ["text"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        text = arguments["text"]
        press_enter = arguments.get("press_enter", False)
        try:
            pyautogui.typewrite(text, interval=0.02) if text.isascii() else pyautogui.write(text)
            if press_enter:
                pyautogui.press("enter")
            return json.dumps(
                {"status": "typed", "length": len(text), "enter": press_enter}
            )
        except Exception as e:
            return json.dumps({"error": str(e)})


class KeyPressTool:
    """Press keyboard keys (hotkeys/shortcuts)."""

    requires_approval = True

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="key_press",
            description='Press one or more keyboard keys simultaneously. E.g. ["ctrl", "c"] for copy.',
            parameters={
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": 'List of keys to press, e.g. ["ctrl", "c"]',
                    },
                },
                "required": ["keys"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        keys = arguments["keys"]
        try:
            pyautogui.hotkey(*keys)
            return json.dumps({"status": "pressed", "keys": keys})
        except Exception as e:
            return json.dumps({"error": str(e)})


class ScrollTool:
    """Scroll the mouse wheel at a position."""

    requires_approval = True

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="scroll",
            description="Scroll the mouse wheel at a specific screen position.",
            parameters={
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate on screen"},
                    "y": {"type": "integer", "description": "Y coordinate on screen"},
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down"],
                        "description": "Scroll direction",
                    },
                    "clicks": {
                        "type": "integer",
                        "description": "Number of scroll clicks (default: 3)",
                    },
                },
                "required": ["x", "y", "direction"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        x = arguments["x"]
        y = arguments["y"]
        direction = arguments["direction"]
        clicks = arguments.get("clicks", 3)
        amount = clicks if direction == "up" else -clicks
        try:
            pyautogui.scroll(amount, x=x, y=y)
            return json.dumps(
                {"status": "scrolled", "x": x, "y": y, "direction": direction, "clicks": clicks}
            )
        except Exception as e:
            return json.dumps({"error": str(e)})
