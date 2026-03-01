"""
Progress Reporting Plugin for AshAI
Provides non-blocking progress reporting for agents
"""

from typing import Dict, Any, Optional, List
import json
from datetime import datetime
from pathlib import Path
import hashlib


class ReportProgressTool:
    """Tool for reporting progress without stopping execution"""

    name = "report_progress"
    description = "Report progress to user without stopping - for ongoing status updates"

    async def execute(
        self,
        agent_id: str,
        message: str,
        status: str = "in_progress",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a progress report without stopping execution.

        Args:
            agent_id: ID of the reporting agent
            message: Progress message to report
            status: Status type (in_progress, completed, warning, error)
            metadata: Optional metadata dictionary

        Returns:
            Confirmation that report was sent
        """
        timestamp = datetime.now().isoformat()
        report_id = hashlib.md5(f"{timestamp}{agent_id}{message}".encode()).hexdigest()[:8]

        progress_report = {
            "id": report_id,
            "type": "progress_report",
            "agent_id": agent_id,
            "timestamp": timestamp,
            "status": status,
            "message": message,
            "metadata": metadata or {}
        }

        # Write to signal file for monitoring
        signal_dir = Path("/app/workspace/signals")
        signal_dir.mkdir(exist_ok=True, parents=True)

        signal_file = signal_dir / f"progress_{agent_id}_{report_id}.json"
        signal_file.write_text(json.dumps(progress_report, indent=2))

        # Append to progress log
        log_file = signal_dir / f"agent_{agent_id}_progress.jsonl"
        with log_file.open("a") as f:
            f.write(json.dumps(progress_report) + "\n")

        return {
            "success": True,
            "report_id": report_id,
            "message": "Progress report sent",
            "timestamp": timestamp
        }


class ReportMilestoneTool:
    """Tool for reporting specific milestones"""

    name = "report_milestone"
    description = "Report reaching a major milestone in task execution"

    async def execute(
        self,
        agent_id: str,
        milestone: str,
        details: Optional[str] = None,
        percent_complete: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Report reaching a milestone.

        Args:
            agent_id: ID of the reporting agent
            milestone: Name/description of the milestone
            details: Optional additional details
            percent_complete: Optional completion percentage (0-100)

        Returns:
            Confirmation that milestone was reported
        """
        message = f"Milestone: {milestone}"
        if details:
            message += f" - {details}"

        metadata = {
            "milestone": milestone,
            "type": "milestone"
        }

        if percent_complete is not None:
            metadata["percent_complete"] = min(100, max(0, percent_complete))
            message += f" ({metadata['percent_complete']}% complete)"

        tool = ReportProgressTool()
        return await tool.execute(agent_id, message, "in_progress", metadata)


class ReportStepTool:
    """Tool for reporting step-by-step progress"""

    name = "report_step"
    description = "Report completion of a numbered step in a multi-step process"

    async def execute(
        self,
        agent_id: str,
        step_number: int,
        total_steps: int,
        description: str
    ) -> Dict[str, Any]:
        """
        Report a numbered step.

        Args:
            agent_id: ID of the reporting agent
            step_number: Current step number
            total_steps: Total number of steps
            description: What this step does

        Returns:
            Confirmation that step was reported
        """
        percent = int((step_number / total_steps) * 100) if total_steps > 0 else 0
        message = f"Step {step_number}/{total_steps}: {description}"

        metadata = {
            "step": step_number,
            "total_steps": total_steps,
            "percent_complete": percent,
            "type": "step"
        }

        tool = ReportProgressTool()
        return await tool.execute(agent_id, message, "in_progress", metadata)


class ReportFindingTool:
    """Tool for reporting discoveries and findings"""

    name = "report_finding"
    description = "Report an important finding or discovery during exploration"

    async def execute(
        self,
        agent_id: str,
        finding: str,
        importance: str = "info",
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Report a finding or discovery.

        Args:
            agent_id: ID of the reporting agent
            finding: Description of what was found
            importance: Level (info, warning, critical)
            details: Optional additional details

        Returns:
            Confirmation that finding was reported
        """
        importance_map = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🚨"
        }

        icon = importance_map.get(importance, "📌")
        message = f"{icon} Finding: {finding}"

        status = "warning" if importance in ["warning", "critical"] else "in_progress"

        metadata = {
            "type": "finding",
            "importance": importance,
            "finding": finding
        }

        if details:
            metadata["details"] = details

        tool = ReportProgressTool()
        return await tool.execute(agent_id, message, status, metadata)


class ReportMetricsTool:
    """Tool for reporting metrics and statistics"""

    name = "report_metrics"
    description = "Report numerical metrics, statistics, or measurements"

    async def execute(
        self,
        agent_id: str,
        metrics: Dict[str, Any],
        description: Optional[str] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Report metrics or statistics.

        Args:
            agent_id: ID of the reporting agent
            metrics: Dictionary of metric names and values
            description: Optional description of the metrics
            category: Optional category (performance, resource, analysis, etc.)

        Returns:
            Confirmation that metrics were reported
        """
        message = description or "Metrics update"

        if metrics:
            metric_lines = [f"{k}: {v}" for k, v in metrics.items()]
            message += " - " + ", ".join(metric_lines[:3])  # Show first 3 inline
            if len(metric_lines) > 3:
                message += f" (+{len(metric_lines)-3} more)"

        metadata = {
            "type": "metrics",
            "metrics": metrics
        }

        if category:
            metadata["category"] = category

        tool = ReportProgressTool()
        return await tool.execute(agent_id, message, "in_progress", metadata)


# Register tools with the plugin system
def get_tools() -> List:
    """Return all progress reporting tools"""
    return [
        ReportProgressTool(),
        ReportMilestoneTool(),
        ReportStepTool(),
        ReportFindingTool(),
        ReportMetricsTool()
    ]


def get_tool_names() -> List[str]:
    """Return tool names for registration"""
    return [
        "report_progress",
        "report_milestone",
        "report_step",
        "report_finding",
        "report_metrics"
    ]


# Plugin metadata
__version__ = "1.0.0"
__author__ = "AshAI"
__description__ = "Progress reporting tools for continuous agent updates"