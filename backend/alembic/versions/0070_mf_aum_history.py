"""mf.aum_history — per-scheme AUM time series + aum_change event type.

`mf_funds.aum_crore`/`aum_as_of` (migrations 0004/0069) are overwritten in place on
every `_upsert_constituents` run — there was no history table to look back on month
over month. This adds `mf.aum_history`: one row per (isin, as_of_month), upserted
from the same SEBI monthly disclosure net-assets row already used to write
`mf_funds.aum_crore` (§8.4 — genuine scheme-level data only, never derived from an
AMC aggregate). `run_id` mirrors the nullable, unconstrained-FK convention used by
`mf_fund_manager_history`/`expense_ratio_history` (a real FK to `mf.ingestion_runs`,
nullable because `_upsert_constituents`'s current callers don't yet thread a run_id
through an `ingestion_run()` context).

Also extends `mf_fund_events.event_type` to allow `'aum_change'` (fourth What-Changed
event type, FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §10.6/§17 W2) — bundled into this
migration since both are one feature (per-scheme AUM tracking + its diff event).

Additive + reversible.

Revision ID: 0070
Revises: 0069
Create Date: 2026-07-06
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0070"
down_revision: str | None = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "aum_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("aum_crore", sa.Numeric(14, 2), nullable=False),
        sa.Column("as_of_month", sa.Date(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "run_id",
            sa.BigInteger(),
            sa.ForeignKey("mf.ingestion_runs.run_id"),
            nullable=True,
        ),
        sa.Column(
            "ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        schema="mf",
    )
    # A single unique index on (isin, as_of_month) serves both the upsert-conflict target
    # AND the last-two-rows lookback query the aum_change detector runs (partition by isin,
    # order by as_of_month) -- a second plain index on the identical column pair would be
    # redundant (same leading columns, no additional query shape it uniquely serves).
    op.create_index(
        "uq_mf_aum_history_isin_month",
        "aum_history",
        ["isin", "as_of_month"],
        unique=True,
        schema="mf",
    )

    op.drop_constraint("ck_mf_fund_events_event_type", "mf_fund_events", schema="mf", type_="check")
    op.create_check_constraint(
        "ck_mf_fund_events_event_type",
        "mf_fund_events",
        "event_type IN ('rank_change', 'ter_change', 'holding_change', 'aum_change')",
        schema="mf",
    )


def downgrade() -> None:
    op.drop_constraint("ck_mf_fund_events_event_type", "mf_fund_events", schema="mf", type_="check")
    op.create_check_constraint(
        "ck_mf_fund_events_event_type",
        "mf_fund_events",
        "event_type IN ('rank_change', 'ter_change', 'holding_change')",
        schema="mf",
    )

    op.drop_index("uq_mf_aum_history_isin_month", table_name="aum_history", schema="mf")
    op.drop_table("aum_history", schema="mf")
