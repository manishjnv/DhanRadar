"""mf.mf_fund_metrics — Phase 2 batch metrics
(docs/features/leaderboard-data-backend.md §8).

Adds 3 nullable columns computed by `dhanradar.tasks.mf._metrics_refresh_pipeline`
from the NAV series already loaded there (no new query): SIP XIRR (3Y/5Y) and
drawdown recovery days. Feeds 5 new leaderboard boards in
`_leaderboard_refresh_pipeline` — the wealth-creator board's since-launch
multiple is computed directly in that pipeline from the full `mf_nav_history`
table instead (not stored here; see `_since_launch_multiple` in tasks/mf.py).

Additive + reversible.

Revision ID: 0081
Revises: 0080
Create Date: 2026-08-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0081"
down_revision: str | None = "0080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mf_fund_metrics",
        sa.Column("sip_xirr_3y_pct", sa.Float(), nullable=True),
        schema="mf",
    )
    op.add_column(
        "mf_fund_metrics",
        sa.Column("sip_xirr_5y_pct", sa.Float(), nullable=True),
        schema="mf",
    )
    op.add_column(
        "mf_fund_metrics",
        sa.Column("recovery_days", sa.Integer(), nullable=True),
        schema="mf",
    )


def downgrade() -> None:
    op.drop_column("mf_fund_metrics", "recovery_days", schema="mf")
    op.drop_column("mf_fund_metrics", "sip_xirr_5y_pct", schema="mf")
    op.drop_column("mf_fund_metrics", "sip_xirr_3y_pct", schema="mf")
