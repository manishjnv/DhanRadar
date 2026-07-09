"""mf.mf_funds — min_lumpsum_amount / min_sip_amount (BSE StAR scheme master).

The BSE StAR MF v2 scheme master is the ONE source carrying per-scheme minimum
lumpsum/SIP amounts (verified 2026-07-10 — no SEBI disclosure file publishes
them). Written by tasks/bse_enrich.py, exact per-ISIN, prod-gated. Additive +
reversible.

Revision ID: 0074
Revises: 0073
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0074"
down_revision: str | None = "0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mf_funds",
        sa.Column("min_lumpsum_amount", sa.Numeric(14, 2), nullable=True),
        schema="mf",
    )
    op.add_column(
        "mf_funds",
        sa.Column("min_sip_amount", sa.Numeric(14, 2), nullable=True),
        schema="mf",
    )


def downgrade() -> None:
    op.drop_column("mf_funds", "min_sip_amount", schema="mf")
    op.drop_column("mf_funds", "min_lumpsum_amount", schema="mf")
