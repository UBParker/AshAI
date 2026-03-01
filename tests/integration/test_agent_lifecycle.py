"""Integration tests for agent lifecycle."""

import pytest

from helperai.agents.manager import AgentManager
from helperai.config import Settings
from helperai.core.events import EventBus
from helperai.core.types import AgentStatus
from helperai.db.engine import close_db, get_engine, init_db
from helperai.llm.message_types import Message, StreamChunk
from helperai.llm.registry import LLMRegistry
from helperai.tools.builtin.list_agents import ListAgentsTool
from helperai.tools.builtin.message_agent import MessageAgentTool
from helperai.tools.builtin.report_to_eve import ReportToEveTool
from helperai.tools.builtin.spawn_agent import SpawnAgentTool
from helperai.tools.registry import ToolRegistry


class MockProvider:
    """Mock LLM provider that returns a fixed response."""

    def __init__(self):
        self._name = "test"
        self._responses = ["Hello! I'm Eve."]
        self._call_count = 0

    @property
    def name(self):
        return self._name

    async def stream(self, messages, model, **kwargs):
        idx = min(self._call_count, len(self._responses) - 1)
        text = self._responses[idx]
        self._call_count += 1
        for char in text:
            yield StreamChunk(delta_content=char)
        yield StreamChunk(finish_reason="stop")

    async def list_models(self):
        return ["test-model"]


@pytest.fixture
async def setup():
    """Set up test database and services."""
    import helperai.db.engine as eng
    import helperai.config as cfg

    # Override settings
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        default_provider="test",
        default_model="test-model",
        ollama_base_url="",
        eve_provider="test",  # override env var so tests stay isolated
        eve_model="test-model",
        eve_name="Eve",
    )
    cfg._settings = settings

    # Reset engine
    eng._engine = None
    eng._session_factory = None

    await init_db()

    event_bus = EventBus()
    llm_registry = LLMRegistry()
    mock_provider = MockProvider()
    llm_registry.register(mock_provider, is_default=True)

    tool_registry = ToolRegistry()
    tool_registry.register(SpawnAgentTool())
    tool_registry.register(ListAgentsTool())
    tool_registry.register(MessageAgentTool())
    tool_registry.register(ReportToEveTool())

    manager = AgentManager(
        settings=settings,
        llm_registry=llm_registry,
        tool_registry=tool_registry,
        event_bus=event_bus,
    )

    yield manager, mock_provider, event_bus

    await close_db()
    cfg._settings = None


async def test_init_eve(setup):
    manager, _, _ = setup
    eve = await manager.init_eve()
    assert eve.name == "Eve"
    assert eve.status == AgentStatus.IDLE.value
    assert manager.eve_id == eve.id


async def test_chat_with_eve(setup):
    manager, _, _ = setup
    eve = await manager.init_eve()

    chunks = []
    async for event in manager.send_message_stream(eve.id, "Hello"):
        chunks.append(event)

    content_chunks = [c for c in chunks if c.get("type") == "content"]
    assert len(content_chunks) > 0
    full_text = "".join(c["text"] for c in content_chunks)
    assert "Eve" in full_text


async def test_create_sub_agent(setup):
    manager, _, _ = setup
    await manager.init_eve()

    agent = await manager.create_agent(
        name="Researcher",
        role="You are a research agent.",
        goal="Find information.",
        parent_id=manager.eve_id,
    )
    assert agent.name == "Researcher"
    assert agent.status == AgentStatus.CREATED.value
    assert agent.parent_id == manager.eve_id


async def test_list_agents(setup):
    manager, _, _ = setup
    await manager.init_eve()
    await manager.create_agent(name="Agent1", role="test", goal="test")

    agents = await manager.list_agents()
    names = [a.name for a in agents]
    assert "Eve" in names
    assert "Agent1" in names


async def test_destroy_agent(setup):
    manager, _, _ = setup
    await manager.init_eve()
    agent = await manager.create_agent(name="Temp", role="test", goal="test")
    await manager.start_agent(agent.id)
    await manager.destroy_agent(agent.id)

    db_agent = await manager.get_agent(agent.id)
    assert db_agent.status == AgentStatus.DESTROYED.value


async def test_cannot_destroy_eve(setup):
    manager, _, _ = setup
    await manager.init_eve()

    with pytest.raises(ValueError, match="Cannot destroy Eve"):
        await manager.destroy_agent(manager.eve_id)


async def test_thread_persistence(setup):
    manager, _, _ = setup
    eve = await manager.init_eve()

    async for _ in manager.send_message_stream(eve.id, "Test message"):
        pass

    thread = await manager.get_thread(eve.id)
    roles = [m.role for m in thread]
    assert "user" in roles
    assert "assistant" in roles


async def test_queued_message_sse_forwarding(setup):
    """A queued message's response must be streamed back to the HTTP SSE client.

    Scenario:
    - Agent processes M1 directly (keeping status=RUNNING while streaming).
    - M2 arrives while M1 is in flight → gets queued with a response_queue.
    - After M1 finishes, _process_queue() processes M2 and forwards events into
      the response_queue so the M2 SSE generator can yield them.
    """
    import asyncio as _asyncio

    manager, mock_provider, _ = setup
    eve = await manager.init_eve()

    # Slow M1: yields chunks with a tiny delay so M2 arrives while M1 is running.
    slow_m1_done = _asyncio.Event()

    async def slow_stream(messages, model, **kwargs):
        yield StreamChunk(delta_content="M1 ")
        await _asyncio.sleep(0.05)  # Give M2 time to arrive
        yield StreamChunk(delta_content="response")
        yield StreamChunk(finish_reason="stop")
        slow_m1_done.set()

    mock_provider.stream = slow_stream

    # Collect M1 events in the background.
    m1_events: list[dict] = []

    async def consume_m1():
        async for ev in manager.send_message_stream(eve.id, "M1"):
            m1_events.append(ev)

    m1_task = _asyncio.create_task(consume_m1())

    # Wait briefly so M1 starts and the agent enters RUNNING.
    await _asyncio.sleep(0.01)

    # Send M2; since the agent is RUNNING it should be queued.
    m2_events: list[dict] = []

    async def consume_m2():
        async for ev in manager.send_message_stream(eve.id, "M2"):
            m2_events.append(ev)

    m2_task = _asyncio.create_task(consume_m2())

    # Wait for both tasks to finish.
    await _asyncio.wait_for(_asyncio.gather(m1_task, m2_task), timeout=10)

    # M1 should have streamed content normally.
    assert any(e.get("type") == "content" for e in m1_events), (
        "M1 should have content events"
    )

    # M2 should have received a 'queued' event followed by the actual response.
    types_m2 = [e.get("type") for e in m2_events]
    assert "queued" in types_m2, "M2 should have been queued"
    assert "content" in types_m2, (
        "M2 SSE client must receive the content events after dequeueing"
    )
    assert "done" in types_m2, "M2 SSE client must receive the done event"

    # 'queued' must come first, before content.
    queued_idx = types_m2.index("queued")
    content_idx = types_m2.index("content")
    assert queued_idx < content_idx, "'queued' must precede 'content'"
