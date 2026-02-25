#!/usr/bin/env python3
"""Test the cancel functionality for agents"""

import asyncio
import aiohttp
import json

async def send_message_and_cancel(agent_id):
    """Send a message and then cancel it after a short delay"""

    async with aiohttp.ClientSession() as session:
        # Send a long-running message
        print(f"Sending message to agent {agent_id}...")
        message_url = f"http://localhost:8000/api/agents/{agent_id}/message"
        data = {"message": "Please count from 1 to 100 slowly, saying each number."}

        # Start the message stream
        response_task = asyncio.create_task(
            stream_response(session, message_url, data)
        )

        # Wait 2 seconds then cancel
        await asyncio.sleep(2)

        print("\n🛑 Sending cancel request...")
        cancel_url = f"http://localhost:8000/api/agents/{agent_id}/cancel"
        async with session.post(cancel_url) as cancel_response:
            cancel_result = await cancel_response.json()
            print(f"Cancel result: {cancel_result}")

        # Wait for the stream to complete/cancel
        await response_task

async def stream_response(session, url, data):
    """Stream the response from the agent"""
    try:
        async with session.post(url, json=data) as response:
            async for line in response.content:
                if line:
                    line_str = line.decode('utf-8').strip()
                    if line_str.startswith('data: '):
                        try:
                            event_data = json.loads(line_str[6:])
                            if event_data.get('type') == 'content':
                                print(event_data.get('text', ''), end='', flush=True)
                            elif event_data.get('type') == 'cancelled':
                                print(f"\n✅ Response cancelled: {event_data.get('message')}")
                                break
                            elif event_data.get('type') == 'error':
                                print(f"\n❌ Error: {event_data.get('error')}")
                                break
                        except json.JSONDecodeError:
                            pass
    except Exception as e:
        print(f"\nStream error: {e}")

async def main():
    # Get Ash's ID
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8000/api/agents") as response:
            agents = await response.json()
            ash = next((a for a in agents if a['name'] == 'Ash'), None)

            if ash:
                print(f"Found Ash with ID: {ash['id']}")
                print(f"Current status: {ash['status']}\n")
                await send_message_and_cancel(ash['id'])
            else:
                print("Ash not found!")

if __name__ == "__main__":
    asyncio.run(main())