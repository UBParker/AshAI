"""SQLAlchemy ORM models."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="")  # system prompt
    goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created")
    parent_id: Mapped[str | None] = mapped_column(
        String(12), ForeignKey("agents.id"), nullable=True
    )
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    tool_names_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    messages: Mapped[list[ThreadMessage]] = relationship(
        back_populates="agent", cascade="all, delete-orphan", order_by="ThreadMessage.sequence"
    )
    children: Mapped[list[Agent]] = relationship(back_populates="parent")
    parent: Mapped[Agent | None] = relationship(
        back_populates="children", remote_side=[id]
    )

    @property
    def tool_names(self) -> list[str]:
        return json.loads(self.tool_names_json)

    @tool_names.setter
    def tool_names(self, value: list[str]) -> None:
        self.tool_names_json = json.dumps(value)


class ThreadMessage(Base):
    __tablename__ = "thread_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(
        String(12), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # system/user/assistant/tool
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tool_calls_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sender_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    agent: Mapped[Agent] = relationship(back_populates="messages")

    @property
    def tool_calls(self) -> list[dict] | None:
        if self.tool_calls_json is None:
            return None
        return json.loads(self.tool_calls_json)

    @tool_calls.setter
    def tool_calls(self, value: list[dict] | None) -> None:
        self.tool_calls_json = json.dumps(value) if value else None


class PendingApproval(Base):
    __tablename__ = "pending_approvals"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=_new_id)
    agent_id: Mapped[str] = mapped_column(
        String(12), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending / approved / denied
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def arguments(self) -> dict:
        return json.loads(self.arguments_json)

    @arguments.setter
    def arguments(self, value: dict) -> None:
        self.arguments_json = json.dumps(value)


class ProviderConfig(Base):
    __tablename__ = "provider_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extra_config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    @property
    def extra_config(self) -> dict:
        return json.loads(self.extra_config_json)

    @extra_config.setter
    def extra_config(self, value: dict) -> None:
        self.extra_config_json = json.dumps(value)


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=_new_id)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    added_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class AgentTemplate(Base):
    __tablename__ = "agent_templates"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=_new_id)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    role: Mapped[str] = mapped_column(Text, nullable=False, default="")
    goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    tool_names_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    @property
    def tool_names(self) -> list[str]:
        return json.loads(self.tool_names_json)

    @tool_names.setter
    def tool_names(self, value: list[str]) -> None:
        self.tool_names_json = json.dumps(value)
