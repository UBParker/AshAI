"""AgentManager — lifecycle management for all agents."""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator

from sqlalchemy import select
from helperai.db.engine import get_session_factory

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


@dataclass
class QueuedMessage:
    """A message waiting in an agent's queue, with TTL and retry metadata."""

    content: str
    sender_name: str | None
    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = 0
    injected: bool = False  # True when this was an injected (non-user) message
    response_queue: asyncio.Queue | None = field(default=None)  # SSE client receives events here


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
        self._cancellation_flags: dict[str, bool] = {}
        self._message_lock = threading.Lock()  # Prevent TOCTOU race in message delivery
        self._running_since: dict[str, datetime] = {}  # when each agent last entered RUNNING

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

            eve_provider = self._settings.eve_provider or self._settings.default_provider
            eve_model_name = self._settings.eve_model or self._settings.default_model

            if eve_model is None:
                eve_model = AgentModel(
                    name=self._settings.eve_name,
                    role=EVE_SYSTEM_PROMPT,
                    goal="Help the user with any task.",
                    status=AgentStatus.IDLE.value,
                    provider_name=eve_provider,
                    model_name=eve_model_name,
                    temperature=0.7,
                )
                eve_model.tool_names = EVE_TOOL_NAMES
                session.add(eve_model)
                await session.commit()
                await session.refresh(eve_model)
            else:
                # Sync Eve's provider/model with current config
                changed = False
                if eve_model.provider_name != eve_provider:
                    logger.info(
                        "Updating Eve provider: %s → %s",
                        eve_model.provider_name, eve_provider,
                    )
                    eve_model.provider_name = eve_provider
                    changed = True
                if eve_model.model_name != eve_model_name:
                    logger.info(
                        "Updating Eve model: %s → %s",
                        eve_model.model_name, eve_model_name,
                    )
                    eve_model.model_name = eve_model_name
                    changed = True
                if changed:
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

    def is_agent_started(self, agent_id: str) -> bool:
        """Check if an agent is started in memory."""
        return agent_id in self._agents

    def remove_agent_from_memory(self, agent_id: str) -> None:
        """Remove an agent from the in-memory registry (e.g. before restart)."""
        self._agents.pop(agent_id, None)

    async def restart_agent(self, agent_id: str) -> None:
        """Remove an agent from memory and re-start it (e.g. after config change)."""
        self.remove_agent_from_memory(agent_id)
        await self.start_agent(agent_id)

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

            # Only transition to IDLE if not already IDLE
            current_status = AgentStatus(agent_model.status)
            if current_status != AgentStatus.IDLE:
                validate_transition(current_status, AgentStatus.IDLE)
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

        should_update_status = False
        should_force_reset = False

        # Use lock to prevent TOCTOU race condition
        with self._message_lock:
            # Check if agent is currently busy - check the database, not in-memory model
            # The in-memory model might be stale
            session_factory = get_session_factory()
            async with session_factory() as session:
                result = await session.execute(
                    select(AgentModel).where(AgentModel.id == agent_id)
                )
                agent_db = result.scalar_one_or_none()
                if agent_db:
                    current_status = AgentStatus(agent_db.status)
                    # Update in-memory model to match DB
                    agent.model.status = agent_db.status
                else:
                    current_status = AgentStatus(agent.model.status)

            if current_status == AgentStatus.RUNNING:
                # Check whether the agent is stuck (running too long with no progress)
                running_since = self._running_since.get(agent_id)
                now = datetime.now(timezone.utc)
                stuck_timeout = self._settings.agent_stuck_timeout

                if running_since and (now - running_since).total_seconds() > stuck_timeout:
                    # Agent has been RUNNING longer than the configured limit.
                    # It is likely stuck due to a dropped connection or unhandled error.
                    # Force-reset so this new message can be processed directly.
                    elapsed = (now - running_since).total_seconds()
                    logger.warning(
                        "Agent %s stuck in RUNNING for %.0fs (limit=%ds), forcing reset",
                        agent_id, elapsed, stuck_timeout,
                    )
                    self._running_since.pop(agent_id, None)
                    should_force_reset = True
                    should_update_status = True
                else:
                    # Normal path: agent is legitimately busy, queue the message.
                    if agent_id not in self._message_queues:
                        self._message_queues[agent_id] = asyncio.Queue()

                    queue = self._message_queues[agent_id]
                    # Create a per-request queue so this SSE client can receive the
                    # response once the agent finishes its current task.
                    response_queue: asyncio.Queue = asyncio.Queue()
                    msg = QueuedMessage(
                        content=content,
                        sender_name=sender_name,
                        response_queue=response_queue,
                    )
                    await queue.put(msg)

                    # Save the user message to DB immediately so it appears in history
                    await self._save_message(agent_id, "user", content, sender_name=sender_name)

                    yield {"type": "queued", "position": queue.qsize()}

                    # Keep the SSE connection open and stream the response when ready.
                    # _process_queue() puts events here and sends None as a sentinel.
                    while True:
                        event = await response_queue.get()
                        if event is None:
                            break
                        yield event
                    return
            else:
                # Agent is free — mark that we'll transition it to RUNNING
                should_update_status = True

        # Transition the agent's status now that the lock is released.
        if should_force_reset:
            # RUNNING → IDLE clears the stuck state; we'll go RUNNING again below.
            logger.info("Force-resetting stuck agent %s: RUNNING → IDLE → RUNNING", agent_id)
            await self._set_status(agent_id, AgentStatus.IDLE)

        if should_update_status:
            await self._set_status(agent_id, AgentStatus.RUNNING)

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

        # Clear any previous cancellation flag
        self._cancellation_flags[agent_id] = False

        # Status is already set to RUNNING by send_message_stream
        # Just emit the status change event
        self._event_bus.emit_nowait(
            Event(
                type=EventType.AGENT_STATUS_CHANGED,
                agent_id=agent_id,
                data={"status": AgentStatus.RUNNING.value},
            )
        )

        # Prefix message with sender name for shared projects
        display_content = f"[{sender_name}]: {content}" if sender_name else content

        # Add user message
        agent.add_user_message(display_content)

        # Save user message to DB
        await self._save_message(agent_id, "user", content, sender_name=sender_name)

        # Stream response
        full_content = ""
        initial_message_count = len(agent.get_messages())
        try:
            async for event in agent.step_stream():
                # Check for cancellation
                if self._cancellation_flags.get(agent_id, False):
                    yield {"type": "cancelled", "message": "Response cancelled by user"}
                    await self._set_status(agent_id, AgentStatus.IDLE)
                    self._cancellation_flags[agent_id] = False
                    return

                if event["type"] == "content":
                    full_content += event["text"]
                yield event

            # Save all new messages to DB (assistant message, tool results, etc.)
            final_messages = agent.get_messages()
            for msg in final_messages[initial_message_count:]:
                await self._save_message(
                    agent_id,
                    msg.role,
                    msg.content or "",
                    tool_calls=msg.tool_calls,
                    tool_call_id=msg.tool_call_id
                )

            await self._set_status(agent_id, AgentStatus.IDLE)

        except Exception as e:
            logger.exception("Agent %s error during step", agent_id)
            await self._set_status(agent_id, AgentStatus.ERROR)
            yield {"type": "error", "error": str(e)}

    async def _process_queue(self, agent_id: str) -> None:
        """Process any queued messages for an agent.

        Enforces per-message TTL (expired messages are discarded to dead-letter),
        and retries failed messages with exponential backoff up to
        ``settings.message_queue_max_retries`` times.
        """
        queue = self._message_queues.get(agent_id)
        if queue is None or queue.empty():
            return

        ttl = self._settings.message_queue_ttl
        max_retries = self._settings.message_queue_max_retries
        retry_backoff = self._settings.message_queue_retry_backoff

        while not queue.empty():
            item: QueuedMessage = await queue.get()

            # ── TTL check ────────────────────────────────────────────────────
            now = datetime.now(timezone.utc)
            age = (now - item.queued_at).total_seconds()
            if age > ttl:
                logger.warning(
                    "Dropping expired queued message for agent %s "
                    "(age=%.0fs, ttl=%ds, retry=%d)",
                    agent_id, age, ttl, item.retry_count,
                )
                error_payload = {
                    "type": "error",
                    "error": (
                        f"Queued message expired after {age:.0f}s "
                        f"(TTL={ttl}s)"
                    ),
                }
                if item.response_queue is not None:
                    await item.response_queue.put(error_payload)
                    await item.response_queue.put(None)  # sentinel: stream closed
                self._event_bus.emit_nowait(
                    Event(
                        type=EventType.AGENT_MESSAGE,
                        agent_id=agent_id,
                        data={**error_payload, "role": "system"},
                    )
                )
                continue

            # ── Process the message ──────────────────────────────────────────
            try:
                agent = self._agents.get(agent_id)
                if agent is None:
                    break

                await self._set_status(agent_id, AgentStatus.RUNNING)

                # Injected messages (e.g. sub-agent reports) don't carry a
                # user-visible prefix; regular queued messages do.
                if item.sender_name and not item.injected:
                    display_content = f"[{item.sender_name}]: {item.content}"
                else:
                    display_content = item.content

                agent.add_user_message(display_content)

                initial_message_count = len(agent.get_messages())
                async for event in agent.step_stream():
                    # Forward every event to the waiting SSE client (if any).
                    # EventBus events (AGENT_STREAM_CHUNK etc.) are also emitted
                    # inside step_stream() for WebSocket subscribers.
                    if item.response_queue is not None:
                        await item.response_queue.put(event)

                # Persist new messages (assistant reply, tool results, etc.)
                final_messages = agent.get_messages()
                for msg in final_messages[initial_message_count:]:
                    await self._save_message(
                        agent_id,
                        msg.role,
                        msg.content or "",
                        tool_calls=msg.tool_calls,
                        tool_call_id=msg.tool_call_id,
                    )

                await self._set_status(agent_id, AgentStatus.IDLE)

                # Signal the SSE client that the stream is complete.
                if item.response_queue is not None:
                    await item.response_queue.put(None)  # sentinel

            except Exception as e:
                logger.exception(
                    "Error processing queued message for agent %s "
                    "(attempt %d of %d)",
                    agent_id, item.retry_count + 1, max_retries + 1,
                )

                if item.retry_count < max_retries:
                    # Exponential backoff: 2s, 4s, 8s, …
                    backoff = retry_backoff * (2 ** item.retry_count)
                    logger.info(
                        "Retrying queued message for agent %s in %.1fs "
                        "(attempt %d/%d)",
                        agent_id, backoff, item.retry_count + 1, max_retries,
                    )
                    await asyncio.sleep(backoff)
                    retried = QueuedMessage(
                        content=item.content,
                        sender_name=item.sender_name,
                        queued_at=item.queued_at,   # preserve original timestamp for TTL
                        retry_count=item.retry_count + 1,
                        injected=item.injected,
                        response_queue=item.response_queue,  # preserve SSE client's queue
                    )
                    await queue.put(retried)
                else:
                    # Dead-letter: max retries exhausted
                    logger.error(
                        "Queued message for agent %s exhausted %d retries, "
                        "dropping to dead-letter",
                        agent_id, max_retries,
                    )
                    error_payload = {
                        "type": "error",
                        "error": (
                            f"Message failed after {max_retries + 1} "
                            f"attempts: {e}"
                        ),
                    }
                    if item.response_queue is not None:
                        await item.response_queue.put(error_payload)
                        await item.response_queue.put(None)  # sentinel
                    self._event_bus.emit_nowait(
                        Event(
                            type=EventType.AGENT_MESSAGE,
                            agent_id=agent_id,
                            data={**error_payload, "role": "system"},
                        )
                    )

                try:
                    await self._set_status(agent_id, AgentStatus.ERROR)
                except Exception:
                    pass

    async def inject_message(self, agent_id: str, role: str, content: str) -> None:
        """Inject a message into an agent's thread (e.g., report from sub-agent)."""
        # Use lock to prevent race conditions with message processing
        with self._message_lock:
            # Auto-start agent if not already started in memory
            if not self.is_agent_started(agent_id):
                await self.start_agent(agent_id)

            agent = self._agents.get(agent_id)
            if agent is None:
                raise AgentNotFoundError(agent_id)

            # Check if agent is busy - if so, queue the injection
            current_status = AgentStatus(agent.model.status)
            if current_status == AgentStatus.RUNNING:
                # Queue as an injected message for later
                if agent_id not in self._message_queues:
                    self._message_queues[agent_id] = asyncio.Queue()
                queue = self._message_queues[agent_id]
                await queue.put(
                    QueuedMessage(content=content, sender_name=f"[{role}]", injected=True)
                )
                logger.info(f"Queued injected message for busy agent {agent_id}")
                return

            # Safe to inject directly
            agent.add_injected_message(role, content)

        # Save to DB and emit event (outside the lock)
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

    async def cancel_agent(self, agent_id: str) -> bool:
        """Cancel the current operation for an agent.

        Returns True if cancellation was initiated, False if agent wasn't running.
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id)

        current_status = AgentStatus(agent.model.status)
        if current_status == AgentStatus.RUNNING:
            # Set cancellation flag
            self._cancellation_flags[agent_id] = True

            # Clear the message queue if it exists
            if agent_id in self._message_queues:
                queue = self._message_queues[agent_id]
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

            # Force reset status to idle immediately
            await self._set_status(agent_id, AgentStatus.IDLE)
            return True
        return False

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

        # Track when each agent enters / exits RUNNING so stuck-agent detection works
        if status == AgentStatus.RUNNING:
            self._running_since[agent_id] = datetime.now(timezone.utc)
        else:
            self._running_since.pop(agent_id, None)

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
            # Use a transaction to prevent race conditions
            # For SQLite, this provides some isolation
            from sqlalchemy import func, text

            # Try to use IMMEDIATE transaction for SQLite to prevent races
            # This will serialize access to the sequence number
            try:
                await session.execute(text("BEGIN IMMEDIATE"))
            except Exception:
                # Not SQLite or doesn't support IMMEDIATE, continue with normal transaction
                pass

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
                # Convert ToolCall objects to dict for JSON serialization
                msg.tool_calls = [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in tool_calls
                ]
            session.add(msg)
            await session.commit()
