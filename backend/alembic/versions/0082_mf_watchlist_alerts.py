"""Per-user watchlist alert rows — mf.mf_watchlist_alerts + owner RLS.

Fired daily by the watchlist_alerts Celery task; read by
GET /api/v1/mf/watchlist/alerts (newest-first, max 50).

Additive + reversible. Mirrors the 0079 watchlist pattern:
guarded GRANT to dhanradar_app + owner-isolation RLS from db_security.

Revision ID: 0082
Revises: 0081
Create Date: 2026-08-21
"""

from __future__ import annotations

from alembic import op
from dhanradar.db_security import rls_downgrade_statements, rls_statements

revision: str = "0082"
down_revision: str | None = "0081"
branch_labels = None
depends_on = None

_TABLE = "mf.mf_watchlist_alerts"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mf.mf_watchlist_alerts (
            id           uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
            user_id      uuid        NOT NULL
                REFERENCES auth.users(id) ON DELETE CASCADE,
            isin         text        NOT NULL,
            alert_type   text        NOT NULL
                CHECK (alert_type IN ('nav_move', 'label_change')),
            title        text        NOT NULL,
            body         text        NOT NULL,
            triggered_on date        NOT NULL,
            created_at   timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_mf_watchlist_alert
                UNIQUE (user_id, isin, alert_type, triggered_on)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_mf_watchlist_alerts_user_created
            ON mf.mf_watchlist_alerts (user_id, created_at DESC);
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regrole('dhanradar_app') IS NOT NULL THEN
                GRANT SELECT, INSERT ON mf.mf_watchlist_alerts TO dhanradar_app;
            END IF;
        END $$;
        """
    )
    for stmt in rls_statements(_TABLE):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in rls_downgrade_statements(_TABLE):
        op.execute(stmt)
    op.execute("DROP TABLE IF EXISTS mf.mf_watchlist_alerts;")
