"""Progress reporting tools - non-blocking status updates that stream to frontend."""

from __future__ import annotations

import json
from typing import Any
from datetime import datetime

from helperai.llm.message_types import ToolDefinition
from helperai.tools.protocol import ToolContext


class ReportProgressTool:
    """Send progress updates without blocking - streams to frontend via SSE."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="report_progress",
            description=(
                "Send a progress update that immediately streams to the frontend. "
                "Use this to report ongoing status without stopping your work. "
                "Updates appear in real-time for the user."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The progress message to report",
                    },
                    "percent": {
                        "type": "integer",
                        "description": "Optional completion percentage (0-100)",
                        "minimum": 0,
                        "maximum": 100,
                    },
                    "status": {
                        "type": "string",
                        "description": "Status type: in_progress, completed, warning, error",
                        "enum": ["in_progress", "completed", "warning", "error"],
                        "default": "in_progress",
                    },
                },
                "required": ["message"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        message = arguments["message"]
        percent = arguments.get("percent")
        status = arguments.get("status", "in_progress")

        # Get agent info
        agent = await ctx.agent_manager.get_agent(ctx.agent_id)
        agent_name = agent.name if agent else "Unknown"

        # Create progress event
        progress_data = {
            "type": "progress",
            "agent_id": ctx.agent_id,
            "agent_name": agent_name,
            "message": message,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }

        if percent is not None:
            progress_data["percent"] = max(0, min(100, percent))

        # Stream through SSE by adding to agent's event stream
        # This gets picked up by the SSE endpoint automatically
        await ctx.agent_manager.add_agent_event(ctx.agent_id, "progress", progress_data)

        # Also add to message thread for persistence
        # Format as a special system message so it shows differently
        formatted_msg = f"[PROGRESS] {message}"
        if percent is not None:
            formatted_msg += f" ({percent}%)"

        await ctx.agent_manager.add_message(
            ctx.agent_id,
            role="system",
            content=formatted_msg,
            metadata=progress_data
        )

        return json.dumps({
            "status": "reported",
            "message": message,
            "streaming": True
        })


class ReportMilestoneTool:
    """Report reaching a major milestone - streams to frontend."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="report_milestone",
            description=(
                "Report reaching a major milestone in your task. "
                "This immediately streams to the user with a milestone indicator."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "milestone": {
                        "type": "string",
                        "description": "Name/description of the milestone reached",
                    },
                    "details": {
                        "type": "string",
                        "description": "Optional additional details about the milestone",
                    },
                    "percent_complete": {
                        "type": "integer",
                        "description": "Overall task completion percentage",
                        "minimum": 0,
                        "maximum": 100,
                    },
                },
                "required": ["milestone"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        milestone = arguments["milestone"]
        details = arguments.get("details", "")
        percent = arguments.get("percent_complete")

        message = f"🎯 Milestone: {milestone}"
        if details:
            message += f" - {details}"

        # Use the progress tool to report
        progress_tool = ReportProgressTool()
        progress_args = {
            "message": message,
            "status": "in_progress"
        }
        if percent is not None:
            progress_args["percent"] = percent

        return await progress_tool.execute(progress_args, ctx)


class ReportStepTool:
    """Report step-by-step progress - streams to frontend."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="report_step",
            description=(
                "Report completion of a step in a multi-step process. "
                "Automatically calculates and shows percentage complete."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "step": {
                        "type": "integer",
                        "description": "Current step number",
                        "minimum": 1,
                    },
                    "total_steps": {
                        "type": "integer",
                        "description": "Total number of steps",
                        "minimum": 1,
                    },
                    "description": {
                        "type": "string",
                        "description": "What this step does",
                    },
                },
                "required": ["step", "total_steps", "description"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        step = arguments["step"]
        total = arguments["total_steps"]
        description = arguments["description"]

        percent = int((step / total) * 100) if total > 0 else 0
        message = f"Step {step}/{total}: {description}"

        # Use progress tool
        progress_tool = ReportProgressTool()
        return await progress_tool.execute({
            "message": message,
            "percent": percent,
            "status": "in_progress"
        }, ctx)


class ReportFindingTool:
    """Report discoveries and findings - streams to frontend."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="report_finding",
            description=(
                "Report an important finding or discovery during your exploration. "
                "This immediately alerts the user with appropriate importance level."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "finding": {
                        "type": "string",
                        "description": "Description of what was found",
                    },
                    "importance": {
                        "type": "string",
                        "description": "Importance level",
                        "enum": ["info", "warning", "critical"],
                        "default": "info",
                    },
                    "details": {
                        "type": "object",
                        "description": "Optional additional details as key-value pairs",
                    },
                },
                "required": ["finding"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        finding = arguments["finding"]
        importance = arguments.get("importance", "info")
        details = arguments.get("details")

        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🚨"
        }

        icon = icons.get(importance, "📌")
        message = f"{icon} Finding: {finding}"

        if details:
            detail_str = ", ".join(f"{k}: {v}" for k, v in details.items())
            message += f" [{detail_str}]"

        status = "warning" if importance in ["warning", "critical"] else "in_progress"

        # Use progress tool
        progress_tool = ReportProgressTool()
        return await progress_tool.execute({
            "message": message,
            "status": status
        }, ctx)


class ReportMetricsTool:
    """Report metrics and measurements - streams to frontend."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="report_metrics",
            description=(
                "Report numerical metrics, statistics, or measurements. "
                "These stream to the frontend with proper formatting."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "metrics": {
                        "type": "object",
                        "description": "Dictionary of metric names and values",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description of what these metrics represent",
                    },
                    "category": {
                        "type": "string",
                        "description": "Category of metrics (performance, resource, analysis, etc.)",
                    },
                },
                "required": ["metrics"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        metrics = arguments["metrics"]
        description = arguments.get("description", "Metrics update")
        category = arguments.get("category", "general")

        # Format metrics for display
        metric_lines = []
        for key, value in list(metrics.items())[:5]:  # Show first 5
            if isinstance(value, (int, float)):
                formatted = f"{value:.2f}" if isinstance(value, float) else str(value)
                metric_lines.append(f"{key}: {formatted}")
            else:
                metric_lines.append(f"{key}: {value}")

        message = f"📊 {description} - {', '.join(metric_lines)}"
        if len(metrics) > 5:
            message += f" (+{len(metrics)-5} more)"

        # Use progress tool
        progress_tool = ReportProgressTool()
        return await progress_tool.execute({
            "message": message,
            "status": "in_progress"
        }, ctx)