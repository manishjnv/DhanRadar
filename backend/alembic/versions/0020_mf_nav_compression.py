"""mf_nav_compression — native columnar compression on the mf_nav_history hypertable.

mf_nav_history is append-mostly time-series (one NAV per ISIN per day, ~250 rows/yr
per plan-level scheme, growing toward a full 20-year history across ~45k schemes).
TimescaleDB native columnar compression on this shape yields large reductions
(commonly 90%+), keeping the master NAV store well within the 1 GB Postgres working
set on the shared box.

Settings:
  * segmentby = isin     — queries always filter/group by ISIN (per-fund signals,
    cohort medians); segmenting by ISIN keeps each fund's series co-located.
  * orderby   = nav_date DESC — recent NAV is read most (latest value, trailing
    windows); DESC order makes the hot rows the cheapest to fetch.
  The (isin, nav_date) PRIMARY KEY / unique constraint is fully covered by
  segmentby+orderby, so compression is permitted on this hypertable.

compress_after = 5 years. RATIONALE / backfill-safety (load-bearing):
  INSERT ... ON CONFLICT DO UPDATE into a COMPRESSED chunk HARD-ERRORS on
  TimescaleDB 2.x (the auto-decompress path covers plain INSERT only, NOT the
  conflict/update path). Both writers to this table use ON CONFLICT:
    * daily AMFI fetch — writes only the CURRENT day → always a recent, uncompressed
      chunk → never affected, at any horizon.
    * manual `nav_backfill(years=N)` — upserts historical windows back N*365 days.
  A 5-year horizon means NOTHING inside the last 5 years is ever compressed, so every
  ROUTINE backfill (default years=3; safe up to years=5) lands entirely in
  uncompressed chunks. Compression only acts on data >5 years old — i.e. on the deep
  historical tail of the 20-year master store, exactly where the storage win matters
  and where re-writes are rare. The initial deep (20-year) backfill is also safe: it
  runs before any >5y data exists to be compressed. A DEEP RE-backfill (re-writing
  data >5y old, a rare repair) must first decompress the target range
  (`SELECT decompress_chunk(c, if_compressed => TRUE) FROM show_chunks('mf.mf_nav_history', older_than => ...) c`)
  or temporarily remove the policy; the daily compression job recompresses afterward.

Guarded on the timescaledb extension (plain-Postgres box + CI test DB skip it,
exactly like 0004's hypertable step). Unlike a continuous aggregate, compression DDL
+ policy scheduling are transaction-safe, so this migration runs INSIDE Alembic's
transaction (no COMMIT break-out): a failed apply rolls back fully and is re-runnable.

Reversible: downgrade removes the policy, decompresses all chunks, then disables
compression (compression cannot be turned off while compressed chunks exist).

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-13
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_timescaledb() -> bool:
    bind = op.get_bind()
    return bool(
        bind.execute(
            sa.text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
        ).scalar()
    )


def upgrade() -> None:
    # Plain-Postgres / CI test DB: no timescaledb → nothing to do. The NAV store
    # still works uncompressed; compression is purely a storage optimisation.
    if not _has_timescaledb():
        return

    # Transaction-safe (no COMMIT break-out): if add_compression_policy fails, the
    # ALTER rolls back with it, leaving the table un-compressed and the migration
    # cleanly re-runnable.
    op.execute(
        """
        ALTER TABLE mf.mf_nav_history SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'isin',
            timescaledb.compress_orderby = 'nav_date DESC'
        )
        """
    )
    op.execute(
        """
        SELECT add_compression_policy('mf.mf_nav_history', INTERVAL '5 years',
                                      if_not_exists => TRUE)
        """
    )


def downgrade() -> None:
    if not _has_timescaledb():
        return
    op.execute("SELECT remove_compression_policy('mf.mf_nav_history', if_exists => TRUE)")
    # Compression cannot be disabled while compressed chunks remain — decompress all.
    op.execute(
        """
        DO $$
        DECLARE ch regclass;
        BEGIN
          FOR ch IN SELECT show_chunks('mf.mf_nav_history') LOOP
            PERFORM decompress_chunk(ch, if_compressed => TRUE);
          END LOOP;
        END $$;
        """
    )
    op.execute("ALTER TABLE mf.mf_nav_history SET (timescaledb.compress = false)")
