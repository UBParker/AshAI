"""Integration tests for the API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from helperai.llm.message_types import StreamChunk


class MockProvider:
    def __init__(self):
        self._name = "test"

    @property
    def name(self):
        return self._name

    async def stream(self, messages, model, **kwargs):
        yield StreamChunk(delta_content="Hi there!")
        yield StreamChunk(finish_reason="stop")

    async def list_models(self):
        return ["test-model"]


@pytest.fixture
async def client():
    """Create a test client with mocked LLM."""
    import helperai.config as cfg
    import helperai.db.engine as eng

    from helperai.config import Settings

    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        default_provider="test",
        default_model="test-model",
        ollama_base_url="",
        eve_model="test-model",
        plugins_dir="__nonexistent__",
    )
    cfg._settings = settings
    eng._engine = None
    eng._session_factory = None

    # Patch the lifespan to use our mock
    from helperai.api.app import create_app

    app = create_app()

    # We need to manually run the lifespan setup with our mock provider
    from helperai.agents.manager import AgentManager
    from helperai.api.deps import set_services
    from helperai.core.events import EventBus
    from helperai.db.engine import init_db
    from helperai.llm.registry import LLMRegistry
    from helperai.tools.builtin.list_agents import ListAgentsTool
    from helperai.tools.builtin.message_agent import MessageAgentTool
    from helperai.tools.builtin.report_to_eve import ReportToEveTool
    from helperai.tools.builtin.spawn_agent import SpawnAgentTool
    from helperai.tools.registry import ToolRegistry

    await init_db()

    event_bus = EventBus()
    llm_registry = LLMRegistry()
    llm_registry.register(MockProvider(), is_default=True)

    tool_registry = ToolRegistry()
    tool_registry.register(SpawnAgentTool())
    tool_registry.register(ListAgentsTool())
    tool_registry.register(MessageAgentTool())
    tool_registry.register(ReportToEveTool())

    manager = AgentManager(settings, llm_registry, tool_registry, event_bus)
    await manager.init_eve()
    set_services(manager, event_bus, llm_registry, tool_registry)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    from helperai.db.engine import close_db

    await close_db()
    cfg._settings = None


async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


async def test_list_agents(client):
    resp = await client.get("/api/agents")
    assert resp.status_code == 200
    agents = resp.json()
    assert len(agents) >= 1
    assert any(a["name"] == "Eve" for a in agents)


async def test_get_agent(client):
    resp = await client.get("/api/agents")
    agents = resp.json()
    eve = next(a for a in agents if a["name"] == "Eve")

    resp = await client.get(f"/api/agents/{eve['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Eve"


async def test_get_agent_not_found(client):
    resp = await client.get("/api/agents/nonexistent")
    assert resp.status_code == 404


async def test_list_providers(client):
    resp = await client.get("/api/providers")
    assert resp.status_code == 200
    providers = resp.json()
    assert any(p["name"] == "test" for p in providers)


async def test_list_models(client):
    resp = await client.get("/api/providers/test/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "test-model" in data["models"]


async def test_provider_not_found(client):
    resp = await client.get("/api/providers/nonexistent/models")
    assert resp.status_code == 404
