"""mfu schema + mfu_api_log evidence ledger (MFU Phase 0 — foundation only, no orders).

Creates the `mfu` schema and `mfu.mfu_api_log` — one row per outbound MFU API
attempt (OAuth login + service calls), scrubbed before write, mirroring the
role `bse.webhook_events` plays for the BSE rail. `unique_id` is UNIQUE (MFU's
own uniqueId, never repeats). No FK on any column — MFU identifiers are not our
user ids (module isolation, non-neg #7); mfu_api_log is NOT personal user data
so it carries no RLS (mirrors bse.webhook_events).

Grants BOTH runtime roles USAGE + table privileges on the new schema — this
schema is created AFTER the roles (0051/0052 for dhanradar_app, 0053 for
dhanradar_admin), unlike every other APP_SCHEMAS entry, so (unlike those) it
needs its own grant block here rather than relying on those one-time loops.
dhanradar_admin (BYPASSRLS) is the role `get_admin_db` uses for every
admin/mfu-uat/* route (db.py), so it needs the grant too — SELECT, INSERT only
(append-only evidence ledger, no UPDATE/DELETE, same spirit as 0053's audit
revoke). Keep `dhanradar.db_schemas.APP_SCHEMAS` in sync (done in this same
change).

Additive + reversible.

Revision ID: 0083
Revises: 0082
Create Date: 2026-09-29
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0083"
down_revision: str | None = "0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS mfu")

    op.create_table(
        "mfu_api_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("unique_id", sa.String(50), nullable=False),
        sa.Column("api_type", sa.String(30), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("resp_flag", sa.String(1), nullable=True),
        sa.Column("error_code", sa.String(20), nullable=True),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("request_json", postgresql.JSONB(), nullable=True),
        sa.Column("response_json", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("unique_id", name="uq_mfu_api_log_unique_id"),
        schema="mfu",
    )
    op.create_index("ix_mfu_api_log_created_at", "mfu_api_log", ["created_at"], schema="mfu")

    op.execute(
        """
        DO $$
        BEGIN
            IF to_regrole('dhanradar_app') IS NOT NULL THEN
                GRANT USAGE ON SCHEMA mfu TO dhanradar_app;
                GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA mfu TO dhanradar_app;
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA mfu TO dhanradar_app;
                ALTER DEFAULT PRIVILEGES IN SCHEMA mfu GRANT SELECT, INSERT ON TABLES TO dhanradar_app;
                ALTER DEFAULT PRIVILEGES IN SCHEMA mfu GRANT USAGE, SELECT ON SEQUENCES TO dhanradar_app;
            END IF;

            -- get_admin_db (db.py) runs every admin/mfu-uat/* route as dhanradar_admin
            -- (BYPASSRLS) — same append-only privileges, no UPDATE/DELETE.
            IF to_regrole('dhanradar_admin') IS NOT NULL THEN
                GRANT USAGE ON SCHEMA mfu TO dhanradar_admin;
                GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA mfu TO dhanradar_admin;
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA mfu TO dhanradar_admin;
                ALTER DEFAULT PRIVILEGES IN SCHEMA mfu GRANT SELECT, INSERT ON TABLES TO dhanradar_admin;
                ALTER DEFAULT PRIVILEGES IN SCHEMA mfu GRANT USAGE, SELECT ON SEQUENCES TO dhanradar_admin;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Undo the default-ACL entries for BOTH roles first — a leftover default ACL
    # referencing a role in the about-to-be-dropped schema can make DROP SCHEMA
    # (or a later re-run of upgrade) behave unexpectedly on some Postgres
    # versions, and CI's upgrade -> downgrade base -> upgrade round-trip must be
    # clean. Idempotent + guarded exactly like the upgrade grants.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regrole('dhanradar_app') IS NOT NULL THEN
                ALTER DEFAULT PRIVILEGES IN SCHEMA mfu REVOKE SELECT, INSERT ON TABLES FROM dhanradar_app;
                ALTER DEFAULT PRIVILEGES IN SCHEMA mfu REVOKE USAGE, SELECT ON SEQUENCES FROM dhanradar_app;
            END IF;
            IF to_regrole('dhanradar_admin') IS NOT NULL THEN
                ALTER DEFAULT PRIVILEGES IN SCHEMA mfu REVOKE SELECT, INSERT ON TABLES FROM dhanradar_admin;
                ALTER DEFAULT PRIVILEGES IN SCHEMA mfu REVOKE USAGE, SELECT ON SEQUENCES FROM dhanradar_admin;
            END IF;
        END $$;
        """
    )
    op.drop_table("mfu_api_log", schema="mfu")
    op.execute("DROP SCHEMA IF EXISTS mfu")
