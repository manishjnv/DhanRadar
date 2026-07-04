"""Add mf_funds.isin2 — AMFI plan-variant secondary ISIN (2026-07-04 double-count incident,
defect 2 of 3).

AMFI issues TWO ISINs per scheme-plan line (growth/payout ISIN + the dividend-reinvestment
variant's ISIN), concatenated with no separator in the Scheme Master's final CSV field
(amfi_scheme_master.parse_scheme_master already splits both via a 12-char regex findall —
isin_growth / isin_reinvest). Only the canonical one (isin_growth or isin_reinvest) was ever
written to mf_funds; the OTHER was silently discarded (tasks/mf_scheme_master.py picked one and
never stored the loser). A CAS printed under the discarded ISIN then had no mf_funds row to key
against and became a SECOND, un-aliased holding for the same real position — the founder's HDFC
Mid Cap counted twice: INF179K01XO5 from the CAMS TDS resolver, INF179K01XP2 from the
consolidated KFin PDF.

isin2 is nullable (most schemes have no reinvest variant) with a unique-where-not-null index — a
secondary ISIN maps to exactly one primary scheme. Ingest-time aliasing
(dhanradar.mf.cas.alias_secondary_isins) rewrites any parsed holding keyed on isin2 to its
primary isin before ledger fingerprinting.

Revision ID: 0062
Revises: 0061
Create Date: 2026-07-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0062"
down_revision: str | None = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mf_funds", sa.Column("isin2", sa.Text(), nullable=True), schema="mf")
    op.create_index(
        "uq_mf_funds_isin2",
        "mf_funds",
        ["isin2"],
        unique=True,
        schema="mf",
        postgresql_where=sa.text("isin2 IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_mf_funds_isin2", table_name="mf_funds", schema="mf")
    op.drop_column("mf_funds", "isin2", schema="mf")
