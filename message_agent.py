#!/usr/bin/env python3
"""
AshAI Tool: Message Agent
Sends a message to another agent through signal files.
Supports both full and partial agent IDs.
"""

import json
import sys
from pathlib import Path
import requests

def find_agent_id(partial_id):
    """Find full agent ID from partial ID"""
    try:
        # Try both localhost and host.docker.internal
        urls = ["http://localhost:8000/api/agents", "http://host.docker.internal:8000/api/agents"]

        for url in urls:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    agents = response.json()
                    for agent in agents:
                        if agent['id'].startswith(partial_id):
                            return agent['id']
                    break
            except requests.exceptions.ConnectionError:
                continue

    except Exception as e:
        print(f"Error finding agent: {e}")

    return partial_id  # Return as-is if not found

def message_agent(agent_id, message):
    """Send a message to an agent through signal file."""
    # Write to workspace directory which is mounted to host
    signal_file = Path("/app/workspace/.ashai_tool_signal.json")

    # Try to find full agent ID
    full_agent_id = find_agent_id(agent_id)

    # Create signal data
    signal_data = {
        "tool": "message_agent",
        "arguments": {
            "agent_id": full_agent_id,
            "message": message
        }
    }

    # Write signal file
    with open(signal_file, 'w') as f:
        json.dump(signal_data, f, indent=2)

    return f"Message sent to agent {full_agent_id}: {message[:100]}..."

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python message_agent.py <agent_id> <message>")
        sys.exit(1)

    agent_id = sys.argv[1]
    message = " ".join(sys.argv[2:])

    # First try to install requests if needed
    try:
        import requests
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests

    result = message_agent(agent_id, message)
    print(result)