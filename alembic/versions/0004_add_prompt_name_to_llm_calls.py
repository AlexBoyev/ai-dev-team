"""add prompt_name to llm_calls

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "llm_calls",
        sa.Column("prompt_name", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("llm_calls", "prompt_name")
