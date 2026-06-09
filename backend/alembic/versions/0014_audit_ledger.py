"""audit_ledger — append-only partitioned audit tables for admin actions,
payment events, and security events (B57 P2).

Creates a new `audit` schema with three RANGE-partitioned (monthly) tables,
DEFAULT partitions so every insert always lands, and a guarded pg_partman
block for 7-yr / 84-month retention (same pattern as 0006).

Per-row tamper hash (SHA-256 over business fields) is computed in Python
before insert — see dhanradar.audit.service.

NO FK on any audit column — these records must outlive user/subscription
deletion (SEBI 7-yr + DPDP erasure coexistence).

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")

    # ------------------------------------------------------------------
    # audit.admin_actions
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE audit.admin_actions (
            id          uuid        NOT NULL DEFAULT gen_random_uuid(),
            ts          timestamptz NOT NULL DEFAULT now(),
            admin_id    text        NOT NULL,
            action      text        NOT NULL,
            target_type text,
            target_id   text,
            result      text        NOT NULL,
            request_id  text,
            row_hash    text        NOT NULL,
            PRIMARY KEY (id, ts)
        ) PARTITION BY RANGE (ts)
        """
    )
    op.execute(
        "CREATE INDEX ix_audit_admin_actions_ts "
        "ON audit.admin_actions (ts)"
    )
    op.execute(
        "CREATE INDEX ix_audit_admin_actions_admin_id "
        "ON audit.admin_actions (admin_id)"
    )
    op.execute(
        "CREATE TABLE audit.admin_actions_default "
        "PARTITION OF audit.admin_actions DEFAULT"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_partman') THEN
            BEGIN
              PERFORM partman.create_parent(
                p_parent_table => 'audit.admin_actions',
                p_control      => 'ts',
                p_type         => 'range',
                p_interval     => '1 month',
                p_premake      => 4);
              UPDATE partman.part_config
                 SET retention = '84 months', retention_keep_table = false
               WHERE parent_table = 'audit.admin_actions';
            EXCEPTION WHEN OTHERS THEN
              RAISE NOTICE 'pg_partman registration skipped for admin_actions: %', SQLERRM;
            END;
          END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # audit.payment_events
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE audit.payment_events (
            id                   uuid        NOT NULL DEFAULT gen_random_uuid(),
            ts                   timestamptz NOT NULL DEFAULT now(),
            user_id              text        NOT NULL,
            order_id             text,
            razorpay_payment_id  text,
            status               text        NOT NULL,
            request_id           text,
            row_hash             text        NOT NULL,
            PRIMARY KEY (id, ts)
        ) PARTITION BY RANGE (ts)
        """
    )
    op.execute(
        "CREATE INDEX ix_audit_payment_events_ts "
        "ON audit.payment_events (ts)"
    )
    op.execute(
        "CREATE INDEX ix_audit_payment_events_user_id "
        "ON audit.payment_events (user_id)"
    )
    op.execute(
        "CREATE TABLE audit.payment_events_default "
        "PARTITION OF audit.payment_events DEFAULT"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_partman') THEN
            BEGIN
              PERFORM partman.create_parent(
                p_parent_table => 'audit.payment_events',
                p_control      => 'ts',
                p_type         => 'range',
                p_interval     => '1 month',
                p_premake      => 4);
              UPDATE partman.part_config
                 SET retention = '84 months', retention_keep_table = false
               WHERE parent_table = 'audit.payment_events';
            EXCEPTION WHEN OTHERS THEN
              RAISE NOTICE 'pg_partman registration skipped for payment_events: %', SQLERRM;
            END;
          END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # audit.security_events
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE audit.security_events (
            id          uuid        NOT NULL DEFAULT gen_random_uuid(),
            ts          timestamptz NOT NULL DEFAULT now(),
            event_type  text        NOT NULL,
            user_ref    text,
            request_id  text,
            row_hash    text        NOT NULL,
            PRIMARY KEY (id, ts)
        ) PARTITION BY RANGE (ts)
        """
    )
    op.execute(
        "CREATE INDEX ix_audit_security_events_ts "
        "ON audit.security_events (ts)"
    )
    op.execute(
        "CREATE INDEX ix_audit_security_events_event_type "
        "ON audit.security_events (event_type)"
    )
    op.execute(
        "CREATE TABLE audit.security_events_default "
        "PARTITION OF audit.security_events DEFAULT"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_partman') THEN
            BEGIN
              PERFORM partman.create_parent(
                p_parent_table => 'audit.security_events',
                p_control      => 'ts',
                p_type         => 'range',
                p_interval     => '1 month',
                p_premake      => 4);
              UPDATE partman.part_config
                 SET retention = '84 months', retention_keep_table = false
               WHERE parent_table = 'audit.security_events';
            EXCEPTION WHEN OTHERS THEN
              RAISE NOTICE 'pg_partman registration skipped for security_events: %', SQLERRM;
            END;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit.security_events CASCADE")
    op.execute("DROP TABLE IF EXISTS audit.payment_events CASCADE")
    op.execute("DROP TABLE IF EXISTS audit.admin_actions CASCADE")
    op.execute("DROP SCHEMA IF EXISTS audit")
