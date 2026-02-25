#!/usr/bin/env python3
"""Reset Ash's status to idle"""

import asyncio
import sys
sys.path.insert(0, 'src')
from helperai.agents.manager import AgentManager
from helperai.core.types import AgentStatus

async def reset_ash():
    manager = AgentManager()
    await manager.initialize()

    # Get Ash's ID
    agents = await manager.list_agents()
    ash = next((a for a in agents if a.name == "Ash"), None)

    if ash:
        print(f"Found Ash with ID: {ash.id}")
        print(f"Current status: {ash.status}")

        # Force status to idle
        await manager._set_status(ash.id, AgentStatus.IDLE)

        # Clear any cancellation flags
        if ash.id in manager._cancellation_flags:
            manager._cancellation_flags[ash.id] = False

        # Clear message queue
        if ash.id in manager._message_queues:
            queue = manager._message_queues[ash.id]
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

        print("✅ Ash has been reset to idle status")

        # Verify
        agents = await manager.list_agents()
        ash = next((a for a in agents if a.name == "Ash"), None)
        print(f"New status: {ash.status}")
    else:
        print("Ash not found!")

if __name__ == "__main__":
    asyncio.run(reset_ash())