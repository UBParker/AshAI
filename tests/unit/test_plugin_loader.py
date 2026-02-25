"""Tests for plugin discovery and loading."""

from __future__ import annotations

import types

from helperai.llm.message_types import ToolDefinition
from helperai.plugins.loader import load_plugins
from helperai.tools.registry import ToolRegistry


class _FakeTool:
    def __init__(self, name: str):
        self._name = name

    @property
    def definition(self):
        return ToolDefinition(name=self._name, description="fake")

    async def execute(self, arguments, ctx):
        return "ok"


class _FakePlugin:
    @property
    def name(self):
        return "test_plugin"

    @property
    def description(self):
        return "A test plugin"

    def register_tools(self, registry: ToolRegistry):
        registry.register(_FakeTool("plugin_tool_a"))
        registry.register(_FakeTool("plugin_tool_b"))


def test_load_plugins_nonexistent_dir():
    """load_plugins should silently skip if directory does not exist."""
    registry = ToolRegistry()
    load_plugins("/__does_not_exist_xyz__", registry)
    assert registry.list_tools() == []


def test_load_plugins_empty_dir(tmp_path):
    """load_plugins should handle an empty directory."""
    registry = ToolRegistry()
    load_plugins(str(tmp_path), registry)
    assert registry.list_tools() == []


def test_load_plugins_skips_files(tmp_path):
    """load_plugins should skip non-directory entries."""
    (tmp_path / "not_a_plugin.py").write_text("x = 1")
    registry = ToolRegistry()
    load_plugins(str(tmp_path), registry)
    assert registry.list_tools() == []


def test_load_plugins_skips_dirs_without_init(tmp_path):
    """load_plugins should skip directories without __init__.py."""
    (tmp_path / "noinit").mkdir()
    registry = ToolRegistry()
    load_plugins(str(tmp_path), registry)
    assert registry.list_tools() == []


def test_load_plugins_skips_plugin_without_attribute(tmp_path):
    """load_plugins should skip plugins without a 'plugin' attribute."""
    pkg = tmp_path / "no_attr_plugin"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("x = 42\n")
    registry = ToolRegistry()
    load_plugins(str(tmp_path), registry)
    assert registry.list_tools() == []


def test_load_plugins_loads_valid_plugin(tmp_path):
    """load_plugins should discover and load a valid plugin."""
    pkg = tmp_path / "my_plugin"
    pkg.mkdir()

    init_code = '''
from helperai.llm.message_types import ToolDefinition
from helperai.tools.registry import ToolRegistry

class _Tool:
    def __init__(self, name):
        self._name = name

    @property
    def definition(self):
        return ToolDefinition(name=self._name, description="from plugin")

    async def execute(self, arguments, ctx):
        return "ok"

class _Plugin:
    @property
    def name(self):
        return "my_plugin"

    @property
    def description(self):
        return "My test plugin"

    def register_tools(self, registry):
        registry.register(_Tool("my_plugin_tool"))

plugin = _Plugin()
'''
    (pkg / "__init__.py").write_text(init_code)

    registry = ToolRegistry()
    load_plugins(str(tmp_path), registry)
    assert "my_plugin_tool" in registry.list_tools()


def test_load_plugins_handles_broken_plugin(tmp_path):
    """load_plugins should not crash if a plugin raises on import."""
    pkg = tmp_path / "broken_plugin"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("raise RuntimeError('boom')\n")

    registry = ToolRegistry()
    # Should not raise
    load_plugins(str(tmp_path), registry)
    assert registry.list_tools() == []
