#!/usr/bin/env python3
"""
Simple AshAI Tool: Message Agent
Sends a message directly to an agent via the API.
"""

import sys
import requests
import json

def message_agent(agent_id, message):
    """Send a message to an agent via the API."""

    # Try both localhost and Docker host
    urls = [
        f"http://localhost:8000/api/agents/{agent_id}/message",
        f"http://host.docker.internal:8000/api/agents/{agent_id}/message"
    ]

    payload = {"message": message}

    for url in urls:
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
                stream=True
            )

            if response.status_code == 200:
                # Parse the SSE stream
                result_text = ""
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            try:
                                data = json.loads(line_str[6:])
                                if data.get('type') == 'content':
                                    result_text += data.get('text', '')
                            except:
                                pass

                return f"Message sent to {agent_id}. Response: {result_text[:200]}..."

        except requests.exceptions.ConnectionError:
            continue

    return f"Failed to send message to agent {agent_id}"

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python message_agent_simple.py <agent_id> <message>")
        sys.exit(1)

    agent_id = sys.argv[1]
    message = " ".join(sys.argv[2:])

    # Auto-install requests if needed
    try:
        import requests
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests

    result = message_agent(agent_id, message)
    print(result)