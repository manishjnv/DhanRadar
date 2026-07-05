"""mf_funds: add aum_as_of column (per-scheme AUM disclosure-month provenance).

aum_crore already existed (migration 0004) but had no freshness/provenance column,
so its "as of" date was untraceable. aum_as_of stores the SEBI monthly portfolio
disclosure file's own as_of_month for that value -- never the ingestion run time
(§8.4 no-fabrication). Nullable: existing aum_crore rows (all NULL today; see
docs/rca/README.md AUM-extraction root-cause entry, 2026-07-05) get no invented date.

Revision ID: 0069
Revises: 0068
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0069"
down_revision: str | None = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mf_funds",
        sa.Column("aum_as_of", sa.Date(), nullable=True),
        schema="mf",
    )


def downgrade() -> None:
    op.drop_column("mf_funds", "aum_as_of", schema="mf")
