"""Plugin discovery and loading."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

from helperai.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def load_plugins(plugins_dir: str, tool_registry: ToolRegistry) -> None:
    """Discover and load plugins from the plugins directory.

    Each plugin is a Python package with an __init__.py that exposes a `plugin` attribute
    conforming to the Plugin protocol.
    """
    plugins_path = Path(plugins_dir)
    if not plugins_path.exists():
        logger.debug("Plugins directory does not exist: %s", plugins_dir)
        return

    import sys

    # Add plugins dir to path so we can import them
    plugins_str = str(plugins_path.resolve())
    if plugins_str not in sys.path:
        sys.path.insert(0, plugins_str)

    for child in sorted(plugins_path.iterdir()):
        if not child.is_dir():
            continue
        init_file = child / "__init__.py"
        if not init_file.exists():
            continue

        plugin_name = child.name
        try:
            module = importlib.import_module(plugin_name)
            plugin = getattr(module, "plugin", None)
            if plugin is None:
                logger.warning("Plugin %s has no 'plugin' attribute, skipping", plugin_name)
                continue

            plugin.register_tools(tool_registry)
            logger.info("Loaded plugin: %s — %s", plugin.name, plugin.description)
        except Exception:
            logger.exception("Failed to load plugin: %s", plugin_name)
