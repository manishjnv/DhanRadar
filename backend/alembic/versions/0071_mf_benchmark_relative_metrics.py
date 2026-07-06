"""mf_benchmark_relative_metrics — alpha/beta/tracking error per fund (Block 0.7).

Adds 3 nullable Float columns to mf_fund_metrics (computed by
benchmark_relative_stats in dhanradar/mf/risk.py, populated only for funds
with a non-null mf_funds.benchmark_index — index funds mapped with high
confidence via mf/benchmark_mapping.py). No data migration needed: new
columns default to NULL; the nightly _metrics_refresh_pipeline fills them for
mapped funds only. Reversible: downgrade drops the 3 columns.

Revision ID: 0071
Revises: 0070
Create Date: 2026-07-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0071"
down_revision: str | None = "0070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for col_name in ("alpha_1y", "beta_1y", "tracking_error_pct"):
        op.add_column(
            "mf_fund_metrics",
            sa.Column(col_name, sa.Float(), nullable=True),
            schema="mf",
        )


def downgrade() -> None:
    for col_name in ("tracking_error_pct", "beta_1y", "alpha_1y"):
        op.drop_column("mf_fund_metrics", col_name, schema="mf")
