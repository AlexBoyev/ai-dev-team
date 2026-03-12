"""add agent_logs table

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("agent_key", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_logs_run_id", "agent_logs", ["run_id"])
    op.create_index("ix_agent_logs_agent_key", "agent_logs", ["agent_key"])
    op.create_index("ix_agent_logs_ts", "agent_logs", ["ts"])


def downgrade() -> None:
    op.drop_index("ix_agent_logs_ts", table_name="agent_logs")
    op.drop_index("ix_agent_logs_agent_key", table_name="agent_logs")
    op.drop_index("ix_agent_logs_run_id", table_name="agent_logs")
    op.drop_table("agent_logs")
