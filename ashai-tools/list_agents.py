#!/usr/bin/env python3
"""
AshAI Tool: List Agents
Lists all available agents with their status and details.
"""

import sys
import json

try:
    import requests
except ImportError:
    # If requests isn't installed, just note it but continue
    print("Warning: requests module not available")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

def list_agents():
    """List all agents with their status and capabilities."""
    try:
        # Try localhost first (for host), fallback to host.docker.internal (for Docker)
        urls = ["http://localhost:8000/api/agents", "http://host.docker.internal:8000/api/agents"]
        response = None
        last_error = None

        for url in urls:
            try:
                response = requests.get(url, timeout=5)
                break
            except requests.exceptions.ConnectionError as e:
                last_error = e
                continue

        if response is None:
            raise last_error

        if response.status_code == 200:
            agents = response.json()
            if not agents:
                return "No agents found."

            result = []
            result.append(f"Found {len(agents)} agent(s):\n")

            for agent in agents:
                # Status emoji
                status_emoji = {
                    'idle': '🟢',
                    'running': '🟡',
                    'error': '🔴',
                    'created': '🔵'
                }.get(agent.get('status', 'unknown'), '⚪')

                # Basic info
                name = agent['name']
                agent_id = agent['id'][:8] if len(agent['id']) > 8 else agent['id']
                status = agent.get('status', 'unknown')

                result.append(f"{status_emoji} **{name}** (ID: {agent_id}...) - Status: {status}")

                # Show tools if any
                tools = agent.get('tool_names', [])
                if tools:
                    result.append(f"  Tools: {', '.join(tools[:5])}" + (" ..." if len(tools) > 5 else ""))

            return '\n'.join(result)
        else:
            return f"Error: API returned status {response.status_code}"

    except requests.exceptions.Timeout:
        return "Error: Request timed out. The AshAI backend may not be running."
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to AshAI backend"
    except Exception as e:
        return f"Error listing agents: {str(e)}"

if __name__ == "__main__":
    result = list_agents()
    print(result)