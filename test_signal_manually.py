#!/usr/bin/env python3
"""Manual test for signal file processing"""
import asyncio
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from helperai.signal_monitor import SignalFileMonitor

async def main():
    # Create mock agent manager
    class MockAgentManager:
        async def create_agent(self, name, role, model):
            print(f"create_agent called: name={name}, model={model}")
            print(f"role={role[:50]}...")
            # Return mock agent
            class MockAgent:
                id = "test123"
                name = name
            return MockAgent()

        async def add_agent(self, agent):
            print(f"add_agent called: agent.id={agent.id}, agent.name={agent.name}")

    # Create monitor
    monitor = SignalFileMonitor(watch_dir=".", agent_manager=MockAgentManager())

    # Test processing directly
    test_signal = {
        "tool": "spawn_agent",
        "arguments": {
            "name": "TestAgent",
            "role": "test assistant",
            "model": "claude-terminal",
            "persona": "A test agent"
        }
    }

    # Write test file
    with open(".ashai_tool_signal.json", "w") as f:
        json.dump(test_signal, f)

    # Process it
    await monitor.process_signal_file(".ashai_tool_signal.json")

    # Check if file was deleted
    if not os.path.exists(".ashai_tool_signal.json"):
        print("✓ Signal file was deleted after processing")
    else:
        print("✗ Signal file still exists")

if __name__ == "__main__":
    asyncio.run(main())