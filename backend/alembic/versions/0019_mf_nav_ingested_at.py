"""mf_nav_ingested_at — add ingestion-provenance timestamp to mf_nav_history.

Data-platform six-question provenance (Data-Ingestion governance, Critical Rule #2)
requires every record to answer "when received". mf_nav_history previously carried
only `source` ("where from") and `nav_date` ("as of when"); the ingestion wall-clock
was missing.

Design — honest provenance, no fabrication (invariant: no imputation):
  * The column is added NULLABLE with NO column-level default in the ADD COLUMN, so
    the ~2M rows already backfilled (whose true ingestion time is unknown) stay NULL
    rather than being stamped with a fake migration-time value.
  * A DEFAULT now() is then attached for FUTURE inserts; the daily/backfill upserts
    additionally set ingested_at = now() on conflict (last-ingested semantics).

Hypertable-safe: a plain `ALTER TABLE ADD COLUMN` of a nullable column with no
default is metadata-only and propagates to all TimescaleDB chunks; it runs whether
or not the timescaledb extension is present, so no extension guard is needed here.
This migration MUST precede the compression migration (0020): ADD COLUMN on a
hypertable is unrestricted only while its chunks are uncompressed.

Additive + reversible.

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-13
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Add the column nullable, NO default → existing rows stay NULL (unknown).
    op.add_column(
        "mf_nav_history",
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        schema="mf",
    )
    # 2) Attach a server default so future inserts auto-stamp the ingestion time.
    op.execute("ALTER TABLE mf.mf_nav_history ALTER COLUMN ingested_at SET DEFAULT now()")


def downgrade() -> None:
    op.drop_column("mf_nav_history", "ingested_at", schema="mf")
