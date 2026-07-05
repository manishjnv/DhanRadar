"""mf.mf_fund_events — What-Changed diff-engine events
(FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §10.6/§17 W2).

Populated by `dhanradar.tasks.mf.fund_events_refresh` (nightly 01:15 IST, after
compute_market_ranks at 01:00). One row per detected rank/TER/holding-weight change,
FACTS only (payload never carries an advisory framing) — the request-time summary
sentence is templated from payload in `mf/fund_events.py`, not stored.

Additive + reversible.

Revision ID: 0067
Revises: 0066
Create Date: 2026-07-05
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0067"
down_revision: str | None = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mf_fund_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "event_type IN ('rank_change', 'ter_change', 'holding_change')",
            name="ck_mf_fund_events_event_type",
        ),
        schema="mf",
    )
    op.create_index(
        "uq_mf_fund_events_isin_type_date",
        "mf_fund_events",
        ["isin", "event_type", "as_of"],
        unique=True,
        schema="mf",
    )
    op.create_index(
        "ix_mf_fund_events_isin_as_of",
        "mf_fund_events",
        ["isin", "as_of"],
        schema="mf",
    )


def downgrade() -> None:
    op.drop_index("ix_mf_fund_events_isin_as_of", table_name="mf_fund_events", schema="mf")
    op.drop_index("uq_mf_fund_events_isin_type_date", table_name="mf_fund_events", schema="mf")
    op.drop_table("mf_fund_events", schema="mf")
