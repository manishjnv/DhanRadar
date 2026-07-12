"""mf.mf_category_series — materialized per-category chained median-return index (Phase 4c pt2).

Value Research pattern: a fund-detail chart needs a "category average" line. Computed
purely from NAV data we already own (`mf.mf_nav_history`) — no new data source. Stores a
CHAINED MEDIAN-RETURN INDEX (base 100.0), not a median of raw NAVs, so the series is free
of start-date bias and tolerates funds entering/leaving the category over time (see
`dhanradar.tasks.mf.category_series_refresh` for the exact math). `fund_count` is kept so
a future consumer can suppress a too-thin cohort server-side.

`category` is the SAME grouping key `dhanradar.mf.cohort` uses for the scoring cohort
(`mf_funds.sebi_category`) — this table does NOT change `cohort.py`'s on-the-fly read
path (that switch is a later, separate change).

TimescaleDB hypertable, 1-year chunks — same IF-EXISTS extension guard as migration 0004
(`mf.mf_nav_history`) / the Phase 4 `mf_benchmark_tri` snippet, so a plain-Postgres box
(and the CI test DB) simply skips the hypertable promotion.

No API/DOM exposure yet (internal series only) — nothing here changes a compliance
surface.

Additive + reversible.

Revision ID: 0075
Revises: 0074
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0075"
down_revision: str | None = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mf_category_series",
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("series_date", sa.Date(), nullable=False),
        sa.Column("index_value", sa.Numeric(18, 6), nullable=False),
        sa.Column("median_daily_return", sa.Numeric(12, 8), nullable=True),
        sa.Column("fund_count", sa.Integer(), nullable=False),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("category", "series_date"),
        schema="mf",
    )

    # TimescaleDB hypertable — same guard pattern as 0004_mf_schema.py (mf_nav_history):
    # skip silently on a plain-Postgres box (CI test DB has no timescaledb extension).
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
            PERFORM create_hypertable('mf.mf_category_series', 'series_date',
                                      chunk_time_interval => INTERVAL '1 year',
                                      if_not_exists => TRUE, migrate_data => TRUE);
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("mf_category_series", schema="mf")
