#!/usr/bin/env python3
"""
Terminal controller API for manual Claude Code CLI setup
Provides instructions and status checking
"""

import asyncio
import json
import logging
import subprocess
import shutil
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClaudeTerminalController:
    """Manages Claude Code CLI setup and execution"""

    def __init__(self):
        self.claude_installed = False
        self.authenticated = False
        self.check_installation()

    def check_installation(self):
        """Check if Claude Code CLI is installed"""
        # Check if 'claude' command exists
        if shutil.which('claude'):
            self.claude_installed = True
            logger.info("Claude Code CLI is installed")
            self.check_authentication()
        else:
            logger.info("Claude Code CLI not installed yet")
            logger.info("To install: npm install -g @anthropics/claude-code")

    def check_authentication(self):
        """Check if Claude Code CLI is authenticated"""
        if not self.claude_installed:
            return

        try:
            # Try running a simple claude command
            result = subprocess.run(
                ['claude', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Check if actually authenticated by trying to send a test message
                test_result = subprocess.run(
                    ['claude', 'chat', '--message', 'test'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if test_result.returncode == 0 and 'not authenticated' not in test_result.stderr.lower():
                    self.authenticated = True
                    logger.info("Claude Code CLI is authenticated")
                else:
                    logger.info("Claude Code CLI installed but not authenticated")
        except Exception as e:
            logger.error(f"Error checking authentication: {e}")

    async def send_message(self, message: str) -> str:
        """Send a message to Claude via CLI"""
        if not self.claude_installed:
            return "Error: Claude Code CLI not installed. Run: npm install -g @anthropics/claude-code"

        if not self.authenticated:
            self.check_authentication()
            if not self.authenticated:
                return "Error: Claude Code CLI not authenticated. Run: claude auth"

        try:
            # Send message via Claude CLI
            cmd = ['claude', 'chat', '--message', message]

            logger.info(f"Sending to Claude: {message[:50]}...")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                error = result.stderr.strip() or "Unknown error"
                logger.error(f"Claude error: {error}")
                return f"Error: {error}"

        except subprocess.TimeoutExpired:
            return "Error: Request timed out"
        except Exception as e:
            logger.error(f"Error: {e}")
            return f"Error: {str(e)}"


# API Server
controller = ClaudeTerminalController()

async def handle_status(request):
    """Check installation and authentication status"""
    controller.check_installation()

    status = {
        'claude_installed': controller.claude_installed,
        'authenticated': controller.authenticated,
        'provider': 'claude_terminal'
    }

    if not controller.claude_installed:
        status['message'] = 'Claude Code CLI not installed. Run: npm install -g @anthropics/claude-code'
    elif not controller.authenticated:
        status['message'] = 'Claude Code CLI installed but not authenticated. Run: claude auth'
    else:
        status['message'] = 'Ready to use Claude Code CLI'

    return web.json_response(status)

async def handle_chat(request):
    """Send message to Claude"""
    try:
        data = await request.json()
        message = data.get('message', '')

        if not message:
            return web.json_response({'error': 'Message required'}, status=400)

        # Send message and get response
        response = await controller.send_message(message)

        # Check for errors in response
        if response.startswith("Error:"):
            return web.json_response({
                'success': False,
                'error': response
            }, status=503 if "not installed" in response or "not authenticated" in response else 500)

        return web.json_response({
            'success': True,
            'response': response
        })

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def main():
    """Start the API server"""
    app = web.Application()
    app.router.add_get('/api/status', handle_status)
    app.router.add_post('/api/chat', handle_chat)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8081)
    await site.start()

    logger.info("Claude Terminal Controller API running on http://0.0.0.0:8081")
    logger.info("Endpoints:")
    logger.info("  GET /api/status - Check auth status")
    logger.info("  POST /api/chat - Send message to Claude")
    logger.info("")
    logger.info("Please ensure Claude Code CLI is authenticated:")
    logger.info("  1. Open terminal")
    logger.info("  2. Run: claude auth")
    logger.info("  3. Follow authentication steps")

    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())