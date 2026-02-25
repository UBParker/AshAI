#!/usr/bin/env python3
"""
AshAI Tool Bridge: Message Agent
This tool allows sending messages to existing agents.
Claude CLI can call this from inside the Docker container.
"""

import sys
import json
import uuid
import requests

def message_agent(agent_id, message):
    """Send a message to an existing agent via signal file.

    Uses UUID-based filenames to prevent race conditions.
    Falls back to direct API call if signal file write fails.
    """

    signal = {
        "tool": "message_agent",
        "arguments": {
            "agent_id": agent_id,
            "message": message
        }
    }

    # Use UUID-based filename to prevent race conditions
    signal_file = f"/app/workspace/.ashai_signal_{uuid.uuid4().hex[:12]}.json"
    try:
        with open(signal_file, "w") as f:
            json.dump(signal, f)

        return f"Message sent to agent {agent_id}. The agent will process it and respond through the AshAI interface."

    except OSError as e:
        # Fallback to direct API call if signal file fails
        try:
            response = requests.post(
                f"http://host.docker.internal:8000/api/agents/{agent_id}/message",
                json={"message": message, "stream": False},
                timeout=30
            )

            if response.status_code == 200:
                # Parse SSE response
                lines = response.text.strip().split('\n')
                content_parts = []

                for line in lines:
                    if line.startswith('data:'):
                        try:
                            data = json.loads(line[5:].strip())
                            if data.get('type') == 'content' and 'text' in data:
                                content_parts.append(data['text'])
                        except (json.JSONDecodeError, KeyError):
                            pass

                if content_parts:
                    return ''.join(content_parts)
                else:
                    return f"Message sent to agent {agent_id}"
            else:
                return f"Error: API returned status {response.status_code}"

        except requests.exceptions.RequestException as api_error:
            return f"Error: Could not send message via signal file or API: {str(e)}, {str(api_error)}"

def list_agents_with_ids():
    """Helper to list agents with their IDs."""
    try:
        response = requests.get(
            "http://host.docker.internal:8000/api/agents",
            timeout=5
        )

        if response.status_code == 200:
            agents = response.json()
            if not agents:
                return "No agents found."

            result = "Available agents:\n"
            for agent in agents:
                status_emoji = "🟢" if agent.get('status') == 'idle' else "🔴"
                result += f"{status_emoji} {agent['name']} (ID: {agent['id']}) - {agent.get('status', 'unknown')}\n"
            return result
        else:
            return "Error: Could not list agents"
    except requests.exceptions.RequestException:
        return "Error: Could not connect to AshAI API"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: message_agent.py <agent_id> <message>")
        print("   or: message_agent.py --list")
        print("\nTo list available agents with IDs:")
        print("  python message_agent.py --list")
        print("\nTo send a message to an agent:")
        print("  python message_agent.py abc123def456 'Please check the logs'")
        sys.exit(1)

    if sys.argv[1] == "--list":
        print(list_agents_with_ids())
    elif len(sys.argv) < 3:
        print("Error: Please provide both agent_id and message")
        print("Use --list to see available agents")
        sys.exit(1)
    else:
        agent_id = sys.argv[1]
        message = ' '.join(sys.argv[2:])
        result = message_agent(agent_id, message)
        print(result)