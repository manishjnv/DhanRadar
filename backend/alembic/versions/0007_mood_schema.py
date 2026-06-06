"""mood_schema — Mood Compass module schema (architecture Mood Compass Module).

Creates the `mood` schema + `market_mood` (one row per twice-daily snapshot). The
numeric `mood_score`/`confidence_score` are server-side; the public surface reads
`regime` + `confidence_band` + commentary (non-neg #2). `mood_history` (pgvector,
for AI-Enrichment analogues) is deferred with that module.

Additive + reversible.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-06
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS mood")

    op.create_table(
        "market_mood",
        sa.Column("snapshot_date", sa.Date(), primary_key=True),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("mood_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("regime", sa.Text(), nullable=False),
        sa.Column("confidence_band", sa.Text(), nullable=False),
        sa.Column("inputs_available", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_vector", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("contributing_factors", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("contradicting_factors", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("ai_commentary", sa.Text(), nullable=True),
        sa.Column("model_used", sa.Text(), nullable=True),
        sa.Column("data_quality", sa.Text(), nullable=False, server_default="ok"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="mood",
    )
    op.create_index("ix_market_mood_date", "market_mood", ["snapshot_date"], schema="mood")


def downgrade() -> None:
    # CASCADE so a future mood.* object (e.g. the deferred mood_history) does not
    # block a clean rollback.
    op.execute("DROP SCHEMA IF EXISTS mood CASCADE")
