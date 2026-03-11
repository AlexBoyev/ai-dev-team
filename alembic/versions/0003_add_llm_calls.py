"""add llm_calls table

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id",                UUID(as_uuid=True), primary_key=True,  nullable=False),
        sa.Column("run_id",            UUID(as_uuid=True), sa.ForeignKey("runs.id"),  nullable=True),
        sa.Column("task_id",           UUID(as_uuid=True), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("agent_key",         sa.String(64),      nullable=True),
        sa.Column("model",             sa.String(64),      nullable=False),
        sa.Column("prompt_tokens",     sa.Integer(),       nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(),       nullable=False, server_default="0"),
        sa.Column("total_tokens",      sa.Integer(),       nullable=False, server_default="0"),
        sa.Column("cost_usd",          sa.Numeric(10, 6),  nullable=False, server_default="0"),
        sa.Column("ts",                sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_llm_calls_run_id", "llm_calls", ["run_id"])
    op.create_index("ix_llm_calls_ts",     "llm_calls", ["ts"])


def downgrade() -> None:
    op.drop_index("ix_llm_calls_ts",     table_name="llm_calls")
    op.drop_index("ix_llm_calls_run_id", table_name="llm_calls")
    op.drop_table("llm_calls")
