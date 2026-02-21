"""Approval system — suspends agent coroutines awaiting user approval."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select

from helperai.core.events import Event, EventType
from helperai.db.engine import get_session_factory
from helperai.db.models import PendingApproval

if TYPE_CHECKING:
    from helperai.core.events import EventBus

logger = logging.getLogger(__name__)


class ApprovalManager:
    """Manages approval requests using asyncio.Future to suspend agent coroutines."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._pending: dict[str, asyncio.Future[bool]] = {}

    async def request_approval(
        self,
        agent_id: str,
        tool_name: str,
        arguments: dict,
    ) -> bool:
        """Create an approval request. Suspends the calling coroutine until resolved.

        Returns True if approved, False if denied.
        """
        session_factory = get_session_factory()
        async with session_factory() as session:
            approval = PendingApproval(
                agent_id=agent_id,
                tool_name=tool_name,
                status="pending",
            )
            approval.arguments = arguments
            session.add(approval)
            await session.commit()
            await session.refresh(approval)
            approval_id = approval.id

        # Create a Future that the agent coroutine will await
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._pending[approval_id] = future

        # Emit event so frontend shows the dialog
        self._event_bus.emit_nowait(
            Event(
                type=EventType.APPROVAL_REQUESTED,
                agent_id=agent_id,
                data={
                    "approval_id": approval_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                },
            )
        )

        logger.info(
            "Approval requested: id=%s agent=%s tool=%s", approval_id, agent_id, tool_name
        )

        # Suspend until the user approves/denies via the HTTP endpoint
        try:
            approved = await future
        finally:
            self._pending.pop(approval_id, None)

        return approved

    async def resolve(self, approval_id: str, approved: bool) -> None:
        """Resolve a pending approval. Called from the HTTP endpoint."""
        future = self._pending.get(approval_id)
        if future is None:
            raise ValueError(f"No pending approval with id {approval_id}")

        # Update DB
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(PendingApproval).where(PendingApproval.id == approval_id)
            )
            row = result.scalar_one_or_none()
            if row:
                row.status = "approved" if approved else "denied"
                row.resolved_at = datetime.now(timezone.utc)
                await session.commit()
                agent_id = row.agent_id
            else:
                agent_id = ""

        # Resolve the future — this resumes the agent coroutine
        if not future.done():
            future.set_result(approved)

        self._event_bus.emit_nowait(
            Event(
                type=EventType.APPROVAL_RESOLVED,
                agent_id=agent_id,
                data={
                    "approval_id": approval_id,
                    "approved": approved,
                },
            )
        )

        logger.info("Approval resolved: id=%s approved=%s", approval_id, approved)

    async def list_pending(self) -> list[dict]:
        """Return all pending approvals from the DB."""
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(PendingApproval).where(PendingApproval.status == "pending")
            )
            rows = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "agent_id": r.agent_id,
                    "tool_name": r.tool_name,
                    "arguments": r.arguments,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
