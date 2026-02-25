#!/usr/bin/env python3
"""
AshAI Tool: Report to Eve
Sends a report back to Eve (or Ash) through the signal file mechanism.
"""

import json
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime

def report_to_eve(report, sender=None):
    """Send a report to Ash through signal file.

    Uses UUID-based filenames to prevent race conditions when
    multiple agents report simultaneously.
    """
    # Auto-detect sender from environment or use provided value
    if sender is None:
        sender = os.environ.get("ASHAI_AGENT_NAME", "unknown_agent")

    # Use UUID-based filename to prevent race conditions
    signal_dir = Path("/app/workspace")
    signal_file = signal_dir / f".ashai_signal_{uuid.uuid4().hex[:12]}.json"

    # Create signal data
    signal_data = {
        "tool": "report_to_ash",
        "arguments": {
            "message": report,
            "sender": sender,
            "timestamp": datetime.now().isoformat()
        }
    }

    # Write signal file
    with open(signal_file, 'w') as f:
        json.dump(signal_data, f, indent=2)

    return f"Report sent to Ash: {report[:200]}..."

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python report_to_eve.py <report> [--sender <name>]")
        sys.exit(1)

    # Parse --sender flag if provided
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