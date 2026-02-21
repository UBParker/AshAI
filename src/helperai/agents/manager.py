"""AgentManager — lifecycle management for all agents."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from sqlalchemy import select

from helperai.agents.agent import ConversationalAgent
from helperai.agents.eve import EVE_SYSTEM_PROMPT, EVE_TOOL_NAMES
from helperai.agents.state import validate_transition
from helperai.config import Settings
from helperai.core.events import Event, EventBus, EventType
from helperai.core.exceptions import AgentNotFoundError
from helperai.core.types import AgentStatus
from helperai.db.engine import get_session_factory
from helperai.db.models import Agent as AgentModel
from helperai.db.models import KnowledgeEntry, ThreadMessage
from helperai.llm.message_types import Message
from helperai.llm.registry import LLMRegistry
from helperai.tools.protocol import ToolContext
from helperai.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentManager:
    """Creates, starts, messages, and destroys agents."""

    def __init__(
        self,
        settings: Settings,
        llm_registry: LLMRegistry,
        tool_registry: ToolRegistry,
        event_bus: EventBus,
        approval_manager: object | None = None,
    ) -> None:
        self._settings = settings
        self._llm = llm_registry
        self._tools = tool_registry
        self._event_bus = event_bus
        self._approval_manager = approval_manager
        self._agents: dict[str, ConversationalAgent] = {}
        self._eve_id: str | None = None
        self._message_queues: dict[str, asyncio.Queue] = {}
        self._queue_processors: dict[str, asyncio.Task] = {}

    @property
    def eve_id(self) -> str | None:
        return self._eve_id

    def _make_tool_context(self, agent_id: str) -> ToolContext:
        return ToolContext(
            agent_id=agent_id,
            agent_manager=self,
            event_bus=self._event_bus,
            approval_manager=self._approval_manager,
        )

    async def init_eve(self) -> AgentModel:
        """Create or load Eve, the master agent."""
        session_factory = get_session_factory()
        async with session_factory() as session:
            # Check if Eve already exists
            result = await session.execute(
                select(AgentModel).where(AgentModel.name == self._settings.eve_name)
                .where(AgentModel.parent_id.is_(None))
                .where(AgentModel.status != AgentStatus.DESTROYED.value)
            )
            eve_model = result.scalar_one_or_none()

            if eve_model is None:
                eve_model = AgentModel(
                    name=self._settings.eve_name,
                    role=EVE_SYSTEM_PROMPT,
                    goal="Help the user with any task.",
                    status=AgentStatus.IDLE.value,
                    provider_name=self._settings.default_provider,
                    model_name=self._settings.eve_model or self._settings.default_model,
                    temperature=0.7,
                )
                eve_model.tool_names = EVE_TOOL_NAMES
                session.add(eve_model)
                await session.commit()
                await session.refresh(eve_model)

            self._eve_id = eve_model.id

            # Inject knowledge base into system prompt
            knowledge = await self._load_knowledge(session)
            role_with_knowledge = EVE_SYSTEM_PROMPT
            if knowledge:
                kb_text = "\n\n## Project Knowledge Base\n"
                for entry in knowledge:
                    kb_text += f"\n### {entry.title}\n{entry.content}\n"
                role_with_knowledge += kb_text
            eve_model.role = role_with_knowledge

            # Build in-memory agent
            provider = self._llm.get(eve_model.provider_name)
            tools = {n: self._tools.get(n) for n in EVE_TOOL_NAMES}
            agent = ConversationalAgent(
                agent_model=eve_model,
                provider=provider,
                tools=tools,
                event_bus=self._event_bus,
                tool_context_factory=self._make_tool_context,
            )

            # Load history
            messages = await self._load_messages(session, eve_model.id)
            agent.load_history(messages)

            self._agents[eve_model.id] = agent
            return eve_model

    async def _load_messages(self, session, agent_id: str) -> list[Message]:
        result = await session.execute(
            select(ThreadMessage)
            .where(ThreadMessage.agent_id == agent_id)
            .order_by(ThreadMessage.sequence)
        )
        rows = result.scalars().all()
        messages = []
        for row in rows:
            msg = Message(
                role=row.role,
                content=row.content,
                tool_call_id=row.tool_call_id,
            )
            if row.tool_calls:
                from helperai.llm.message_types import ToolCall

                msg.tool_calls = [
                    ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
                    for tc in row.tool_calls
                ]
            messages.append(msg)
        return messages

    async def _load_knowledge(self, session) -> list[KnowledgeEntry]:
        result = await session.execute(
            select(KnowledgeEntry).order_by(KnowledgeEntry.created_at)
        )
        return list(result.scalars().all())

    async def refresh_knowledge(self) -> None:
        """Reload knowledge entries and update Eve's system prompt."""
        if self._eve_id is None:
            return
        agent = self._agents.get(self._eve_id)
        if agent is None:
            return

        session_factory = get_session_factory()
        async with session_factory() as session:
            knowledge = await self._load_knowledge(session)

        role_with_knowledge = EVE_SYSTEM_PROMPT
        if knowledge:
            kb_text = "\n\n## Project Knowledge Base\n"
            for entry in knowledge:
                kb_text += f"\n### {entry.title}\n{entry.content}\n"
            role_with_knowledge += kb_text

        # Update in-memory agent's system prompt
        agent.model.role = role_with_knowledge
        agent.update_system_prompt(role_with_knowledge)

    async def create_agent(
        self,
        name: str,
        role: str,
        goal: str,
        parent_id: str | None = None,
        model_name: str = "",
        provider_name: str = "",
        tool_names: list[str] | None = None,
    ) -> AgentModel:
        tool_names = tool_names or []
        provider_name = provider_name or self._settings.default_provider
        model_name = model_name or self._settings.default_model

        session_factory = get_session_factory()
        async with session_factory() as session:
            agent_model = AgentModel(
                name=name,
                role=role,
                goal=goal,
                status=AgentStatus.CREATED.value,
                parent_id=parent_id,
                provider_name=provider_name,
                model_name=model_name,
                temperature=0.7,
            )
            agent_model.tool_names = tool_names
            session.add(agent_model)
            await session.commit()
            await session.refresh(agent_model)

        self._event_bus.emit_nowait(
            Event(
                type=EventType.AGENT_CREATED,
                agent_id=agent_model.id,
                data={"name": name, "goal": goal, "parent_id": parent_id},
            )
        )
        return agent_model

    async def start_agent(self, agent_id: str) -> None:
        """Initialize in-memory agent and set status to IDLE."""
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(AgentModel).where(AgentModel.id == agent_id)
            )
            agent_model = result.scalar_one_or_none()
            if agent_model is None:
                raise AgentNotFoundError(agent_id)

            validate_transition(AgentStatus(agent_model.status), AgentStatus.IDLE)
            agent_model.status = AgentStatus.IDLE.value
            await session.commit()
            await session.refresh(agent_model)

        provider = self._llm.get(agent_model.provider_name)
        tools_dict: dict = {}
        for tn in agent_model.tool_names:
            try:
                tools_dict[tn] = self._tools.get(tn)
            except Exception:
                logger.warning("Tool %s not found for agent %s", tn, agent_id)

        agent = ConversationalAgent(
            agent_model=agent_model,
            provider=provider,
            tools=tools_dict,
            event_bus=self._event_bus,
            tool_context_factory=self._make_tool_context,
        )

        messages = []
        async with session_factory() as session:
            messages = await self._load_messages(session, agent_id)
        agent.load_history(messages)

        self._agents[agent_id] = agent

        self._event_bus.emit_nowait(
            Event(
                type=EventType.AGENT_STATUS_CHANGED,
                agent_id=agent_id,
                data={"status": AgentStatus.IDLE.value},
            )
        )

    async def send_message_stream(
        self, agent_id: str, content: str, sender_name: str | None = None
    ) -> AsyncIterator[dict]:
        """Send a user message and stream the response.

        If the agent is already RUNNING (e.g., responding to another user in project mode),
        the message is queued and a 'queued' event is returned.
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id)

        # Check if agent is currently busy
        current_status = AgentStatus(agent.model.status)
        if current_status == AgentStatus.RUNNING:
            # Queue the message for later processing
            if agent_id not in self._message_queues:
                self._message_queues[agent_id] = asyncio.Queue()

            queue = self._message_queues[agent_id]
            await queue.put({"content": content, "sender_name": sender_name})

            # Save the user message to DB immediately so it appears in history
            await self._save_message(agent_id, "user", content, sender_name=sender_name)

            yield {"type": "queued", "position": queue.qsize()}
            return

        # Process message directly
        async for event in self._process_message(agent_id, content, sender_name):
            yield event

        # After completing, check if there are queued messages
        await self._process_queue(agent_id)

    async def _process_message(
        self, agent_id: str, content: str, sender_name: str | None = None
    ) -> AsyncIterator[dict]:
        """Process a single message: set status, stream response, save to DB."""
        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id)

        # Update status to RUNNING
        await self._set_status(agent_id, AgentStatus.RUNNING)

        # Prefix message with sender name for shared projects
        display_content = f"[{sender_name}]: {content}" if sender_name else content

        # Add user message
        agent.add_user_message(display_content)

        # Save user message to DB
        await self._save_message(agent_id, "user", content, sender_name=sender_name)

        # Stream response
        full_content = ""
        try:
            async for event in agent.step_stream():
                if event["type"] == "content":
                    full_content += event["text"]
                yield event

            # Save assistant response to DB
            if full_content:
                await self._save_message(agent_id, "assistant", full_content)

            await self._set_status(agent_id, AgentStatus.IDLE)

        except Exception as e:
            logger.exception("Agent %s error during step", agent_id)
            await self._set_status(agent_id, AgentStatus.ERROR)
            yield {"type": "error", "error": str(e)}

    async def _process_queue(self, agent_id: str) -> None:
        """Process any queued messages for an agent."""
        queue = self._message_queues.get(agent_id)
        if queue is None or queue.empty():
            return

        while not queue.empty():
            item = await queue.get()
            try:
                # Process queued message (the user message was already saved when queued)
                agent = self._agents.get(agent_id)
                if agent is None:
                    break

                await self._set_status(agent_id, AgentStatus.RUNNING)

                display_content = (
                    f"[{item['sender_name']}]: {item['content']}"
                    if item.get("sender_name")
                    else item["content"]
                )
                agent.add_user_message(display_content)

                full_content = ""
                async for event in agent.step_stream():
                    if event["type"] == "content":
                        full_content += event["text"]
                    # Events are broadcast via EventBus/WebSocket already

                if full_content:
                    await self._save_message(agent_id, "assistant", full_content)

                await self._set_status(agent_id, AgentStatus.IDLE)

            except Exception as e:
                logger.exception("Error processing queued message for agent %s", agent_id)
                try:
                    await self._set_status(agent_id, AgentStatus.ERROR)
                except Exception:
                    pass

    async def inject_message(self, agent_id: str, role: str, content: str) -> None:
        """Inject a message into an agent's thread (e.g., report from sub-agent)."""
        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id)

        agent.add_injected_message(role, content)
        await self._save_message(agent_id, role, content)

        self._event_bus.emit_nowait(
            Event(
                type=EventType.AGENT_MESSAGE,
                agent_id=agent_id,
                data={"role": role, "content": content},
            )
        )

    async def get_agent(self, agent_id: str) -> AgentModel | None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(AgentModel).where(AgentModel.id == agent_id)
            )
            return result.scalar_one_or_none()

    async def list_agents(self) -> list[AgentModel]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(AgentModel).where(AgentModel.status != AgentStatus.DESTROYED.value)
            )
            return list(result.scalars().all())

    async def get_thread(self, agent_id: str) -> list[ThreadMessage]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(ThreadMessage)
                .where(ThreadMessage.agent_id == agent_id)
                .order_by(ThreadMessage.sequence)
            )
            return list(result.scalars().all())

    async def destroy_agent(self, agent_id: str) -> None:
        if agent_id == self._eve_id:
            raise ValueError("Cannot destroy Eve")

        await self._set_status(agent_id, AgentStatus.DESTROYED)
        self._agents.pop(agent_id, None)

        self._event_bus.emit_nowait(
            Event(type=EventType.AGENT_DESTROYED, agent_id=agent_id, data={})
        )

    async def _set_status(self, agent_id: str, status: AgentStatus) -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(AgentModel).where(AgentModel.id == agent_id)
            )
            agent_model = result.scalar_one_or_none()
            if agent_model is None:
                return

            current = AgentStatus(agent_model.status)
            if current == status:
                return
            validate_transition(current, status)
            agent_model.status = status.value
            await session.commit()

        # Update in-memory model too
        if agent_id in self._agents:
            self._agents[agent_id].model.status = status.value

        self._event_bus.emit_nowait(
            Event(
                type=EventType.AGENT_STATUS_CHANGED,
                agent_id=agent_id,
                data={"status": status.value},
            )
        )

    async def _save_message(
        self,
        agent_id: str,
        role: str,
        content: str,
        tool_calls=None,
        tool_call_id=None,
        sender_name: str | None = None,
    ) -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            # Get next sequence number
            from sqlalchemy import func

            result = await session.execute(
                select(func.coalesce(func.max(ThreadMessage.sequence), 0)).where(
                    ThreadMessage.agent_id == agent_id
                )
            )
            max_seq = result.scalar()
            next_seq = (max_seq or 0) + 1

            msg = ThreadMessage(
                agent_id=agent_id,
                role=role,
                content=content,
                tool_call_id=tool_call_id,
                sender_name=sender_name,
                sequence=next_seq,
            )
            if tool_calls:
                msg.tool_calls = tool_calls
            session.add(msg)
            await session.commit()
