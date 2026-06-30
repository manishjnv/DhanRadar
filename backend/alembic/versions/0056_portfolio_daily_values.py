"""M2.2 — daily portfolio valuation series.

Creates `mf.mf_portfolio_daily_values` as a TimescaleDB hypertable
(1-month chunks on `valuation_date`).  One row per (portfolio_id, valuation_date)
stores the portfolio's total market value and total invested for that date,
enabling TRUE portfolio Sharpe/σ/max-drawdown (deferred to M2.3, B88).

Revision ID: 0056
Revises: 0055
Create Date: 2026-06-30
"""

from __future__ import annotations

from alembic import op

revision: str = "0056"
down_revision: str | None = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mf.mf_portfolio_daily_values (
            portfolio_id    uuid        NOT NULL
                REFERENCES mf.mf_portfolios(id) ON DELETE CASCADE,
            user_id         uuid        NOT NULL
                REFERENCES auth.users(id) ON DELETE CASCADE,
            valuation_date  date        NOT NULL,
            total_value     numeric(16, 2) NOT NULL,
            total_invested  numeric(16, 2) NOT NULL,
            computed_at     timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_mf_portfolio_daily_value
                UNIQUE (portfolio_id, valuation_date)
        );
        """
    )
    # Promote to a TimescaleDB hypertable on valuation_date (1-month chunks).
    # The IF NOT EXISTS guard makes the migration idempotent on re-run.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM timescaledb_information.hypertables
                WHERE hypertable_schema = 'mf'
                  AND hypertable_name  = 'mf_portfolio_daily_values'
            ) THEN
                PERFORM create_hypertable(
                    'mf.mf_portfolio_daily_values',
                    'valuation_date',
                    chunk_time_interval => INTERVAL '1 month',
                    migrate_data        => true
                );
            END IF;
        END $$;
        """
    )
    # Index for fast per-portfolio ordered reads (the valuation-series endpoint).
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_mf_portfolio_daily_values_portfolio_date
            ON mf.mf_portfolio_daily_values (portfolio_id, valuation_date DESC);
        """
    )
    # Index for per-user sweeps in the daily Celery task.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_mf_portfolio_daily_values_user
            ON mf.mf_portfolio_daily_values (user_id);
        """
    )
    # Grant the app role read/write access (mirrors pattern in 0052/0053).
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regrole('dhanradar_app') IS NOT NULL THEN
                GRANT SELECT, INSERT, UPDATE ON mf.mf_portfolio_daily_values
                    TO dhanradar_app;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS mf.mf_portfolio_daily_values;
        """
    )
