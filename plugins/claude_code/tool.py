"""ClaudeCodeTool — runs Claude Code CLI for coding tasks."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from helperai.llm.message_types import ToolDefinition
from helperai.tools.protocol import ToolContext

CLAUDE_CODE_TIMEOUT = 300  # 5 minutes


class ClaudeCodeTool:
    """Delegate coding tasks to the Claude Code CLI."""

    requires_approval = True

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="claude_code",
            description=(
                "Delegate a coding task to Claude Code CLI. Claude Code can create files, "
                "edit code, run commands, and perform complex coding tasks autonomously. "
                "Requires user approval before execution."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Description of the coding task to perform",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory for the task (optional)",
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context or file contents to provide (optional)",
                    },
                },
                "required": ["task"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        task = arguments["task"]
        cwd = arguments.get("working_directory") or None
        context = arguments.get("context", "")

        prompt = task
        if context:
            prompt = f"{context}\n\n{task}"

        try:
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "--print",
                "--output-format",
                "text",
                "-p",
                prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=CLAUDE_CODE_TIMEOUT
            )

            result: dict[str, Any] = {
                "output": stdout.decode(errors="replace"),
                "returncode": proc.returncode,
            }
            if stderr:
                stderr_text = stderr.decode(errors="replace").strip()
                if stderr_text:
                    result["stderr"] = stderr_text

            return json.dumps(result)

        except asyncio.TimeoutError:
            proc.kill()
            return json.dumps(
                {"error": f"Claude Code timed out after {CLAUDE_CODE_TIMEOUT}s"}
            )
        except FileNotFoundError:
            return json.dumps(
                {
                    "error": "Claude Code CLI not found. Make sure 'claude' is installed and on PATH."
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e)})
