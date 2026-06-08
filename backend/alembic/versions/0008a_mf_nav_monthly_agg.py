"""mf_nav_monthly_agg — TimescaleDB continuous aggregate for MF NAV history (B29).

Migration 0004 created the `mf.mf_nav_history` hypertable but DEFERRED the
continuous aggregate ("lands with the AMFI NAV pipeline"). This adds it: a
monthly roll-up (`first`/`last`/`avg` NAV per ISIN per month) that speeds the
long-range (1Y/3Y) cohort queries the rating-engine return-signals need.

TimescaleDB notes (version-sensitive — Allowed-APIs §0; verify at install):
  * `CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous)` CANNOT run inside
    a transaction block. Alembic wraps each migration in one, so we break out with
    an explicit `COMMIT` first (the standard CONCURRENTLY / continuous-aggregate
    workaround); subsequent statements then run auto-committed.
  * The whole step is GUARDED on the `timescaledb` extension, so a plain-Postgres
    box and the CI test DB (which builds tables from ORM metadata, not migrations)
    simply skip it — exactly like the 0004 hypertable step.

Revision ID: 0008a
Revises: 0008
Create Date: 2026-06-07

Note: renumbered from 0008 -> 0008a to linearize a duplicate-0008 branch
(0008_admin_compliance_tables also claimed 0008). This migration is
independent of the admin/compliance tables, so chaining it after 0008 is
order-safe. No production DB had been stamped at renumber time (pre-launch).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008a"
down_revision: Union[str, None] = "0008"
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
    # Plain-Postgres / CI test DB: no timescaledb → nothing to do (the per-fund
    # signals still read mf.mf_nav_history directly; the aggregate is an optimisation).
    if not _has_timescaledb():
        return

    # Continuous-aggregate DDL is non-transactional — end Alembic's transaction.
    op.execute("COMMIT")
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mf.mf_nav_monthly_agg
        WITH (timescaledb.continuous) AS
        SELECT
            isin,
            time_bucket(INTERVAL '1 month', nav_date) AS bucket,
            first(nav, nav_date) AS first_nav,
            last(nav, nav_date)  AS last_nav,
            avg(nav)             AS avg_nav,
            count(*)             AS points
        FROM mf.mf_nav_history
        GROUP BY isin, bucket
        WITH NO DATA;
        """
    )
    # Refresh policy: keep ~3y of buckets current, leave the last day to the
    # real-time aggregation layer; reconcile daily.
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('mf.mf_nav_monthly_agg',
            start_offset      => INTERVAL '3 years',
            end_offset        => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day',
            if_not_exists     => TRUE);
        """
    )


def downgrade() -> None:
    if not _has_timescaledb():
        return
    op.execute("COMMIT")
    # Dropping the materialized view also removes its continuous-aggregate policy.
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mf.mf_nav_monthly_agg")
