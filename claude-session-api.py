#!/usr/bin/env python3
"""
Direct Claude.ai API using session cookies
No browser needed - just use the cookies to make API requests
"""

import asyncio
import json
import aiohttp
from aiohttp import web
from yarl import URL
import logging
from typing import Dict, List, Optional
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClaudeSessionAPI:
    """Direct API access to Claude.ai using session cookies"""

    def __init__(self, cookies_file: str = "claude-cookies.json"):
        self.cookies = {}
        self.organization_id = None
        self.load_cookies(cookies_file)

    def load_cookies(self, cookies_file: str):
        """Load cookies from the exported file"""
        try:
            with open(cookies_file, 'r') as f:
                data = json.load(f)
                # Convert cookies to dict format for requests
                for cookie in data.get('cookies', []):
                    self.cookies[cookie['name']] = cookie['value']
            logger.info(f"Loaded {len(self.cookies)} cookies")
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")

    async def create_conversation(self, session: aiohttp.ClientSession) -> str:
        """Create a new conversation and return its ID"""
        # Generate a UUID for the conversation
        conversation_id = str(uuid.uuid4())

        # Claude.ai API endpoint for creating conversations
        url = "https://claude.ai/api/organizations/self/conversations"

        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Origin": "https://claude.ai",
            "Referer": "https://claude.ai/new",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

        payload = {
            "uuid": conversation_id,
            "name": ""
        }

        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status == 201 or resp.status == 200:
                data = await resp.json()
                return data.get('uuid', conversation_id)
            else:
                logger.error(f"Failed to create conversation: {resp.status}")
                return conversation_id

    async def send_message(self, message: str, conversation_id: Optional[str] = None) -> Dict:
        """Send a message to Claude using the session cookies"""

        # Create a session with cookies
        connector = aiohttp.TCPConnector(ssl=False)
        cookie_jar = aiohttp.CookieJar()

        async with aiohttp.ClientSession(
            connector=connector,
            cookie_jar=cookie_jar
        ) as session:
            # Add cookies to session
            for name, value in self.cookies.items():
                session.cookie_jar.update_cookies({name: value},
                                                 response_url=URL("https://claude.ai"))

            # Create conversation if needed
            if not conversation_id:
                conversation_id = await self.create_conversation(session)

            # Claude.ai message endpoint
            url = f"https://claude.ai/api/organizations/self/conversations/{conversation_id}/messages"

            headers = {
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Origin": "https://claude.ai",
                "Referer": f"https://claude.ai/chat/{conversation_id}",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }

            # Message payload
            payload = {
                "prompt": message,
                "attachments": [],
                "timezone": "America/New_York",
                "model": "claude-3-5-sonnet-20241022",
                "render_markdown": True,
                "custom_instruction": ""
            }

            try:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        # Read streaming response
                        response_text = ""
                        async for line in resp.content:
                            line_str = line.decode('utf-8').strip()
                            if line_str.startswith('data: '):
                                try:
                                    data = json.loads(line_str[6:])
                                    if 'completion' in data:
                                        response_text = data['completion']
                                except json.JSONDecodeError:
                                    continue

                        return {
                            "success": True,
                            "response": response_text,
                            "conversation_id": conversation_id
                        }
                    else:
                        error_text = await resp.text()
                        logger.error(f"API error: {resp.status} - {error_text}")
                        return {
                            "success": False,
                            "error": f"API returned {resp.status}",
                            "details": error_text
                        }

            except Exception as e:
                logger.error(f"Request failed: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }


class ClaudeAPIServer:
    """HTTP API server for Claude session API"""

    def __init__(self, claude_api: ClaudeSessionAPI):
        self.claude_api = claude_api
        self.app = web.Application()
        self.conversations = {}  # Track conversation IDs
        self.setup_routes()

    def setup_routes(self):
        self.app.router.add_post('/api/chat', self.handle_chat)
        self.app.router.add_get('/api/status', self.handle_status)

    async def handle_chat(self, request):
        """Handle chat API requests"""
        try:
            data = await request.json()
            message = data.get('message', '')
            conversation_id = data.get('conversation_id', None)

            if not message:
                return web.json_response(
                    {'error': 'Message is required'},
                    status=400
                )

            result = await self.claude_api.send_message(message, conversation_id)
            return web.json_response(result)

        except Exception as e:
            logger.error(f"Error handling chat: {e}")
            return web.json_response(
                {'error': str(e)},
                status=500
            )

    async def handle_status(self, request):
        """Get API status"""
        return web.json_response({
            'status': 'online',
            'cookies_loaded': len(self.claude_api.cookies) > 0,
            'cookie_count': len(self.claude_api.cookies)
        })


async def main():
    """Run the Claude session API server"""
    # Initialize API with cookies
    claude_api = ClaudeSessionAPI("claude-cookies.json")

    # Create and start server
    server = ClaudeAPIServer(claude_api)

    # Run the web server
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

    logger.info("Claude Session API running on http://0.0.0.0:8080")
    logger.info("Endpoints:")
    logger.info("  POST /api/chat - Send message to Claude")
    logger.info("  GET /api/status - Check API status")

    # Keep running
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())