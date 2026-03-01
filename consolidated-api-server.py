#!/usr/bin/env python3
"""
Consolidated API Server for AshAI
Combines:
- Backend API (port 8000)
- CLI Terminal Controller (port 8081)
- Multi-Provider Proxy (port 8082)
Into a single unified service on port 8000
"""

import asyncio
import logging
import os
import sys
import subprocess
import shutil
from aiohttp import web
import aiohttp
import json
from typing import Optional

# Add the app directory to path for helperai imports
sys.path.insert(0, '/app')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CLI Agent Controller Configuration
# ---------------------------------------------------------------------------
MODEL_TO_CLI = {
    # Claude models - using CLI's expected names
    "sonnet":   "claude",
    "opus":     "claude",
    "haiku":    "claude",
    # Gemini models
    "gemini-2.5-pro":    "gemini",
    "gemini-2.5-flash":  "gemini",
    "gemini-2.0-flash":  "gemini",
}

CLI_CONFIGS = {
    "claude": {
        "binary": "claude",
        "possible_paths": [
            "/home/claude/.local/bin/claude",
            "/usr/local/bin/claude",
        ],
        "auto_approve_flags": ["--dangerously-skip-permissions"],
        "model_flag": "--model",
        "print_flag": "-p",
    },
    "gemini": {
        "binary": "gemini",
        "possible_paths": [
            "/usr/local/bin/gemini",
        ],
        "auto_approve_flags": ["--yolo"],
        "model_flag": "-m",
        "print_flag": "-p",
        "prompt_via_flag": True,
    },
}

class CLIAgentController:
    """Handles CLI agent operations"""

    def __init__(self):
        self.installed_clis: dict[str, str] = {}
        self.scan_clis()

    def scan_clis(self):
        """Check which CLIs are actually available on this system."""
        self.installed_clis = {}
        for cli_name, cfg in CLI_CONFIGS.items():
            path = self._find_binary(cli_name, cfg)
            if path:
                self.installed_clis[cli_name] = path
                logger.info("CLI '%s' found at %s", cli_name, path)
            else:
                logger.info("CLI '%s' not found", cli_name)

    def _find_binary(self, cli_name: str, cfg: dict) -> Optional[str]:
        for p in cfg["possible_paths"]:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
        found = shutil.which(cfg["binary"])
        if found:
            return found
        return None

    def available_models(self) -> list[dict]:
        """Return models whose CLI is installed."""
        models = []
        for model, cli_name in MODEL_TO_CLI.items():
            if cli_name in self.installed_clis:
                models.append({
                    "id": model,
                    "cli": cli_name,
                    "binary": self.installed_clis[cli_name],
                })
        return models

    async def send_message(self, model: str, message: str) -> str:
        """Run the appropriate CLI for model and return its stdout."""
        cli_name = MODEL_TO_CLI.get(model)
        if cli_name is None:
            return f"Error: unknown model '{model}'. Known models: {list(MODEL_TO_CLI.keys())}"

        if cli_name not in self.installed_clis:
            return f"Error: CLI '{cli_name}' is not installed. Cannot run model '{model}'."

        binary = self.installed_clis[cli_name]
        cfg = CLI_CONFIGS[cli_name]

        cmd = [binary] + cfg["auto_approve_flags"]
        cmd += [cfg["model_flag"], model]

        stdin_input = None
        if cfg.get("print_flag"):
            if cfg.get("prompt_via_flag"):
                cmd += [cfg["print_flag"], message]
            else:
                cmd.append(cfg["print_flag"])
                stdin_input = message

        logger.info("Running: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                input=stdin_input,
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                error = result.stderr.strip() or "Unknown error"
                logger.error("CLI %s error (rc=%d): %s", cli_name, result.returncode, error)
                return f"Error: {error}"

        except subprocess.TimeoutExpired:
            return "Error: Request timed out (600 s)"
        except Exception as e:
            logger.error("Exception running %s: %s", cli_name, e)
            return f"Error: {e}"

# ---------------------------------------------------------------------------
# Multi-Provider Proxy
# ---------------------------------------------------------------------------
class MultiProviderProxy:
    """Handles proxying to various LLM providers"""

    def __init__(self):
        self.providers = {
            "anthropic": {
                "base_url": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
                "api_key": os.getenv("ANTHROPIC_API_KEY"),
            },
            "openai": {
                "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                "api_key": os.getenv("OPENAI_API_KEY"),
            },
            "gemini": {
                "base_url": os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com"),
                "api_key": os.getenv("GEMINI_API_KEY"),
            },
            "ollama": {
                "base_url": os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
                "api_key": None,
            },
        }

    async def proxy_request(self, request: web.Request, provider: str, path: str) -> web.Response:
        """Proxy a request to the specified provider"""
        if provider not in self.providers:
            return web.json_response({"error": f"Unknown provider: {provider}"}, status=404)

        config = self.providers[provider]
        if provider != "ollama" and not config["api_key"]:
            return web.json_response({"error": f"No API key configured for {provider}"}, status=401)

        # Build target URL
        target_url = f"{config['base_url']}{path}"

        # Prepare headers
        headers = dict(request.headers)
        headers.pop("Host", None)
        headers.pop("Content-Length", None)

        # Handle API key
        if request.headers.get("x-api-key") == "proxy":
            if config["api_key"]:
                if provider == "anthropic":
                    headers["x-api-key"] = config["api_key"]
                elif provider == "openai":
                    headers["Authorization"] = f"Bearer {config['api_key']}"
                elif provider == "gemini":
                    target_url += f"?key={config['api_key']}"

        # Forward the request
        async with aiohttp.ClientSession() as session:
            try:
                body = await request.read() if request.body_exists else None

                async with session.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    data=body,
                    timeout=aiohttp.ClientTimeout(total=600)
                ) as resp:
                    response_body = await resp.read()
                    return web.Response(
                        body=response_body,
                        status=resp.status,
                        headers=resp.headers
                    )
            except Exception as e:
                logger.error(f"Proxy error for {provider}: {e}")
                return web.json_response({"error": str(e)}, status=500)

# ---------------------------------------------------------------------------
# Consolidated API Server
# ---------------------------------------------------------------------------
class ConsolidatedAPIServer:
    """Main consolidated API server"""

    def __init__(self):
        self.cli_controller = CLIAgentController()
        self.proxy = MultiProviderProxy()
        self.backend_app = None
        self.backend_runner = None

    async def start_backend(self):
        """Start the helperai backend API"""
        try:
            # Import and start helperai
            from helperai import create_app
            from helperai.config import get_settings

            settings = get_settings()
            self.backend_app = create_app(settings)

            # Create runner but don't bind to port (we'll mount it)
            self.backend_runner = web.AppRunner(self.backend_app)
            await self.backend_runner.setup()

            logger.info("Backend API initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to start backend: {e}")
            return False

    # CLI Controller Handlers
    async def handle_cli_status(self, request):
        self.cli_controller.scan_clis()
        return web.json_response({
            "installed_clis": list(self.cli_controller.installed_clis.keys()),
            "models": [m["id"] for m in self.cli_controller.available_models()],
            "ready": bool(self.cli_controller.installed_clis),
        })

    async def handle_cli_models(self, request):
        return web.json_response(self.cli_controller.available_models())

    async def handle_cli_chat(self, request):
        try:
            data = await request.json()
            model = data.get("model")
            message = data.get("message")

            if not model or not message:
                return web.json_response({
                    "success": False,
                    "error": "Missing 'model' or 'message' in request"
                }, status=400)

            result = await self.cli_controller.send_message(model, message)

            if result.startswith("Error:"):
                return web.json_response({
                    "success": False,
                    "error": result
                }, status=503)

            return web.json_response({
                "success": True,
                "response": result
            })

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    # Proxy health check
    async def handle_proxy_health(self, request):
        """Health check for proxy"""
        providers_status = {}
        for name, config in self.proxy.providers.items():
            providers_status[name] = {
                "configured": bool(config.get("api_key")) if name != "ollama" else True,
                "url": config["base_url"],
                "key_hint": config["api_key"][-4:] if config.get("api_key") else None
            }

        return web.json_response({
            "status": "ok",
            "providers": providers_status
        })

    async def create_app(self):
        """Create the main aiohttp application"""
        app = web.Application()

        # CLI Controller routes (legacy /api prefix for compatibility)
        app.router.add_get("/api/status", self.handle_cli_status)
        app.router.add_get("/api/models", self.handle_cli_models)
        app.router.add_post("/api/chat", self.handle_cli_chat)

        # Proxy routes
        app.router.add_get("/proxy/health", self.handle_proxy_health)

        # Provider proxy routes
        async def proxy_anthropic(request):
            path = "/" + request.match_info.get("path", "")
            return await self.proxy.proxy_request(request, "anthropic", path)

        async def proxy_openai(request):
            path = "/" + request.match_info.get("path", "")
            return await self.proxy.proxy_request(request, "openai", path)

        async def proxy_gemini(request):
            path = "/" + request.match_info.get("path", "")
            return await self.proxy.proxy_request(request, "gemini", path)

        async def proxy_ollama(request):
            path = "/" + request.match_info.get("path", "")
            return await self.proxy.proxy_request(request, "ollama", path)

        # Legacy proxy route (defaults to anthropic)
        async def proxy_legacy(request):
            path = request.path
            return await self.proxy.proxy_request(request, "anthropic", path)

        app.router.add_route("*", "/anthropic/{path:.*}", proxy_anthropic)
        app.router.add_route("*", "/openai/{path:.*}", proxy_openai)
        app.router.add_route("*", "/gemini/{path:.*}", proxy_gemini)
        app.router.add_route("*", "/ollama/{path:.*}", proxy_ollama)

        # Mount backend API if available
        if await self.start_backend():
            # Forward all /api/* routes to backend (except the CLI controller ones above)
            async def forward_to_backend(request):
                if self.backend_runner and self.backend_runner.server:
                    # Create a sub-request to the backend app
                    handler = self.backend_app.make_handler()
                    return await handler(request)
                return web.json_response({"error": "Backend not available"}, status=503)

            # Add specific backend routes
            app.router.add_route("*", "/api/agents", forward_to_backend)
            app.router.add_route("*", "/api/agents/{path:.*}", forward_to_backend)
            app.router.add_route("*", "/api/health", forward_to_backend)
            app.router.add_route("*", "/api/providers", forward_to_backend)
            app.router.add_route("*", "/api/providers/{path:.*}", forward_to_backend)

        # Legacy compatibility - proxy all other paths to anthropic
        app.router.add_route("*", "/{path:.*}", proxy_legacy)

        return app

async def main():
    server = ConsolidatedAPIServer()
    app = await server.create_app()

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("CONSOLIDATED_PORT", "8000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"""
    ========================================
    Consolidated API Server running on port {port}
    ========================================
    Backend API:       http://0.0.0.0:{port}/api/*
    CLI Controller:    http://0.0.0.0:{port}/api/status, /api/models, /api/chat
    Proxy Health:      http://0.0.0.0:{port}/proxy/health
    Provider Proxies:
      - Anthropic:     http://0.0.0.0:{port}/anthropic/*
      - OpenAI:        http://0.0.0.0:{port}/openai/*
      - Gemini:        http://0.0.0.0:{port}/gemini/*
      - Ollama:        http://0.0.0.0:{port}/ollama/*
    ========================================
    """)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())