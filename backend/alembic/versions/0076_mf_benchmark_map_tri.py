"""mf.mf_benchmark_map + mf.mf_benchmark_tri (Phase 4c pt3).

Two tables, ONE migration (they ship together — the map feeds the fetch's index_key
universe):

``mf_benchmark_map`` — free-text AMFI ``benchmark_index`` string -> canonical TRI index
key (``dhanradar.mf.benchmark_map.CANONICAL_INDEX_KEYS``). Data, not code: a new benchmark
string arrives with every AMFI file, and the honest-fallback rule (never guess) means most
strings stay unmapped until confidently classified — a fix must not need a deploy. Plain
table, no hypertable (a few thousand rows total, no time-series shape).

``mf_benchmark_tri`` — daily Total Return Index values for the 4 canonical equity indices
(niftyindices.com; see ``dhanradar.tasks.mf.benchmark_tri_fetch``). COMPLIANCE (ADR-0033,
binding): raw ``tri_value`` is internal-compute-only and must NEVER reach the API/DOM — it
lives in its OWN table, never in ``mf_benchmark_daily`` (the existing Nifty 50 PRICE-index
table, which DOES serve the DOM). Only a derived value (e.g. a future ``alpha_1y_pct``
differential) may ever surface client-facing. TimescaleDB hypertable, 1-year chunks — same
IF-EXISTS extension guard as migration 0075 (``mf_category_series``) / migration 0004
(``mf_nav_history``), so a plain-Postgres box (and the CI test DB) simply skips the
hypertable promotion.

Additive + reversible. No API/DOM exposure — nothing here changes a compliance surface.

Revision ID: 0076
Revises: 0075
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0076"
down_revision: str | None = "0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mf_benchmark_map",
        sa.Column("benchmark_name_raw", sa.Text(), nullable=False),
        sa.Column("index_key", sa.Text(), nullable=False),
        sa.Column("mapped_by", sa.Text(), nullable=False),
        sa.Column(
            "mapped_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("benchmark_name_raw"),
        schema="mf",
    )

    op.create_table(
        "mf_benchmark_tri",
        sa.Column("index_key", sa.Text(), nullable=False),
        sa.Column("tri_date", sa.Date(), nullable=False),
        sa.Column("tri_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("index_key", "tri_date"),
        schema="mf",
    )

    # TimescaleDB hypertable — same guard pattern as 0075_mf_category_series.py: skip
    # silently on a plain-Postgres box (CI test DB has no timescaledb extension).
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
            PERFORM create_hypertable('mf.mf_benchmark_tri', 'tri_date',
                                      chunk_time_interval => INTERVAL '1 year',
                                      if_not_exists => TRUE, migrate_data => TRUE);
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("mf_benchmark_tri", schema="mf")
    op.drop_table("mf_benchmark_map", schema="mf")
