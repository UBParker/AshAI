#!/usr/bin/env python3
"""Reset Ash agent status to idle."""

import asyncio
from helperai.agents.manager import AgentManager
from helperai.core.types import AgentStatus

async def main():
    manager = AgentManager()
    await manager.initialize()

    # Get Ash's ID
    agents = await manager.list_agents()
    ash = next((a for a in agents if a.name == "Ash"), None)

    if ash:
        print(f"Found Ash with ID: {ash.id}, current status: {ash.status}")

        # Reset status to idle
        await manager._set_status(ash.id, AgentStatus.IDLE)
        print(f"Reset Ash to IDLE status")

        # Clear any queued messages
        if ash.id in manager._message_queues:
            queue = manager._message_queues[ash.id]
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            print("Cleared message queue")
    else:
        print("Ash not found!")

if __name__ == "__main__":
    asyncio.run(main())