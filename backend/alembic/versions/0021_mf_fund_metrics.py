"""mf_fund_metrics — precomputed per-fund long-horizon stats table.

Adds ``mf.mf_fund_metrics`` — a nightly-refreshed cache of each fund's
``long_horizon_stats()`` output (return_1y_pct, return_3y_pct,
max_drawdown_pct) so the cohort builder reads precomputed rows instead of
loading ~6M NAV rows into worker memory (B63 memory cap).

Columns use ``DOUBLE PRECISION`` (sa.Float) — NOT Numeric — because Python
float ↔ float8 round-trips exactly; Numeric would round and break bit-identity
with the signals.py calculation.

Plain additive table; no TimescaleDB / hypertable (this is a keyed lookup
table, not a time-series). Reversible downgrade drops the table.

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-13
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mf_fund_metrics",
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("return_1y_pct", sa.Float(), nullable=True),
        sa.Column("return_3y_pct", sa.Float(), nullable=True),
        sa.Column("max_drawdown_pct", sa.Float(), nullable=True),
        sa.Column(
            "nav_points",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("isin"),
        schema="mf",
    )


def downgrade() -> None:
    op.drop_table("mf_fund_metrics", schema="mf")
