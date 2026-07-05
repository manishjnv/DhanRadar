"""mf.mf_category_flows — add scheme_type to the dedup key (data-accuracy fix).

Found 2026-07-05 while verifying the scheduled pull's accuracy (post-deploy
smoke test of PR #469): AMFI's raw monthly report reuses the SAME leaf category
label under more than one top-level scheme_type in the same month — e.g. "ELSS"
appears once under "Open ended Schemes" and once under "Close Ended Schemes".
The original `uq_mf_category_flows_month_category` constraint (period_month,
scheme_category) could not distinguish the two, so the second row silently
overwrote/collided with the first at upsert — one category's real flow figures
were being dropped every month. Confirmed against the live May-2026 prod data:
the raw file has 45 real leaf rows / 45 distinct (scheme_type, category) pairs,
but only 44 were ever stored.

All 44 rows currently live in prod (ingested via the initial manual trigger,
before this fix) are Open-ended-only categories — the dropped row was the
Close-Ended ELSS one — so backfilling every existing row's `scheme_type` to
'Open ended Schemes' is safe and correct for 100% of the current data. The next
task run re-upserts all rows with the real per-row scheme_type (including the
previously-missing Close-Ended ELSS row) — this migration only needs to get
the column/constraint into a consistent state, not the numbers right.

Revision ID: 0068
Revises: 0067
Create Date: 2026-07-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0068"
down_revision: str | None = "0067"
branch_labels = None
depends_on = None

_OLD_CONSTRAINT = "uq_mf_category_flows_month_category"
_NEW_CONSTRAINT = "uq_mf_category_flows_month_type_category"


def upgrade() -> None:
    op.add_column(
        "mf_category_flows",
        sa.Column("scheme_type", sa.Text(), nullable=True),
        schema="mf",
    )
    # Every row currently in prod is an Open-ended category (the one row this
    # bug ever dropped was Close-Ended ELSS) — safe, correct backfill.
    op.execute(
        "UPDATE mf.mf_category_flows SET scheme_type = 'Open ended Schemes' "
        "WHERE scheme_type IS NULL"
    )
    op.alter_column("mf_category_flows", "scheme_type", nullable=False, schema="mf")
    op.drop_constraint(_OLD_CONSTRAINT, "mf_category_flows", schema="mf", type_="unique")
    op.create_unique_constraint(
        _NEW_CONSTRAINT,
        "mf_category_flows",
        ["period_month", "scheme_type", "scheme_category"],
        schema="mf",
    )


def downgrade() -> None:
    op.drop_constraint(_NEW_CONSTRAINT, "mf_category_flows", schema="mf", type_="unique")
    op.create_unique_constraint(
        _OLD_CONSTRAINT,
        "mf_category_flows",
        ["period_month", "scheme_category"],
        schema="mf",
    )
    op.drop_column("mf_category_flows", "scheme_type", schema="mf")
