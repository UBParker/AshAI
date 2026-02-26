#!/usr/bin/env python3
"""
Generic CLI Agent Controller — one API, many CLI backends.

Runs on port 8081 inside Docker. Maps model names to the right CLI binary
(claude, gemini, etc.) and executes them via subprocess.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess

from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model → CLI mapping
# ---------------------------------------------------------------------------
MODEL_TO_CLI = {
    # Claude models
    "claude-sonnet-4":   "claude",
    "claude-opus-4":     "claude",
    "claude-haiku-3.5":  "claude",
    # Gemini models
    "gemini-2.5-pro":    "gemini",
    "gemini-2.5-flash":  "gemini",
    "gemini-2.0-flash":  "gemini",
}

# ---------------------------------------------------------------------------
# Per-CLI configuration
# ---------------------------------------------------------------------------
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
    """Discovers installed CLIs and dispatches chat requests."""

    def __init__(self):
        # cli_name -> resolved binary path
        self.installed_clis: dict[str, str] = {}
        self.scan_clis()

    # ---- discovery --------------------------------------------------------

    def scan_clis(self):
        """Check which CLIs are actually available on this system."""
        self.installed_clis = {}
        for cli_name, cfg in CLI_CONFIGS.items():
            path = self._find_binary(cli_name, cfg)
            if path:
                self.installed_clis[cli_name] = path
                logger.info("CLI '%s' found at %s", cli_name, path)
            else:
                logger.info("CLI '%s' not found — its models will be unavailable", cli_name)

    def _find_binary(self, cli_name: str, cfg: dict) -> str | None:
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

    # ---- execution --------------------------------------------------------

    async def send_message(self, model: str, message: str) -> str:
        """Run the appropriate CLI for *model* and return its stdout."""
        cli_name = MODEL_TO_CLI.get(model)
        if cli_name is None:
            return f"Error: unknown model '{model}'. Known models: {list(MODEL_TO_CLI.keys())}"

        if cli_name not in self.installed_clis:
            return f"Error: CLI '{cli_name}' is not installed. Cannot run model '{model}'."

        binary = self.installed_clis[cli_name]
        cfg = CLI_CONFIGS[cli_name]

        cmd = [binary] + cfg["auto_approve_flags"]

        # Add model selection flag
        cmd += [cfg["model_flag"], model]

        # Add print/prompt flag for non-interactive mode
        # Claude: -p is a standalone flag, prompt comes via stdin
        # Gemini: -p takes the prompt as its argument value
        stdin_input = None
        if cfg.get("print_flag"):
            if cfg.get("prompt_via_flag"):
                cmd += [cfg["print_flag"], message]
            else:
                cmd.append(cfg["print_flag"])
                stdin_input = message

        logger.info("Running: %s  (input length=%d)", " ".join(cmd), len(message))

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
# HTTP handlers
# ---------------------------------------------------------------------------
controller = CLIAgentController()


async def handle_status(request):
    controller.scan_clis()
    return web.json_response({
        "installed_clis": list(controller.installed_clis.keys()),
        "models": [m["id"] for m in controller.available_models()],
        "ready": bool(controller.installed_clis),
    })


async def handle_models(request):
    return web.json_response(controller.available_models())


async def handle_chat(request):
    try:
        data = await request.json()
        model = data.get("model", "")
        message = data.get("message", "")

        if not model:
            return web.json_response({"error": "model is required"}, status=400)
        if not message:
            return web.json_response({"error": "message is required"}, status=400)

        response = await controller.send_message(model, message)

        if response.startswith("Error:"):
            status = 503 if ("not installed" in response or "unknown model" in response) else 500
            return web.json_response({"success": False, "error": response}, status=status)

        return web.json_response({"success": True, "response": response})

    except Exception as e:
        logger.error("Chat error: %s", e)
        return web.json_response({"error": str(e)}, status=500)


async def main():
    app = web.Application()
    app.router.add_get("/api/status", handle_status)
    app.router.add_get("/api/models", handle_models)
    app.router.add_post("/api/chat", handle_chat)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8081)
    await site.start()

    logger.info("CLI Agent Controller running on http://0.0.0.0:8081")
    logger.info("  GET  /api/status  — installed CLIs & available models")
    logger.info("  GET  /api/models  — list available models")
    logger.info("  POST /api/chat    — {model, message}")
    logger.info("Installed CLIs: %s", list(controller.installed_clis.keys()))

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
