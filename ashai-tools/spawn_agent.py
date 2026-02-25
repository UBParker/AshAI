#!/usr/bin/env python3
"""
AshAI Tool Bridge: Spawn Agent
This tool signals to AshAI to spawn a new agent.
Claude CLI can call this from inside the Docker container.
"""

import sys
import json
import uuid
import requests

def spawn_agent(name, role="assistant", model="claude-terminal", persona="A helpful AI assistant",
                tools=None, initial_message=None):
    """Signal AshAI to spawn a new agent."""

    # Write a signal file that AshAI can detect
    signal = {
        "tool": "spawn_agent",
        "arguments": {
            "name": name,
            "role": role,
            "model": model,
            "persona": persona,
            "tools": tools or [],
            "initial_message": initial_message
        }
    }

    # Use UUID-based filename to prevent race conditions
    signal_file = f"/app/workspace/.ashai_signal_{uuid.uuid4().hex[:12]}.json"
    with open(signal_file, "w") as f:
        json.dump(signal, f)

    # Also try to call the bridge API if available
    try:
        response = requests.post(
            "http://host.docker.internal:8000/api/tool/request",
            json={
                "tool_name": "spawn_agent",
                "arguments": signal["arguments"]
            },
            timeout=5
        )
        if response.status_code == 200:
            return response.json().get("result", f"Agent {name} spawned successfully")
    except requests.exceptions.RequestException:
        pass

    return f"Signaled AshAI to spawn agent: {name}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: spawn_agent.py <name> [--role <role>] [--model <model>] [--persona <persona>] [--tools <tool1,tool2>] [--initial-message <message>]")
        print("\nExample:")
        print('  spawn_agent.py CodeAnalyzer --role "Code expert" --tools "read_file,search_files" --initial-message "Analyze the Python files"')
        sys.exit(1)

    # Parse arguments
    name = sys.argv[1]
    role = "assistant"
    model = "claude-terminal"
    persona = "A helpful AI assistant"
    tools = []
    initial_message = None

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--role" and i + 1 < len(sys.argv):
            role = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--model" and i + 1 < len(sys.argv):
            model = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--persona" and i + 1 < len(sys.argv):
            persona = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--tools" and i + 1 < len(sys.argv):
            tools = sys.argv[i + 1].split(",")
            i += 2
        elif sys.argv[i] == "--initial-message" and i + 1 < len(sys.argv):
            initial_message = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    result = spawn_agent(name, role, model, persona, tools, initial_message)
    print(result)