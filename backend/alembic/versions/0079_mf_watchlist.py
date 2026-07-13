"""Per-user MF watchlist — mf.mf_watchlist_items + owner RLS.

Backs the fund-detail hero "☆ Watchlist" star and /mf/watchlist for logged-in
users (anonymous users keep the localStorage store). One row per
(user_id, isin); the fund's display data is joined client-side from
fund.head, so no denormalized name/category columns.

Additive + reversible. Mirrors the 0056 personal-table pattern:
guarded GRANT to dhanradar_app + owner-isolation RLS from db_security.

Revision ID: 0079
Revises: 0078
Create Date: 2026-07-13
"""

from __future__ import annotations

from alembic import op
from dhanradar.db_security import rls_downgrade_statements, rls_statements

revision: str = "0079"
down_revision: str | None = "0078"
branch_labels = None
depends_on = None

_TABLE = "mf.mf_watchlist_items"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mf.mf_watchlist_items (
            id          uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
            user_id     uuid        NOT NULL
                REFERENCES auth.users(id) ON DELETE CASCADE,
            isin        text        NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_mf_watchlist_user_isin UNIQUE (user_id, isin)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_mf_watchlist_items_user
            ON mf.mf_watchlist_items (user_id);
        """
    )
    # App role needs DELETE too (star-off removes the row) — still no UPDATE:
    # a watchlist row is add/remove only.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regrole('dhanradar_app') IS NOT NULL THEN
                GRANT SELECT, INSERT, DELETE ON mf.mf_watchlist_items
                    TO dhanradar_app;
            END IF;
        END $$;
        """
    )
    for stmt in rls_statements(_TABLE):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in rls_downgrade_statements(_TABLE):
        op.execute(stmt)
    op.execute("DROP TABLE IF EXISTS mf.mf_watchlist_items;")
