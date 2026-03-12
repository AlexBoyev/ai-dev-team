# backend/db/models.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at  = Column(DateTime(timezone=True), default=utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status      = Column(String(32), default="running")
    repo_url    = Column(Text, nullable=True)
    note        = Column(Text, nullable=True)

    tasks     = relationship("Task",       back_populates="run", cascade="all, delete-orphan")
    logs      = relationship("Log",        back_populates="run", cascade="all, delete-orphan")
    agents    = relationship("AgentEvent", back_populates="run", cascade="all, delete-orphan")
    artifacts = relationship("Artifact",   back_populates="run", cascade="all, delete-orphan")
    llm_calls = relationship("LLMCall", foreign_keys="LLMCall.run_id", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id         = Column(UUID(as_uuid=True), ForeignKey("runs.id"), nullable=False)
    title          = Column(Text)
    task_type      = Column(String(64))
    assigned_agent = Column(String(64))
    status         = Column(String(32), default="pending")
    result         = Column(Text, nullable=True)
    created_at     = Column(DateTime(timezone=True), default=utcnow)
    updated_at     = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    run = relationship("Run", back_populates="tasks")


class AgentEvent(Base):
    __tablename__ = "agent_events"

    id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id    = Column(UUID(as_uuid=True), ForeignKey("runs.id"), nullable=False)
    agent_key = Column(String(64))
    status    = Column(String(32))
    action    = Column(Text, nullable=True)
    ts        = Column(DateTime(timezone=True), default=utcnow)

    run = relationship("Run", back_populates="agents")


class Log(Base):
    __tablename__ = "logs"

    id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id  = Column(UUID(as_uuid=True), ForeignKey("runs.id"), nullable=True)
    ts      = Column(DateTime(timezone=True), default=utcnow)
    level   = Column(String(16))
    source  = Column(String(64))
    message = Column(Text)

    run = relationship("Run", back_populates="logs")


class Repository(Base):
    __tablename__ = "repositories"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name        = Column(String(256), nullable=False)
    url         = Column(Text, nullable=True)
    local_path  = Column(Text, nullable=False)
    disk_bytes  = Column(sa.BigInteger, default=0)
    last_run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id"), nullable=True)
    cloned_at   = Column(DateTime(timezone=True), default=utcnow)
    updated_at  = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Artifact(Base):
    __tablename__ = "artifacts"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id     = Column(UUID(as_uuid=True), ForeignKey("runs.id"), nullable=False)
    name       = Column(String(256))
    path       = Column(Text)
    size_bytes = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    run = relationship("Run", back_populates="artifacts")


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id            = Column(UUID(as_uuid=True), ForeignKey("runs.id"), nullable=True)
    task_id           = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    agent_key         = Column(String(64), nullable=True)
    prompt_name       = Column(String(128), nullable=True)          # ← NEW
    model             = Column(String(64), nullable=False)
    prompt_tokens     = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens      = Column(Integer, default=0)
    cost_usd          = Column(Numeric(10, 6), default=0)
    ts                = Column(DateTime(timezone=True), default=utcnow)
