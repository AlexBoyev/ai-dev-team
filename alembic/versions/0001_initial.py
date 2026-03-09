"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32)),
        sa.Column("repo_url", sa.Text, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
    )
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id")),
        sa.Column("title", sa.Text),
        sa.Column("task_type", sa.String(64)),
        sa.Column("assigned_agent", sa.String(64)),
        sa.Column("status", sa.String(32)),
        sa.Column("result", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "agent_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id")),
        sa.Column("agent_key", sa.String(64)),
        sa.Column("status", sa.String(32)),
        sa.Column("action", sa.Text, nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True)),
        sa.Column("level", sa.String(16)),
        sa.Column("source", sa.String(64)),
        sa.Column("message", sa.Text),
    )
    op.create_table(
        "artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id")),
        sa.Column("name", sa.String(256)),
        sa.Column("path", sa.Text),
        sa.Column("size_bytes", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    # Indexes for common queries
    op.create_index("ix_tasks_run_id", "tasks", ["run_id"])
    op.create_index("ix_logs_run_id", "logs", ["run_id"])
    op.create_index("ix_agent_events_run_id", "agent_events", ["run_id"])
    op.create_index("ix_runs_status", "runs", ["status"])


def downgrade() -> None:
    op.drop_table("artifacts")
    op.drop_table("logs")
    op.drop_table("agent_events")
    op.drop_table("tasks")
    op.drop_table("runs")
