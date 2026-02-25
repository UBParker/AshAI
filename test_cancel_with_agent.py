#!/usr/bin/env python3
"""Test the cancel functionality by creating a test agent and canceling its operation"""

import asyncio
import aiohttp
import json
import time

async def create_test_agent():
    """Create a test agent for testing cancellation"""
    async with aiohttp.ClientSession() as session:
        # Create a test agent
        url = "http://localhost:8000/api/agents"
        data = {
            "name": "TestCancelBot",
            "role": "A test agent that counts slowly",
            "goal": "Test cancellation functionality",
            "provider_name": "claude_terminal",
            "model_name": "",
            "tool_names": []
        }

        async with session.post(url, json=data) as response:
            if response.status == 200:
                agent = await response.json()
                print(f"✅ Created test agent: {agent['name']} (ID: {agent['id']})")
                return agent['id']
            else:
                print(f"❌ Failed to create agent: {response.status}")
                return None

async def send_long_message(session, agent_id):
    """Send a long-running message to the agent"""
    print(f"\n📤 Sending long counting task to agent...")
    url = f"http://localhost:8000/api/agents/{agent_id}/message"
    data = {
        "message": "Please count from 1 to 50, saying each number on a new line. Take your time with each number."
    }

    content_received = []
    cancelled = False

    try:
        async with session.post(url, json=data) as response:
            async for line in response.content:
                if line:
                    line_str = line.decode('utf-8').strip()
                    if line_str.startswith('data: '):
                        try:
                            event_data = json.loads(line_str[6:])
                            if event_data.get('type') == 'content':
                                text = event_data.get('text', '')
                                content_received.append(text)
                                print(text, end='', flush=True)
                            elif event_data.get('type') == 'cancelled':
                                print(f"\n\n✅ CANCELLED: {event_data.get('message')}")
                                cancelled = True
                                break
                            elif event_data.get('type') == 'error':
                                print(f"\n❌ Error: {event_data.get('error')}")
                                break
                        except json.JSONDecodeError:
                            pass
    except Exception as e:
        print(f"\n⚠️ Stream ended: {e}")

    return ''.join(content_received), cancelled

async def cancel_agent(session, agent_id):
    """Send cancel request to the agent"""
    print(f"\n\n🛑 Sending CANCEL request to agent...")
    url = f"http://localhost:8000/api/agents/{agent_id}/cancel"

    async with session.post(url) as response:
        result = await response.json()
        print(f"📍 Cancel response: {result}")
        return result

async def main():
    # Create a test agent
    agent_id = await create_test_agent()

    if not agent_id:
        print("Failed to create test agent")
        return

    async with aiohttp.ClientSession() as session:
        # Start the long-running task
        message_task = asyncio.create_task(send_long_message(session, agent_id))

        # Wait a bit to let it start processing
        await asyncio.sleep(3)

        # Check agent status before cancel
        async with session.get(f"http://localhost:8000/api/agents/{agent_id}") as resp:
            agent = await resp.json()
            print(f"\n📊 Agent status before cancel: {agent['status']}")

        # Send cancel request
        cancel_result = await cancel_agent(session, agent_id)

        # Wait for the message task to complete
        content, was_cancelled = await message_task

        # Check agent status after cancel
        await asyncio.sleep(1)
        async with session.get(f"http://localhost:8000/api/agents/{agent_id}") as resp:
            agent = await resp.json()
            print(f"\n📊 Agent status after cancel: {agent['status']}")

        # Summary
        print("\n" + "="*50)
        print("📋 TEST SUMMARY:")
        print(f"- Agent created: ✅")
        print(f"- Content received before cancel: {len(content)} chars")
        print(f"- Cancel request successful: {'✅' if cancel_result.get('status') == 'cancelled' else '❌'}")
        print(f"- Stream marked as cancelled: {'✅' if was_cancelled else '❌'}")
        print(f"- Agent returned to idle: {'✅' if agent['status'] == 'idle' else '❌'}")
        print("="*50)

        # Clean up - destroy the test agent
        print("\n🧹 Cleaning up test agent...")
        async with session.delete(f"http://localhost:8000/api/agents/{agent_id}") as resp:
            if resp.status == 200:
                print("✅ Test agent removed")

if __name__ == "__main__":
    print("🧪 CANCEL FUNCTIONALITY TEST")
    print("="*50)
    asyncio.run(main())