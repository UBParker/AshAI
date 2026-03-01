#!/usr/bin/env python3
"""
Progress reporting tool for AshAI agents
Allows agents to send progress updates without stopping execution
"""

import json
import sys
from datetime import datetime
from pathlib import Path
import time
import hashlib

def report_progress(message: str, status: str = "in_progress", metadata: dict = None):
    """
    Report progress to the user without stopping execution.

    Args:
        message: The progress update message
        status: Current status (in_progress, completed, warning, error)
        metadata: Optional metadata dict with additional info

    Returns:
        dict: Confirmation of report sent
    """

    # Generate unique report ID
    timestamp = datetime.now().isoformat()
    report_id = hashlib.md5(f"{timestamp}{message}".encode()).hexdigest()[:8]

    # Create progress report
    progress_report = {
        "id": report_id,
        "type": "progress_report",
        "timestamp": timestamp,
        "status": status,
        "message": message,
        "metadata": metadata or {}
    }

    # Define signal file paths
    signal_dir = Path("/app/workspace/signals")
    signal_dir.mkdir(exist_ok=True)

    # Write to multiple locations for redundancy
    locations = [
        signal_dir / f"progress_{report_id}.json",
        Path("/app/workspace") / f"progress_report_{report_id}.json",
        Path("/tmp") / f"progress_{report_id}.json"
    ]

    written = False
    for signal_file in locations:
        try:
            signal_file.write_text(json.dumps(progress_report, indent=2))
            written = True
            break
        except Exception as e:
            continue

    # Also write to a rolling log file
    try:
        log_file = signal_dir / "progress_log.jsonl"
        with log_file.open("a") as f:
            f.write(json.dumps(progress_report) + "\n")
    except:
        pass

    # Print to stdout for immediate visibility
    status_icon = {
        "in_progress": "🔄",
        "completed": "✅",
        "warning": "⚠️",
        "error": "❌"
    }.get(status, "📝")

    print(f"{status_icon} Progress Report [{report_id}]: {message}")
    if metadata:
        for key, value in metadata.items():
            print(f"   {key}: {value}")

    return {
        "success": True,
        "report_id": report_id,
        "message": "Progress report sent",
        "timestamp": timestamp
    }


def report_milestone(milestone_name: str, details: str = None, percent_complete: int = None):
    """
    Report reaching a specific milestone.

    Args:
        milestone_name: Name of the milestone reached
        details: Optional details about the milestone
        percent_complete: Optional completion percentage (0-100)
    """
    message = f"Milestone reached: {milestone_name}"
    if details:
        message += f" - {details}"

    metadata = {"milestone": milestone_name}
    if percent_complete is not None:
        metadata["percent_complete"] = percent_complete
        message += f" ({percent_complete}% complete)"

    return report_progress(message, "in_progress", metadata)


def report_step(step_number: int, total_steps: int, description: str):
    """
    Report completion of a numbered step.

    Args:
        step_number: Current step number
        total_steps: Total number of steps
        description: Description of the step
    """
    percent = int((step_number / total_steps) * 100)
    message = f"Step {step_number}/{total_steps}: {description}"

    metadata = {
        "step": step_number,
        "total_steps": total_steps,
        "percent_complete": percent
    }

    return report_progress(message, "in_progress", metadata)


def report_finding(finding: str, importance: str = "info"):
    """
    Report a specific finding or discovery.

    Args:
        finding: Description of what was found
        importance: Importance level (info, warning, critical)
    """
    importance_icons = {
        "info": "ℹ️",
        "warning": "⚠️",
        "critical": "🚨"
    }

    icon = importance_icons.get(importance, "📌")
    message = f"{icon} Finding: {finding}"

    status = "warning" if importance == "warning" else "in_progress"
    metadata = {"importance": importance, "type": "finding"}

    return report_progress(message, status, metadata)


def report_metrics(metrics: dict, description: str = None):
    """
    Report metrics or statistics.

    Args:
        metrics: Dictionary of metric names and values
        description: Optional description
    """
    message = description or "Metrics update"

    # Format metrics for display
    if metrics:
        metric_lines = []
        for key, value in metrics.items():
            metric_lines.append(f"{key}: {value}")
        message += " - " + ", ".join(metric_lines)

    metadata = {"metrics": metrics, "type": "metrics"}

    return report_progress(message, "in_progress", metadata)


# CLI interface
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: report_progress.py <message> [status] [metadata_json]")
        print("   or: report_progress.py --milestone <name> [details] [percent]")
        print("   or: report_progress.py --step <num> <total> <description>")
        print("   or: report_progress.py --finding <finding> [importance]")
        print("   or: report_progress.py --metrics <json> [description]")
        sys.exit(1)

    if sys.argv[1] == "--milestone":
        if len(sys.argv) < 3:
            print("Error: milestone name required")
            sys.exit(1)

        milestone_name = sys.argv[2]
        details = sys.argv[3] if len(sys.argv) > 3 else None
        percent = int(sys.argv[4]) if len(sys.argv) > 4 else None

        result = report_milestone(milestone_name, details, percent)

    elif sys.argv[1] == "--step":
        if len(sys.argv) < 5:
            print("Error: step number, total, and description required")
            sys.exit(1)

        step_num = int(sys.argv[2])
        total = int(sys.argv[3])
        desc = " ".join(sys.argv[4:])

        result = report_step(step_num, total, desc)

    elif sys.argv[1] == "--finding":
        if len(sys.argv) < 3:
            print("Error: finding description required")
            sys.exit(1)

        finding = sys.argv[2]
        importance = sys.argv[3] if len(sys.argv) > 3 else "info"

        result = report_finding(finding, importance)

    elif sys.argv[1] == "--metrics":
        if len(sys.argv) < 3:
            print("Error: metrics JSON required")
            sys.exit(1)

        try:
            metrics = json.loads(sys.argv[2])
            description = sys.argv[3] if len(sys.argv) > 3 else None
            result = report_metrics(metrics, description)
        except json.JSONDecodeError:
            print("Error: Invalid JSON for metrics")
            sys.exit(1)

    else:
        # Simple progress report
        message = sys.argv[1]
        status = sys.argv[2] if len(sys.argv) > 2 else "in_progress"

        metadata = None
        if len(sys.argv) > 3:
            try:
                metadata = json.loads(sys.argv[3])
            except:
                pass

        result = report_progress(message, status, metadata)

    print(json.dumps(result, indent=2))