"""mf_risk_adjusted_metrics — Sharpe, Sortino, volatility + rolling-1Y stats
per fund, plus the mf_category_stats distribution table.

Adds 7 nullable Float columns to mf_fund_metrics (computed by risk_adjusted_stats
in dhanradar/mf/risk.py) and creates a new mf_category_stats table for per-category
p25/p50/p75/p90 percentile distributions (return_1y_pct, return_3y_pct,
max_drawdown_pct), refreshed nightly by _metrics_refresh_pipeline.

No data migration needed: new columns default to NULL; the nightly task fills them.
Reversible: downgrade drops the 7 columns and the table.

Revision ID: 0042
Revises: 0041
Create Date: 2026-06-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. Add 7 risk-metric columns to mf_fund_metrics (schema = "mf")    #
    # ------------------------------------------------------------------ #
    for col_name in (
        "sharpe_ratio",
        "sortino_ratio",
        "volatility_pct",
        "rolling_1y_avg_pct",
        "rolling_1y_min_pct",
        "rolling_1y_max_pct",
        "rolling_1y_pct_positive",
    ):
        op.add_column(
            "mf_fund_metrics",
            sa.Column(col_name, sa.Float(), nullable=True),
            schema="mf",
        )

    # ------------------------------------------------------------------ #
    # 2. Create mf_category_stats                                         #
    # ------------------------------------------------------------------ #
    op.create_table(
        "mf_category_stats",
        sa.Column("sebi_category", sa.Text(), nullable=False),
        sa.Column("metric_key", sa.Text(), nullable=False),
        sa.Column("p25", sa.Float(), nullable=True),
        sa.Column("p50", sa.Float(), nullable=True),
        sa.Column("p75", sa.Float(), nullable=True),
        sa.Column("p90", sa.Float(), nullable=True),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("sebi_category", "metric_key", "as_of"),
        schema="mf",
    )


def downgrade() -> None:
    # Drop mf_category_stats first (no dependants).
    op.drop_table("mf_category_stats", schema="mf")

    # Remove the 7 risk-metric columns from mf_fund_metrics.
    for col_name in (
        "sharpe_ratio",
        "sortino_ratio",
        "volatility_pct",
        "rolling_1y_avg_pct",
        "rolling_1y_min_pct",
        "rolling_1y_max_pct",
        "rolling_1y_pct_positive",
    ):
        op.drop_column("mf_fund_metrics", col_name, schema="mf")
