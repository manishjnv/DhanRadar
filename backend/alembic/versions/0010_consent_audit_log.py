"""consent_audit_log — DPDP consent grant/revoke audit trail (B44).

Creates the `consent` schema and the append-only `consent.consent_audit_log`
table that records every DPDP consent grant and revoke action.

Design invariants:
  * user_id has NO FK/CASCADE — the audit trail must survive a DPDP erasure
    of the auth.users row (right-to-erasure erases PII content, not the audit
    fact of consent itself).
  * action is constrained to ('grant', 'revoke') at the DB level.
  * Additive and reversible — downgrade drops the table but leaves the schema.

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-08
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS consent")

    op.execute(
        """
        CREATE TABLE consent.consent_audit_log (
            id               uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
            user_id          uuid        NOT NULL,
            purpose          text        NOT NULL,
            action           text        NOT NULL CHECK (action IN ('grant', 'revoke')),
            consent_version  text,
            request_id       text,
            created_at       timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        "CREATE INDEX ix_consent_audit_user "
        "ON consent.consent_audit_log (user_id, created_at)"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS consent.ix_consent_audit_user"
    )
    op.execute(
        "DROP TABLE IF EXISTS consent.consent_audit_log CASCADE"
    )
    # Leave the schema — shared resource, other tables may be added later.
