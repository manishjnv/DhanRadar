"""mood.mood_regime_history — daily served-regime snapshot for the future per-fund
"performance by market phase" feature (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §10.8).

Populated by `dhanradar.tasks.mood.mood_history_snapshot` (daily 16:05 IST), a PURE
Redis cache consumer: it reads the already-published `mood:latest` key and writes
one row — it never recomputes and never live-fetches (mood worker discipline, see
memory 'mood-breadth-is-cache-consumer'). Cold cache → no row that day.

Deliberately NOT named `mood_history` — that name is reserved by migration 0007 /
models/mood.py for the deferred pgvector(11) historical-analogues table (the
AI-Enrichment module's semantic-similarity search, a different feature).

`mood` schema already exists (migration 0007) and is already in db_schemas.APP_SCHEMAS
— this migration only adds a table to it.

Additive + reversible.

Revision ID: 0063
Revises: 0062
Create Date: 2026-07-04
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0063"
down_revision: str | None = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mood_regime_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False, unique=True),
        sa.Column("regime", sa.Text(), nullable=False),
        sa.Column(
            "score_inputs", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        schema="mood",
    )


def downgrade() -> None:
    op.drop_table("mood_regime_history", schema="mood")
