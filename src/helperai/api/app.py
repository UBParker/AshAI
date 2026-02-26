"""FastAPI application factory."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from helperai.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all services on startup, clean up on shutdown."""
    settings = get_settings()

    # --- Database ---
    from helperai.db.engine import close_db, init_db

    await init_db()
    logger.info("Database initialized")

    # Reset any agents stuck in "running" from a previous crash
    from sqlalchemy import update
    from helperai.db.engine import get_session_factory
    from helperai.db.models import Agent as AgentModel

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            update(AgentModel)
            .where(AgentModel.status == "running")
            .values(status="idle")
        )
        if result.rowcount:
            logger.info("Reset %d stale 'running' agents to 'idle'", result.rowcount)
        await session.commit()

    # --- Event Bus ---
    from helperai.core.events import EventBus

    event_bus = EventBus()

    # --- LLM Registry ---
    from helperai.llm.openai_compat import OpenAICompatProvider
    from helperai.llm.registry import LLMRegistry

    llm_registry = LLMRegistry()

    # Register builtin providers from settings
    if settings.ollama_base_url:
        # Ollama uses OpenAI-compatible /v1 endpoint
        ollama = OpenAICompatProvider(
            name="ollama",
            base_url=settings.ollama_base_url + "/v1",
            api_key="ollama",
        )
        llm_registry.register(ollama, is_default=(settings.default_provider == "ollama"))

    if settings.openai_api_key.get_secret_value():
        # base_url defaults to https://api.openai.com/v1 but can be overridden
        # to route through the multi-provider proxy:
        #   HELPERAI_OPENAI_BASE_URL=http://localhost:8082/openai
        #   HELPERAI_OPENAI_API_KEY=proxy  (proxy injects real key)
        openai = OpenAICompatProvider(
            name="openai",
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key.get_secret_value(),
        )
        llm_registry.register(openai, is_default=(settings.default_provider == "openai"))

    # Register Gemini if key is set (or provider is requested)
    _need_gemini = (
        settings.default_provider == "gemini"
        or settings.eve_provider == "gemini"
        or settings.gemini_api_key.get_secret_value()
    )
    if _need_gemini:
        from helperai.llm.gemini_provider import GeminiProvider

        # base_url can be overridden to route through the multi-provider proxy:
        #   HELPERAI_GEMINI_BASE_URL=http://localhost:8082/gemini
        #   HELPERAI_GEMINI_API_KEY=proxy  (proxy injects real key via ?key=)
        gemini = GeminiProvider(
            name="gemini",
            base_url=settings.gemini_base_url,
            api_key=settings.gemini_api_key.get_secret_value(),
        )
        llm_registry.register(gemini, is_default=(settings.default_provider == "gemini"))
        logger.info("Gemini provider registered (base_url=%s)", settings.gemini_base_url)

    # Register Anthropic if it's the default, eve_provider, or has an API key
    _need_anthropic = (
        settings.default_provider == "anthropic"
        or settings.eve_provider == "anthropic"
        or settings.anthropic_api_key.get_secret_value()
    )
    if _need_anthropic:
        from helperai.llm.anthropic_provider import AnthropicProvider

        # Use custom base_url if set (e.g. proxy inside Docker container)
        _base_url = settings.anthropic_base_url
        if _base_url == "https://api.anthropic.com/v1":
            _base_url = None  # SDK default, no override needed

        anthropic = AnthropicProvider(
            api_key=settings.anthropic_api_key.get_secret_value() or "proxy",
            base_url=_base_url,
        )
        llm_registry.register(
            anthropic, is_default=(settings.default_provider == "anthropic")
        )
        logger.info("Anthropic provider registered (base_url=%s)", _base_url)

    # Register Claude Docker provider if enabled (uses subscription via Docker containers!)
    if settings.claude_code_enabled or settings.default_provider == "claude_docker":
        try:
            from helperai.llm.claude_docker_provider import ClaudeDockerProvider

            claude_docker = ClaudeDockerProvider(
                image_name="ashai-claude-cli",
                max_containers=10
            )
            llm_registry.register(
                claude_docker, is_default=(settings.default_provider == "claude_docker")
            )
            logger.info("Claude Docker provider registered - ALL agents use Docker containers with your subscription!")
            logger.info("Cost: $20/month total for UNLIMITED agents (saving you $580+/month!)")
        except ImportError as e:
            logger.warning(
                f"Claude Docker provider requested but docker library not installed: {e}. "
                "Install with: pip install docker"
            )
        except Exception as e:
            logger.error(f"Failed to register Claude Docker provider: {e}")

    # Register Claude Host provider if enabled (uses host's CLI directly)
    if settings.default_provider == "claude_host":
        try:
            from helperai.llm.claude_host_provider import ClaudeHostProvider

            claude_host = ClaudeHostProvider()
            llm_registry.register(claude_host, is_default=True)
            logger.info("Claude Host provider registered - using host's Claude CLI with your subscription!")
        except Exception as e:
            logger.error(f"Failed to register Claude Host provider: {e}")

    # Register Claude Web Automation provider if credentials are provided
    if settings.claude_web_email and settings.claude_web_password.get_secret_value():
        try:
            from helperai.llm.claude_web_provider import ClaudeWebProvider

            claude_web = ClaudeWebProvider(
                email=settings.claude_web_email,
                password=settings.claude_web_password.get_secret_value(),
                headless=settings.claude_web_headless,
                timeout=settings.claude_web_timeout,
            )
            llm_registry.register(
                claude_web, is_default=(settings.default_provider == "claude_web")
            )
            logger.info("Claude Web Automation provider registered")
        except ImportError:
            logger.warning(
                "Claude Web Automation provider requested but playwright not installed. "
                "Install with: pip install 'helperai[web-automation]'"
            )
        except Exception as e:
            logger.error(f"Failed to register Claude Web Automation provider: {e}")

    # Register CLI Agent provider (wraps Claude CLI, Gemini CLI, etc.)
    _need_cli_agent = (
        settings.default_provider in ("cli_agent", "claude_terminal")
        or settings.eve_provider in ("cli_agent", "claude_terminal")
    )
    if _need_cli_agent:
        try:
            from helperai.llm.cli_agent_provider import CLIAgentProvider

            cli_agent = CLIAgentProvider(
                api_url="http://localhost:8081",
                check_status=True,
            )
            llm_registry.register(
                cli_agent,
                is_default=(settings.default_provider in ("cli_agent", "claude_terminal")),
            )
            logger.info("CLI Agent provider registered — routes to installed CLIs (claude, gemini, …)")
        except Exception as e:
            logger.error(f"Failed to register CLI Agent provider: {e}")

    # Register Claude Session provider if enabled (uses browser cookies)
    if settings.default_provider == "claude_session" or os.path.exists("claude-cookies.json"):
        try:
            from helperai.llm.claude_session_provider import ClaudeSessionProvider

            # Check for custom API URL from environment
            session_api_url = os.getenv("CLAUDE_SESSION_API_URL", "http://localhost:8080")

            claude_session = ClaudeSessionProvider(
                api_url=session_api_url,
                cookies_file="claude-cookies.json"
            )
            llm_registry.register(
                claude_session, is_default=(settings.default_provider == "claude_session")
            )
            logger.info("Claude Session provider registered - using browser cookies with your subscription!")
            logger.info(f"Cost: $20/month total (saving you $560+/month vs API!)")
        except Exception as e:
            logger.error(f"Failed to register Claude Session provider: {e}")

    logger.info("LLM providers registered: %s", llm_registry.list_providers())

    # --- Tool Registry ---
    from helperai.tools.builtin.list_agents import ListAgentsTool
    from helperai.tools.builtin.message_agent import MessageAgentTool
    from helperai.tools.builtin.report_to_eve import ReportToEveTool
    from helperai.tools.builtin.spawn_agent import SpawnAgentTool
    from helperai.tools.registry import ToolRegistry

    tool_registry = ToolRegistry()
    tool_registry.register(SpawnAgentTool())
    tool_registry.register(ListAgentsTool())
    tool_registry.register(MessageAgentTool())
    tool_registry.register(ReportToEveTool())
    logger.info("Tools registered: %s", tool_registry.list_tools())

    # --- Load plugins ---
    from helperai.plugins.loader import load_plugins

    load_plugins(settings.plugins_dir, tool_registry)

    # --- Approval Manager ---
    from helperai.core.approval import ApprovalManager

    approval_manager = ApprovalManager(event_bus=event_bus)

    # --- Agent Manager ---
    from helperai.agents.manager import AgentManager

    agent_manager = AgentManager(
        settings=settings,
        llm_registry=llm_registry,
        tool_registry=tool_registry,
        event_bus=event_bus,
        approval_manager=approval_manager,
    )

    # Initialize Eve
    eve = await agent_manager.init_eve()
    logger.info("Eve initialized: id=%s, model=%s", eve.id, eve.model_name)

    # --- Signal File Monitor ---
    # Start monitoring for signal files from Claude CLI
    signal_monitor = None
    try:
        from helperai.signal_monitor import SignalFileMonitor

        signal_monitor = SignalFileMonitor(
            watch_dir=".",  # Monitor current directory for .ashai_tool_signal.json files
            agent_manager=agent_manager
        )
        signal_monitor.start()
        logger.info("Signal file monitor started - watching for Claude CLI tool signals")
    except ImportError as e:
        logger.warning(f"Signal file monitor not available: {e}. Install with: pip install watchdog aiofiles")

    # --- Wire up deps ---
    from helperai.api.deps import set_services

    set_services(agent_manager, event_bus, llm_registry, tool_registry, approval_manager)

    yield

    # --- Shutdown ---
    # Stop signal file monitor
    if signal_monitor:
        signal_monitor.stop()
        logger.info("Signal file monitor stopped")

    # Clean up Claude Web provider if it exists
    if "claude_web" in llm_registry.list_providers():
        try:
            claude_web_provider = llm_registry.get("claude_web")
            if hasattr(claude_web_provider, "close"):
                await claude_web_provider.close()
        except Exception as e:
            logger.error(f"Error closing Claude Web provider: {e}")

    await close_db()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AshAI",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    from helperai.api.routes import agents, approvals, chat, knowledge, providers, settings, tools, ws

    app.include_router(chat.router)
    app.include_router(agents.router)
    app.include_router(providers.router)
    app.include_router(ws.router)
    app.include_router(approvals.router)
    app.include_router(tools.router)
    app.include_router(settings.router)
    app.include_router(knowledge.router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/instance-info")
    async def instance_info():
        return {
            "instance_type": os.environ.get("HELPERAI_INSTANCE_TYPE", "personal"),
            "project_id": os.environ.get("HELPERAI_PROJECT_ID"),
        }

    return app