#!/usr/bin/env python3
"""Direct Claude API using OAuth tokens from subscription."""

import os
import json
import asyncio
import aiohttp
import logging
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClaudeOAuthHandler:
    """Handle messages using Claude OAuth API directly."""

    def __init__(self):
        """Initialize and load OAuth credentials."""
        self.access_token = None
        self._load_oauth_token()

    def _load_oauth_token(self):
        """Load OAuth token from mounted file."""
        auth_file = '/home/claude/.claude-auth.json'
        if os.path.exists(auth_file):
            try:
                with open(auth_file, 'r') as f:
                    auth_data = json.load(f)

                if 'claudeAiOauth' in auth_data:
                    self.access_token = auth_data['claudeAiOauth'].get('accessToken', '')
                    if self.access_token:
                        logger.info("OAuth token loaded successfully")
                    else:
                        logger.warning("No access token found in auth file")
                else:
                    logger.warning("Auth file doesn't contain claudeAiOauth data")
            except Exception as e:
                logger.error(f"Failed to load OAuth token: {e}")
        else:
            logger.warning(f"No auth file found at {auth_file}")

    async def send_message(self, messages, **kwargs):
        """Send messages to Claude using OAuth API."""
        if not self.access_token:
            return {
                "id": "msg_error",
                "role": "assistant",
                "content": "Authentication not configured. Please provide OAuth token.",
                "model": "claude-subscription"
            }

        try:
            # Try the Anthropic API endpoint with OAuth token
            url = "https://api.anthropic.com/v1/messages"

            # Format messages for Anthropic API
            conversation = []
            for msg in messages:
                if msg.get("role") == "user":
                    conversation.append({
                        "role": "user",
                        "content": msg.get("content", "")
                    })
                elif msg.get("role") == "assistant":
                    conversation.append({
                        "role": "assistant",
                        "content": msg.get("content", "")
                    })

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
                "User-Agent": "Claude-Code-Docker/1.0"
            }

            payload = {
                "messages": conversation,
                "model": "claude-sonnet-4-6",
                "max_tokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.7)
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Extract content from Anthropic API response
                        content = ""
                        if "content" in data and isinstance(data["content"], list):
                            for block in data["content"]:
                                if block.get("type") == "text":
                                    content += block.get("text", "")
                        return {
                            "id": data.get("id", f"msg_{os.urandom(8).hex()}"),
                            "role": "assistant",
                            "content": content,
                            "model": "claude-subscription",
                            "usage": data.get("usage", {
                                "input_tokens": len(str(conversation).split()),
                                "output_tokens": len(content.split())
                            })
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"API error: {response.status} - {error_text}")
                        return {
                            "id": "msg_error",
                            "role": "assistant",
                            "content": f"API error: {response.status} - Check logs for details",
                            "model": "claude-subscription"
                        }

        except Exception as e:
            logger.error(f"Error calling Claude OAuth API: {e}")
            return {
                "id": "msg_error",
                "role": "assistant",
                "content": f"Error: {str(e)}",
                "model": "claude-subscription"
            }


# Global handler instance
handler = ClaudeOAuthHandler()


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
                content = response.get("content", "")
                chunks = content.split(". ")
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
                yield f"data: {json.dumps({'usage': response.get('usage', {})})}\n\n".encode()

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
        "container": "claude-oauth-docker",
        "authenticated": handler.access_token is not None
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