"""System tools — run_command, read_file, write_file, list_directory, search_files."""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from helperai.llm.message_types import ToolDefinition
from helperai.tools.protocol import ToolContext

MAX_FILE_SIZE = 50 * 1024  # 50KB safety limit
COMMAND_TIMEOUT = 30  # seconds
MAX_SEARCH_RESULTS = 100


class RunCommandTool:
    """Execute a shell command with approval."""

    requires_approval = True

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="run_command",
            description="Execute a shell command and return stdout, stderr, and return code. Requires user approval.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory for the command (optional, defaults to cwd)",
                    },
                },
                "required": ["command"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        command = arguments["command"]
        cwd = arguments.get("working_directory") or None

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=COMMAND_TIMEOUT
            )
            return json.dumps(
                {
                    "stdout": stdout.decode(errors="replace"),
                    "stderr": stderr.decode(errors="replace"),
                    "returncode": proc.returncode,
                }
            )
        except asyncio.TimeoutError:
            proc.kill()
            return json.dumps({"error": f"Command timed out after {COMMAND_TIMEOUT}s"})
        except Exception as e:
            return json.dumps({"error": str(e)})


class ReadFileTool:
    """Read file contents."""

    requires_approval = False

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_file",
            description="Read the contents of a file. Supports optional line range. Max 50KB.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative path to the file",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "First line to read (1-based, optional)",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Last line to read (inclusive, optional)",
                    },
                },
                "required": ["path"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        path = Path(arguments["path"]).expanduser().resolve()

        if not path.exists():
            return json.dumps({"error": f"File not found: {path}"})
        if not path.is_file():
            return json.dumps({"error": f"Not a file: {path}"})
        if path.stat().st_size > MAX_FILE_SIZE:
            return json.dumps(
                {"error": f"File too large ({path.stat().st_size} bytes). Max {MAX_FILE_SIZE}."}
            )

        try:
            content = path.read_text(errors="replace")
        except Exception as e:
            return json.dumps({"error": str(e)})

        start = arguments.get("start_line")
        end = arguments.get("end_line")
        if start or end:
            lines = content.splitlines(keepends=True)
            s = (start or 1) - 1
            e = end or len(lines)
            content = "".join(lines[s:e])

        return json.dumps({"path": str(path), "content": content})


class WriteFileTool:
    """Write content to a file. Requires approval."""

    requires_approval = True

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write_file",
            description="Write or append content to a file. Creates parent directories if needed. Requires user approval.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative path to the file",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write",
                    },
                    "append": {
                        "type": "boolean",
                        "description": "If true, append instead of overwrite (default false)",
                    },
                },
                "required": ["path", "content"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        path = Path(arguments["path"]).expanduser().resolve()
        content = arguments["content"]
        append = arguments.get("append", False)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            path.write_text(content) if not append else path.open(mode).write(content)
            return json.dumps(
                {"path": str(path), "bytes_written": len(content.encode()), "mode": mode}
            )
        except Exception as e:
            return json.dumps({"error": str(e)})


class ListDirectoryTool:
    """List directory contents."""

    requires_approval = False

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_directory",
            description="List files and directories in a given path with name, type, size, and modification time.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (defaults to current directory)",
                    },
                },
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        path = Path(arguments.get("path", ".")).expanduser().resolve()

        if not path.exists():
            return json.dumps({"error": f"Path not found: {path}"})
        if not path.is_dir():
            return json.dumps({"error": f"Not a directory: {path}"})

        entries = []
        try:
            for entry in sorted(path.iterdir()):
                stat = entry.stat()
                entries.append(
                    {
                        "name": entry.name,
                        "type": "directory" if entry.is_dir() else "file",
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat(),
                    }
                )
        except PermissionError:
            return json.dumps({"error": f"Permission denied: {path}"})

        return json.dumps({"path": str(path), "entries": entries})


class SearchFilesTool:
    """Search for a regex pattern in files."""

    requires_approval = False

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_files",
            description="Search for a regex pattern in files within a directory. Returns matching lines (max 100 results).",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search in (defaults to current directory)",
                    },
                    "glob": {
                        "type": "string",
                        "description": "File glob pattern to filter files (e.g. '*.py')",
                    },
                },
                "required": ["pattern"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        pattern_str = arguments["pattern"]
        search_path = Path(arguments.get("path", ".")).expanduser().resolve()
        file_glob = arguments.get("glob", "*")

        try:
            regex = re.compile(pattern_str)
        except re.error as e:
            return json.dumps({"error": f"Invalid regex: {e}"})

        if not search_path.exists():
            return json.dumps({"error": f"Path not found: {search_path}"})

        results = []
        for fpath in search_path.rglob(file_glob):
            if not fpath.is_file():
                continue
            if fpath.stat().st_size > MAX_FILE_SIZE:
                continue
            try:
                text = fpath.read_text(errors="replace")
                for lineno, line in enumerate(text.splitlines(), 1):
                    if regex.search(line):
                        results.append(
                            {
                                "file": str(fpath),
                                "line": lineno,
                                "text": line.rstrip(),
                            }
                        )
                        if len(results) >= MAX_SEARCH_RESULTS:
                            return json.dumps(
                                {
                                    "results": results,
                                    "truncated": True,
                                    "message": f"Stopped at {MAX_SEARCH_RESULTS} matches",
                                }
                            )
            except (PermissionError, UnicodeDecodeError):
                continue

        return json.dumps({"results": results, "total": len(results)})
