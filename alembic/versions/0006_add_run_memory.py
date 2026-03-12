"""add run_memory table

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_memory",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("repo_name", sa.String(256), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("agent_key", sa.String(64), nullable=False),
        sa.Column("memory_type", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_run_memory_repo_name", "run_memory", ["repo_name"])
    op.create_index("ix_run_memory_agent_key", "run_memory", ["agent_key"])
    op.create_index("ix_run_memory_memory_type", "run_memory", ["memory_type"])
    op.create_index("ix_run_memory_ts", "run_memory", ["ts"])


def downgrade() -> None:
    op.drop_index("ix_run_memory_ts", table_name="run_memory")
    op.drop_index("ix_run_memory_memory_type", table_name="run_memory")
    op.drop_index("ix_run_memory_agent_key", table_name="run_memory")
    op.drop_index("ix_run_memory_repo_name", table_name="run_memory")
    op.drop_table("run_memory")
