#!/usr/bin/env python3
"""Test message queueing when agent is busy"""

import asyncio
import aiohttp
import json

async def send_message(session, agent_id, message):
    """Send a message to an agent"""
    url = f"http://localhost:8000/api/agents/{agent_id}/message"
    data = {"message": message}

    try:
        async with session.post(url, json=data) as response:
            async for line in response.content:
                if line:
                    line_str = line.decode('utf-8').strip()
                    if line_str.startswith('data: '):
                        try:
                            event_data = json.loads(line_str[6:])
                            if event_data.get('type') == 'queued':
                                print(f"Message queued at position {event_data.get('position')}")
                                return "queued"
                        except:
                            pass
            return "processed"
    except Exception as e:
        print(f"Error: {e}")
        return "error"

async def test_queue():
    """Send multiple messages to test queueing"""
    agent_id = "8dfe0ce2e1fd"  # Ash

    async with aiohttp.ClientSession() as session:
        # Send first message (will start processing)
        print("Sending first message...")
        task1 = asyncio.create_task(send_message(session, agent_id, "First message - count to 3 slowly"))

        # Wait a bit then send more messages while first is processing
        await asyncio.sleep(0.5)

        print("Sending second message...")
        task2 = asyncio.create_task(send_message(session, agent_id, "Second message - what is 2+2?"))

        print("Sending third message...")
        task3 = asyncio.create_task(send_message(session, agent_id, "Third message - say hi"))

        # Wait for all to complete
        results = await asyncio.gather(task1, task2, task3)
        print(f"Results: {results}")

if __name__ == "__main__":
    asyncio.run(test_queue())