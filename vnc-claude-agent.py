#!/usr/bin/env python3
"""
VNC-based Claude.ai agent using browser automation
Runs multiple browser instances to interact with Claude using subscription
"""

import asyncio
import os
import json
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from aiohttp import web
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClaudeAgent:
    """Single Claude.ai conversation agent"""

    def __init__(self, agent_id: str, context: BrowserContext):
        self.agent_id = agent_id
        self.context = context
        self.page: Optional[Page] = None
        self.conversation_id: Optional[str] = None
        self.is_busy = False

    async def initialize(self):
        """Initialize the agent with a Claude.ai page"""
        self.page = await self.context.new_page()
        await self.page.goto("https://claude.ai/new")

        # Wait for page to load
        await self.page.wait_for_selector('div[contenteditable="true"]', timeout=10000)
        logger.info(f"Agent {self.agent_id} initialized")

    async def send_message(self, message: str) -> str:
        """Send a message to Claude and get response"""
        if self.is_busy:
            raise Exception(f"Agent {self.agent_id} is busy")

        self.is_busy = True
        try:
            # Find the input field
            input_field = await self.page.query_selector('div[contenteditable="true"]')
            if not input_field:
                raise Exception("Could not find input field")

            # Type the message
            await input_field.click()
            await input_field.fill(message)

            # Send the message (Enter key or send button)
            await self.page.keyboard.press("Enter")

            # Wait for response to start
            await self.page.wait_for_selector('div[data-testid="message-bot"]', timeout=30000)

            # Wait for response to complete (look for stop button to disappear)
            await asyncio.sleep(2)  # Initial wait

            # Get the last bot message
            bot_messages = await self.page.query_selector_all('div[data-testid="message-bot"]')
            if bot_messages:
                last_message = bot_messages[-1]
                response = await last_message.inner_text()
                return response

            return "No response received"

        finally:
            self.is_busy = False


class ClaudeAgentPool:
    """Manages a pool of Claude agents"""

    def __init__(self, pool_size: int = 3):
        self.pool_size = pool_size
        self.agents: List[ClaudeAgent] = []
        self.browser: Optional[Browser] = None
        self.playwright = None
        self.auth_cookies = None

    async def initialize(self, auth_file: str = "claude-cookies.json"):
        """Initialize the agent pool with authenticated browser contexts"""
        self.playwright = await async_playwright().start()

        # Launch browser in headless mode (or with VNC if needed)
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Set to True for production
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )

        # Load authentication cookies if available
        if os.path.exists(auth_file):
            with open(auth_file, 'r') as f:
                self.auth_cookies = json.load(f)

        # Create agents
        for i in range(self.pool_size):
            context = await self.browser.new_context(
                storage_state=self.auth_cookies if self.auth_cookies else None,
                viewport={'width': 1280, 'height': 720}
            )

            agent = ClaudeAgent(f"agent_{i}", context)
            await agent.initialize()
            self.agents.append(agent)

        logger.info(f"Initialized pool with {self.pool_size} agents")

    async def get_available_agent(self) -> Optional[ClaudeAgent]:
        """Get an available agent from the pool"""
        for agent in self.agents:
            if not agent.is_busy:
                return agent
        return None

    async def send_message(self, message: str) -> Dict:
        """Send a message using an available agent"""
        agent = await self.get_available_agent()
        if not agent:
            raise Exception("No available agents")

        response = await agent.send_message(message)
        return {
            "agent_id": agent.agent_id,
            "response": response
        }

    async def cleanup(self):
        """Clean up resources"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


# Web API Server
class ClaudeAPIServer:
    def __init__(self, agent_pool: ClaudeAgentPool):
        self.agent_pool = agent_pool
        self.app = web.Application()
        self.setup_routes()

    def setup_routes(self):
        self.app.router.add_post('/api/chat', self.handle_chat)
        self.app.router.add_get('/api/status', self.handle_status)

    async def handle_chat(self, request):
        """Handle chat API requests"""
        try:
            data = await request.json()
            message = data.get('message', '')

            if not message:
                return web.json_response(
                    {'error': 'Message is required'},
                    status=400
                )

            result = await self.agent_pool.send_message(message)
            return web.json_response(result)

        except Exception as e:
            logger.error(f"Error handling chat: {e}")
            return web.json_response(
                {'error': str(e)},
                status=500
            )

    async def handle_status(self, request):
        """Get status of agent pool"""
        available = sum(1 for agent in self.agent_pool.agents if not agent.is_busy)
        return web.json_response({
            'total_agents': len(self.agent_pool.agents),
            'available_agents': available,
            'busy_agents': len(self.agent_pool.agents) - available
        })


async def main():
    """Main function to run the VNC Claude agent system"""
    # Initialize agent pool
    agent_pool = ClaudeAgentPool(pool_size=3)
    await agent_pool.initialize()

    # Create and start API server
    api_server = ClaudeAPIServer(agent_pool)

    try:
        # Run the web server
        runner = web.AppRunner(api_server.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()

        logger.info("Claude Agent API running on http://0.0.0.0:8080")
        logger.info("Endpoints:")
        logger.info("  POST /api/chat - Send message to Claude")
        logger.info("  GET /api/status - Get agent pool status")

        # Keep running
        await asyncio.Event().wait()

    finally:
        await agent_pool.cleanup()


if __name__ == "__main__":
    asyncio.run(main())