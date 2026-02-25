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
        self.claude_path = '/home/claude/.local/bin/claude'  # Set the correct path for claude user
        self.check_installation()

    def check_installation(self):
        """Check if Claude Code CLI is installed"""
        import os

        # Priority order: check /home/claude/.local/bin first (official install location for claude user)
        possible_paths = [
            '/home/claude/.local/bin/claude',
            '/usr/local/bin/claude',
            shutil.which('claude')
        ]

        claude_path = None
        for path in possible_paths:
            if path and os.path.exists(path):
                # Verify it's executable
                if os.access(path, os.X_OK):
                    claude_path = path
                    break

        if claude_path:
            self.claude_installed = True
            self.claude_path = claude_path
            logger.info(f"Claude Code CLI is installed at {claude_path}")
            self.check_authentication()
        else:
            self.claude_path = 'claude'
            logger.info("Claude Code CLI not installed yet")
            logger.info("To install: curl -fsSL https://claude.ai/install.sh | sh")

    def check_authentication(self):
        """Check if Claude Code CLI is authenticated"""
        if not self.claude_installed:
            return

        try:
            # Try running a simple claude command
            result = subprocess.run(
                [self.claude_path, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Check if actually authenticated by trying a simple echo
                # The new Claude CLI will error if not authenticated
                test_result = subprocess.run(
                    f"echo 'test' | {self.claude_path}",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                # Check for common auth error messages
                error_indicators = ['not authenticated', 'please authenticate', 'auth required', 'login required']
                has_error = any(indicator in test_result.stderr.lower() for indicator in error_indicators)

                if test_result.returncode == 0 and not has_error:
                    self.authenticated = True
                    logger.info("Claude Code CLI is authenticated")
                else:
                    logger.info("Claude Code CLI installed but not authenticated")
                    if test_result.stderr:
                        logger.info(f"Auth check output: {test_result.stderr[:200]}")
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
            # Send message via Claude CLI using stdin
            logger.info(f"Sending to Claude: {message[:50]}...")

            result = subprocess.run(
                [self.claude_path, '--dangerously-skip-permissions'],
                input=message,
                capture_output=True,
                text=True,
                timeout=600
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