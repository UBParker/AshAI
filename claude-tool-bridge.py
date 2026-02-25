#!/usr/bin/env python3
"""
Tool Bridge Server for Claude CLI in Docker container.
Allows Claude CLI to request tool execution from the host AshAI system.
"""

import asyncio
import json
import logging
from aiohttp import web
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClaudeToolBridge:
    """Bridge between Claude CLI in container and AshAI tool system on host"""

    def __init__(self):
        self.pending_tool_requests = {}
        self.tool_responses = {}
        self.request_counter = 0

    async def request_tool_execution(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Store a tool execution request for AshAI to pick up"""
        self.request_counter += 1
        request_id = f"tool_req_{self.request_counter}"

        self.pending_tool_requests[request_id] = {
            "id": request_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "status": "pending"
        }

        logger.info(f"Tool request {request_id}: {tool_name} with args {arguments}")

        # Wait for response (with timeout)
        max_wait = 30  # seconds
        for _ in range(max_wait * 10):  # Check every 100ms
            await asyncio.sleep(0.1)
            if request_id in self.tool_responses:
                response = self.tool_responses.pop(request_id)
                del self.pending_tool_requests[request_id]
                return response

        # Timeout
        if request_id in self.pending_tool_requests:
            del self.pending_tool_requests[request_id]
        return f"Tool execution timeout for {tool_name}"


# Global bridge instance
bridge = ClaudeToolBridge()


async def handle_tool_request(request):
    """Handle tool execution request from Claude CLI"""
    try:
        data = await request.json()
        tool_name = data.get("tool_name")
        arguments = data.get("arguments", {})

        if not tool_name:
            return web.json_response({"error": "tool_name required"}, status=400)

        # Request tool execution and wait for response
        result = await bridge.request_tool_execution(tool_name, arguments)

        return web.json_response({
            "success": True,
            "result": result
        })

    except Exception as e:
        logger.error(f"Tool request error: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_pending_requests(request):
    """Get pending tool requests for AshAI to execute"""
    return web.json_response({
        "pending": list(bridge.pending_tool_requests.values())
    })


async def handle_tool_response(request):
    """Receive tool execution response from AshAI"""
    try:
        data = await request.json()
        request_id = data.get("request_id")
        response = data.get("response")

        if not request_id or response is None:
            return web.json_response({"error": "request_id and response required"}, status=400)

        if request_id in bridge.pending_tool_requests:
            bridge.tool_responses[request_id] = response
            bridge.pending_tool_requests[request_id]["status"] = "completed"
            return web.json_response({"success": True})
        else:
            return web.json_response({"error": "Unknown request_id"}, status=404)

    except Exception as e:
        logger.error(f"Tool response error: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_claude_helper(request):
    """Provide a helper script for Claude CLI to use"""
    helper_script = '''#!/usr/bin/env python3
"""Helper script for Claude CLI to call AshAI tools"""
import sys
import json
import requests

def call_tool(tool_name, **kwargs):
    """Call an AshAI tool through the bridge"""
    response = requests.post(
        "http://localhost:8082/api/tool/request",
        json={"tool_name": tool_name, "arguments": kwargs}
    )
    if response.status_code == 200:
        return response.json().get("result", "Tool executed")
    else:
        return f"Error calling {tool_name}: {response.text}"

# Tool wrapper functions
def spawn_agent(name, role, model="claude-terminal", persona="A helpful AI assistant"):
    """Spawn a new AI agent"""
    return call_tool("spawn_agent", name=name, role=role, model=model, persona=persona)

def list_agents():
    """List all active agents"""
    return call_tool("list_agents")

def message_agent(agent_id, message):
    """Send a message to an agent"""
    return call_tool("message_agent", agent_id=agent_id, message=message)

def report_to_eve(message):
    """Report to Eve"""
    return call_tool("report_to_eve", message=message)

if __name__ == "__main__":
    print("AshAI Tool Helper loaded")
    print("Available functions: spawn_agent, list_agents, message_agent, report_to_eve")
'''

    return web.Response(text=helper_script, content_type="text/plain")


async def main():
    """Start the tool bridge server"""
    app = web.Application()

    # Endpoints for Claude CLI in container
    app.router.add_post('/api/tool/request', handle_tool_request)
    app.router.add_get('/api/tool/helper', handle_claude_helper)

    # Endpoints for AshAI on host
    app.router.add_get('/api/tool/pending', handle_pending_requests)
    app.router.add_post('/api/tool/response', handle_tool_response)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8082)
    await site.start()

    logger.info("Claude Tool Bridge running on http://0.0.0.0:8082")
    logger.info("Endpoints:")
    logger.info("  POST /api/tool/request - Request tool execution (from Claude CLI)")
    logger.info("  GET /api/tool/helper - Get helper script for Claude CLI")
    logger.info("  GET /api/tool/pending - Get pending tool requests (for AshAI)")
    logger.info("  POST /api/tool/response - Submit tool response (from AshAI)")

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())