#!/usr/bin/env python3
"""Minimal API Server using Claude CLI."""

import asyncio
import json
import logging
import subprocess
import tempfile
import os
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClaudeCLIHandler:
    """Handle messages using Claude CLI."""

    def __init__(self):
        """Initialize and set up authentication."""
        self._setup_auth()

    def _setup_auth(self):
        """Set up Claude CLI authentication using auth file."""
        # Claude CLI expects auth data in ~/.config/@anthropic-ai/claude-code/auth.json
        auth_source = '/home/claude/.claude-auth.json'
        auth_dest_dir = '/home/claude/.config/@anthropic-ai/claude-code'
        auth_dest = f'{auth_dest_dir}/auth.json'

        if os.path.exists(auth_source):
            try:
                # Create directory if it doesn't exist
                os.makedirs(auth_dest_dir, exist_ok=True)

                # Copy auth file to where Claude CLI expects it
                with open(auth_source, 'r') as f:
                    auth_data = json.load(f)

                # Write to Claude CLI's expected location
                with open(auth_dest, 'w') as f:
                    json.dump(auth_data, f)

                # Also set environment variable as backup
                if 'claudeAiOauth' in auth_data:
                    oauth_token = auth_data['claudeAiOauth'].get('accessToken', '')
                    if oauth_token:
                        os.environ['CLAUDE_CODE_OAUTH_TOKEN'] = oauth_token
                        logger.info("Claude CLI auth configured successfully")
                    else:
                        logger.warning("No access token found in auth file")
                else:
                    logger.warning("Auth file doesn't contain claudeAiOauth data")
            except Exception as e:
                logger.error(f"Failed to set up authentication: {e}")
        else:
            logger.warning(f"No auth file found at {auth_source}")

    async def send_message(self, messages, **kwargs):
        """Send messages to Claude CLI and get response."""
        try:
            # Get the last user message
            last_message = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_message = msg.get("content", "")
                    break

            # Use the Claude CLI to get a response
            # Create a temp file with the message
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(last_message)
                temp_file = f.name

            try:
                # Call Claude CLI
                # Note: This assumes the container has auth configured
                result = await asyncio.create_subprocess_exec(
                    'claude', 'chat', '--file', temp_file,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = await result.communicate()

                if result.returncode == 0:
                    response_text = stdout.decode('utf-8').strip()
                else:
                    logger.error(f"Claude CLI error: {stderr.decode('utf-8')}")
                    response_text = "I'm having trouble connecting to Claude. Please ensure authentication is configured."

            finally:
                # Clean up temp file
                os.unlink(temp_file)

            return {
                "id": f"msg_{os.urandom(8).hex()}",
                "role": "assistant",
                "content": response_text,
                "model": "claude-cli",
                "usage": {
                    "input_tokens": len(last_message.split()),
                    "output_tokens": len(response_text.split())
                }
            }

        except Exception as e:
            logger.error(f"Error calling Claude CLI: {e}")
            return {
                "id": "msg_error",
                "role": "assistant",
                "content": f"Error: {str(e)}",
                "model": "claude-cli",
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }


# Global handler instance
handler = ClaudeCLIHandler()


async def handle_chat(request):
    """Handle chat API requests."""
    try:
        data = await request.json()
        messages = data.get("messages", [])

        # Remove messages from data to avoid duplicate argument
        params = {k: v for k, v in data.items() if k != "messages"}
        response = await handler.send_message(messages, **params)

        # Stream response if requested
        if data.get("stream", False):
            # Return as SSE stream
            async def stream_response():
                # Send chunks
                chunks = response["content"].split(". ")
                for chunk in chunks:
                    event_data = {
                        "id": response["id"],
                        "role": "assistant",
                        "content": chunk + ". " if chunk != chunks[-1] else chunk,
                        "model": response["model"]
                    }
                    yield f"data: {json.dumps(event_data)}\n\n".encode()
                    await asyncio.sleep(0.05)

                # Send final usage data
                yield f"data: {json.dumps({'usage': response['usage']})}\n\n".encode()

            return web.Response(
                body=stream_response(),
                content_type="text/event-stream",
                headers={"Cache-Control": "no-cache"}
            )
        else:
            return web.json_response(response)

    except Exception as e:
        logger.error(f"Error handling chat request: {e}")
        return web.json_response(
            {"error": str(e)},
            status=500
        )


async def handle_health(request):
    """Health check endpoint."""
    return web.json_response({
        "status": "healthy",
        "ready": True,
        "container": "claude-cli-docker"
    })


def create_app():
    """Create the web application."""
    app = web.Application()

    # Routes
    app.router.add_post("/api/chat", handle_chat)
    app.router.add_get("/health", handle_health)

    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=8000)