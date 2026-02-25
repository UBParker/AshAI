#!/usr/bin/env python3
"""
AshAI Tool Bridge: Report to Ash
Posts a report directly to the AshAI backend API.
Claude CLI can call this from inside the Docker container.
"""

import json
import os
import sys
import requests


BACKEND_URL = os.environ.get("ASHAI_BACKEND_URL", "http://host.docker.internal:8000")


def report_to_eve(report, sender=None):
    """Send a report to Ash via the backend API."""
    if sender is None:
        sender = os.environ.get("ASHAI_AGENT_NAME", "unknown_agent")

    message = f"[Report from sub-agent '{sender}']: {report}"

    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/chat",
            json={"message": message},
            timeout=30,
        )
        if resp.status_code == 200:
            return f"Report delivered to Ash."
        else:
            return f"Error: API returned {resp.status_code}: {resp.text[:200]}"
    except requests.exceptions.RequestException as e:
        return f"Error: Could not reach backend: {e}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: report_to_eve.py <report> [--sender <name>]")
        print("\nExample:")
        print('  report_to_eve.py "Analysis complete: found 3 issues" --sender CodeAnalyzer')
        sys.exit(1)

    sender = None
    args = sys.argv[1:]
    if "--sender" in args:
        idx = args.index("--sender")
        if idx + 1 < len(args):
            sender = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    report = " ".join(args)
    result = report_to_eve(report, sender=sender)
    print(result)
