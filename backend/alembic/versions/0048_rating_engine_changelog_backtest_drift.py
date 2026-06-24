"""Add backtest and drift JSONB columns to compliance.rating_engine_changelog.

Revision ID: 0048
Revises: 0047
Create Date: 2026-06-24
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rating_engine_changelog",
        sa.Column("backtest", JSONB, nullable=True),
        schema="compliance",
    )
    op.add_column(
        "rating_engine_changelog",
        sa.Column("drift", JSONB, nullable=True),
        schema="compliance",
    )


def downgrade() -> None:
    op.drop_column("rating_engine_changelog", "backtest", schema="compliance")
    op.drop_column("rating_engine_changelog", "drift", schema="compliance")
