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

    if settings.openai_api_key:
        openai = OpenAICompatProvider(
            name="openai",
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
        )
        llm_registry.register(openai, is_default=(settings.default_provider == "openai"))

    if settings.anthropic_api_key:
        from helperai.llm.anthropic_provider import AnthropicProvider

        anthropic = AnthropicProvider(api_key=settings.anthropic_api_key)
        llm_registry.register(
            anthropic, is_default=(settings.default_provider == "anthropic")
        )

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

    # --- Wire up deps ---
    from helperai.api.deps import set_services

    set_services(agent_manager, event_bus, llm_registry, tool_registry, approval_manager)

    yield

    # --- Shutdown ---
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
