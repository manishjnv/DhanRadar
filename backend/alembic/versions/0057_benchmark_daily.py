"""Nifty 50 price-index daily-close series (ADR-0037 — benchmark for Portfolio vs Market chart).

Creates `mf.mf_benchmark_daily` — a plain reference-data table (NOT a hypertable; one row/day,
one benchmark series).  Public market data: no user_id, no RLS.  First use: Nifty 50 price
index ('nifty50_price') sourced from Yahoo Finance ^NSEI.

Revision ID: 0057
Revises: 0056
Create Date: 2026-07-01
"""

from __future__ import annotations

from alembic import op

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mf.mf_benchmark_daily (
            benchmark   text        NOT NULL,
            close_date  date        NOT NULL,
            close_value numeric(14, 2) NOT NULL,
            CONSTRAINT uq_mf_benchmark_daily UNIQUE (benchmark, close_date)
        );
        """
    )
    # Fast range-scan for the chart endpoint (benchmark, date ASC/DESC).
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_mf_benchmark_daily_benchmark_date
            ON mf.mf_benchmark_daily (benchmark, close_date);
        """
    )
    # Grant the app role read/write access (public reference data — no RLS needed).
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regrole('dhanradar_app') IS NOT NULL THEN
                GRANT SELECT, INSERT, UPDATE ON mf.mf_benchmark_daily
                    TO dhanradar_app;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mf.mf_benchmark_daily;")
