"""mf_funds: add fund_name_short + idcw_frequency, widen plan_type (B72 follow-up).

Adds a derived, DISPLAY-ONLY clean name (``fund_name_short``) and the IDCW payout
cadence (``idcw_frequency``) to mf.mf_funds, so every surface reads a clean name
from one server-side source of truth (``taxonomy.derive_short_name``). The official
AMFI ``scheme_name`` is unchanged and remains the immutable legal name.

Also widens ``plan_type`` String(10) → String(20) so the newly-recognised
``'institutional'`` plan value (13 chars) fits.

Backfill: existing rows are populated in-place using the same pure helpers the
nightly ``nav_daily_fetch`` upsert uses (``derive_short_name`` /
``parse_idcw_frequency``), so backfilled and freshly-ingested values are identical.

Reversible: downgrade drops both columns and narrows ``plan_type`` back to
String(10). The narrow assumes no value exceeds 10 chars (true unless an
``institutional`` plan was ingested before rollback) — an honest loud failure if not.

Revision ID: 0043
Revises: 0042
Create Date: 2026-06-22
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels = None
depends_on = None

# Backfill batch size — bounds the executemany statement size.
_BACKFILL_CHUNK = 2000


def upgrade() -> None:
    op.add_column(
        "mf_funds",
        sa.Column("fund_name_short", sa.Text(), nullable=True),
        schema="mf",
    )
    op.add_column(
        "mf_funds",
        sa.Column("idcw_frequency", sa.Text(), nullable=True),
        schema="mf",
    )
    # Widen plan_type to fit 'institutional' (13 chars).
    op.alter_column(
        "mf_funds",
        "plan_type",
        existing_type=sa.String(10),
        type_=sa.String(20),
        existing_nullable=True,
        schema="mf",
    )

    _backfill()


def _backfill() -> None:
    """Populate fund_name_short + idcw_frequency for existing rows.

    Imports the live pure helpers so backfilled values match the nightly upsert
    bit-for-bit (single source of truth). No-ops cleanly on an empty table (CI).
    """
    from dhanradar.mf.taxonomy import derive_short_name, parse_idcw_frequency

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT isin, scheme_name FROM mf.mf_funds")
    ).all()

    updates: list[dict] = []
    for isin, scheme_name in rows:
        updates.append(
            {
                "isin": isin,
                "short": derive_short_name(scheme_name, isin),
                "freq": parse_idcw_frequency(scheme_name),
            }
        )

    stmt = sa.text(
        "UPDATE mf.mf_funds SET fund_name_short = :short, idcw_frequency = :freq"
        " WHERE isin = :isin"
    )
    for i in range(0, len(updates), _BACKFILL_CHUNK):
        chunk = updates[i : i + _BACKFILL_CHUNK]
        if chunk:
            bind.execute(stmt, chunk)


def downgrade() -> None:
    op.drop_column("mf_funds", "idcw_frequency", schema="mf")
    op.drop_column("mf_funds", "fund_name_short", schema="mf")
    op.alter_column(
        "mf_funds",
        "plan_type",
        existing_type=sa.String(20),
        type_=sa.String(10),
        existing_nullable=True,
        schema="mf",
    )
