"""add repositories table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True),
        sa.Column("name",        sa.String(256),     nullable=False),
        sa.Column("url",         sa.Text,            nullable=True),
        sa.Column("local_path",  sa.Text,            nullable=False),
        sa.Column("disk_bytes",  sa.BigInteger,      default=0),
        sa.Column("last_run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=True),
        sa.Column("cloned_at",   sa.DateTime(timezone=True)),
        sa.Column("updated_at",  sa.DateTime(timezone=True)),
    )
    op.create_index("ix_repositories_name", "repositories", ["name"])


def downgrade() -> None:
    op.drop_table("repositories")
