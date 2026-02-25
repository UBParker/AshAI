#!/usr/bin/env python3
"""
Simple AshAI Tool: Report to Eve/Ash
Sends a report directly to Ash (the master agent) via the API.
"""

import sys
import requests
import json

def report_to_eve(report):
    """Send a report to Eve/Ash via the API."""

    # First, find Ash's agent ID
    urls = ["http://localhost:8000/api/agents", "http://host.docker.internal:8000/api/agents"]
    ash_id = None

    for url in urls:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                agents = response.json()
                for agent in agents:
                    if agent['name'] == 'Ash':
                        ash_id = agent['id']
                        break
                if ash_id:
                    break
        except requests.exceptions.RequestException:
            continue

    if not ash_id:
        return "Could not find Ash agent"

    # Send the report to Ash
    message_urls = [
        f"http://localhost:8000/api/agents/{ash_id}/message",
        f"http://host.docker.internal:8000/api/agents/{ash_id}/message"
    ]

    payload = {"message": f"Report from agent: {report}"}

    for url in message_urls:
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
                stream=True
            )

            if response.status_code == 200:
                return f"Report sent to Ash successfully"

        except requests.exceptions.ConnectionError:
            continue

    return "Failed to send report to Ash"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python report_to_eve_simple.py <report>")
        sys.exit(1)

    report = " ".join(sys.argv[1:])

    # Auto-install requests if needed
    try:
        import requests
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests

    result = report_to_eve(report)
    print(result)