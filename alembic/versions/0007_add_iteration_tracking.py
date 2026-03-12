"""add iteration tracking to tasks

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("iteration", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("tasks", sa.Column("approved", sa.Boolean(), nullable=True))
    op.add_column("runs",  sa.Column("current_iteration", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("runs",  sa.Column("awaiting_approval", sa.Boolean(), nullable=True, server_default="false"))


def downgrade() -> None:
    op.drop_column("tasks", "iteration")
    op.drop_column("tasks", "approved")
    op.drop_column("runs", "current_iteration")
    op.drop_column("runs", "awaiting_approval")
