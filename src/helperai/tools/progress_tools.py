"""
Progress reporting tools that integrate with the streaming system
Allows agents to send real-time progress updates through SSE
"""

from typing import Dict, Any, Optional
from datetime import datetime
import json
import asyncio
from ..core.events import EventBus, Event


class ReportProgressTool:
    """
    Tool for sending progress updates through the event stream
    These updates are immediately streamed to the frontend via SSE
    """

    name = "report_progress"
    description = "Send a progress update that streams to the frontend in real-time"

    def __init__(self, event_bus: EventBus = None):
        self.event_bus = event_bus or EventBus()

    async def execute(
        self,
        agent_id: str,
        message: str,
        status: str = "in_progress",
        percent: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a progress report that streams immediately to frontend.

        Args:
            agent_id: ID of the reporting agent
            message: Progress message to display
            status: Status (in_progress, completed, warning, error)
            percent: Optional completion percentage (0-100)
            metadata: Optional additional data

        Returns:
            Confirmation dict
        """
        timestamp = datetime.now().isoformat()

        # Create progress event
        progress_data = {
            "agent_id": agent_id,
            "type": "progress",
            "timestamp": timestamp,
            "status": status,
            "message": message,
            "metadata": metadata or {}
        }

        if percent is not None:
            progress_data["percent"] = max(0, min(100, percent))

        # Emit event for SSE streaming
        event = Event(
            type="agent_progress",
            data=progress_data,
            agent_id=agent_id
        )

        await self.event_bus.emit(event)

        # Also store in agent's message thread for persistence
        # This allows the frontend to catch up if connection is lost
        from ..core.database import get_session
        from ..models import AgentMessage

        async with get_session() as session:
            progress_msg = AgentMessage(
                agent_id=agent_id,
                role="system",
                content=json.dumps(progress_data),
                message_type="progress",
                metadata=progress_data
            )
            session.add(progress_msg)
            await session.commit()

        return {
            "success": True,
            "message": "Progress reported",
            "timestamp": timestamp,
            "streamed": True
        }


class ReportMilestoneTool:
    """Report major milestones with streaming"""

    name = "report_milestone"
    description = "Report reaching a major milestone with real-time streaming"

    def __init__(self, event_bus: EventBus = None):
        self.progress_tool = ReportProgressTool(event_bus)

    async def execute(
        self,
        agent_id: str,
        milestone: str,
        details: Optional[str] = None,
        percent_complete: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Report a milestone achievement.

        Args:
            agent_id: Agent ID
            milestone: Milestone name/description
            details: Optional additional details
            percent_complete: Optional overall completion percentage

        Returns:
            Confirmation dict
        """
        message = f"🎯 Milestone: {milestone}"
        if details:
            message += f" - {details}"

        metadata = {
            "milestone": milestone,
            "milestone_type": "major"
        }

        if details:
            metadata["details"] = details

        return await self.progress_tool.execute(
            agent_id=agent_id,
            message=message,
            status="in_progress",
            percent=percent_complete,
            metadata=metadata
        )


class ReportStepTool:
    """Report step-by-step progress with streaming"""

    name = "report_step"
    description = "Report completion of a step in a multi-step process"

    def __init__(self, event_bus: EventBus = None):
        self.progress_tool = ReportProgressTool(event_bus)

    async def execute(
        self,
        agent_id: str,
        step: int,
        total_steps: int,
        description: str,
        status: str = "in_progress"
    ) -> Dict[str, Any]:
        """
        Report step progress.

        Args:
            agent_id: Agent ID
            step: Current step number
            total_steps: Total number of steps
            description: What this step does
            status: Step status

        Returns:
            Confirmation dict
        """
        percent = int((step / total_steps) * 100) if total_steps > 0 else 0
        message = f"Step {step}/{total_steps}: {description}"

        metadata = {
            "step": step,
            "total_steps": total_steps,
            "step_description": description
        }

        return await self.progress_tool.execute(
            agent_id=agent_id,
            message=message,
            status=status,
            percent=percent,
            metadata=metadata
        )


class ReportFindingTool:
    """Report discoveries and findings with streaming"""

    name = "report_finding"
    description = "Report an important finding or discovery"

    def __init__(self, event_bus: EventBus = None):
        self.progress_tool = ReportProgressTool(event_bus)

    async def execute(
        self,
        agent_id: str,
        finding: str,
        importance: str = "info",
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Report a finding.

        Args:
            agent_id: Agent ID
            finding: What was found
            importance: Level (info, warning, critical)
            details: Optional additional details

        Returns:
            Confirmation dict
        """
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🚨"
        }

        icon = icons.get(importance, "📌")
        message = f"{icon} Finding: {finding}"

        status = "warning" if importance in ["warning", "critical"] else "in_progress"

        metadata = {
            "finding_type": "discovery",
            "importance": importance,
            "finding": finding
        }

        if details:
            metadata["details"] = details

        return await self.progress_tool.execute(
            agent_id=agent_id,
            message=message,
            status=status,
            metadata=metadata
        )


class ReportMetricsTool:
    """Report metrics and measurements with streaming"""

    name = "report_metrics"
    description = "Report numerical metrics or measurements"

    def __init__(self, event_bus: EventBus = None):
        self.progress_tool = ReportProgressTool(event_bus)

    async def execute(
        self,
        agent_id: str,
        metrics: Dict[str, Any],
        description: Optional[str] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Report metrics.

        Args:
            agent_id: Agent ID
            metrics: Dictionary of metric names and values
            description: Optional description
            category: Optional category (performance, resource, etc.)

        Returns:
            Confirmation dict
        """
        message = description or "📊 Metrics update"

        # Add inline preview of key metrics
        if metrics:
            preview = []
            for key, value in list(metrics.items())[:3]:
                if isinstance(value, (int, float)):
                    preview.append(f"{key}: {value:.2f}" if isinstance(value, float) else f"{key}: {value}")
                else:
                    preview.append(f"{key}: {value}")

            if preview:
                message += " - " + ", ".join(preview)

            if len(metrics) > 3:
                message += f" (+{len(metrics)-3} more)"

        metadata = {
            "metrics": metrics,
            "metric_type": category or "general"
        }

        if category:
            metadata["category"] = category

        return await self.progress_tool.execute(
            agent_id=agent_id,
            message=message,
            status="in_progress",
            metadata=metadata
        )


# Export tools
__all__ = [
    'ReportProgressTool',
    'ReportMilestoneTool',
    'ReportStepTool',
    'ReportFindingTool',
    'ReportMetricsTool'
]