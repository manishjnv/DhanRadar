"""mf.mf_leaderboard_boards — Phase 1 leaderboard materialization
(docs/features/leaderboard-data-backend.md §4).

Nightly `dhanradar.tasks.mf.leaderboard_refresh` (01:20 IST, after fund_events_refresh
01:15) upserts one row per (board_key, as_of_date) — ~18 board payloads + a `hero`
summary row, all pure SELECTs over
mf_fund_ranks/mf_funds/mf_fund_metrics/aum_history/mf_category_flows. `GET
/mf/leaderboard` reads each board_key's own latest row.

Additive + reversible. No RLS — public educational board content (not per-user data);
default schema-wide grants (migration 0052) cover the new table.

Revision ID: 0080
Revises: 0079
Create Date: 2026-08-16
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0080"
down_revision: str | None = "0079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mf_leaderboard_boards",
        sa.Column("board_key", sa.Text(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("source_run_id", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("board_key", "as_of_date"),
        schema="mf",
    )


def downgrade() -> None:
    op.drop_table("mf_leaderboard_boards", schema="mf")
