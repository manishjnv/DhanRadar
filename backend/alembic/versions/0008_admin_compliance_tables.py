"""admin_compliance_tables — Rating-engine changelog + AI low-confidence log (B6/B28, B20-style).

Creates two append-only tables in the existing `compliance` schema:

* ``compliance.rating_engine_changelog`` — one row per methodology version change;
  written by the B6/B28 two-person scoring-activation gate (slice 2). Stores factors
  before/after, methodology URL, and the two-person approval outcome so every weight
  change is reproducible for SEBI purposes (spec §8 / architecture §S4).

* ``compliance.ai_low_confidence_log`` — one row per AI/scoring surface emission that
  fell below the confidence floor; no writer wired yet (the AI/scoring consumer
  planned in B22 calls this). Built ahead like B20's call site so the schema is
  stable before the consumer lands.

Additive + reversible. The `compliance` schema already exists (migration 0006).

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-07
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # compliance schema already created by 0006 — no CREATE SCHEMA needed.

    op.execute(
        """
        CREATE TABLE compliance.rating_engine_changelog (
            id              uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
            model_version   text        NOT NULL,
            created_by      text        NOT NULL,
            approved_by     text,
            two_person_ok   boolean     NOT NULL DEFAULT false,
            factors_before  jsonb       NOT NULL DEFAULT '{}',
            factors_after   jsonb       NOT NULL DEFAULT '{}',
            methodology_url text,
            activated       boolean     NOT NULL DEFAULT false,
            activated_at    timestamptz,
            created_at      timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE compliance.ai_low_confidence_log (
            id               uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
            logged_at        timestamptz NOT NULL DEFAULT now(),
            surface          text,
            identifier       text,
            confidence_score numeric(5,4),
            confidence_band  text,
            model            text,
            reason           text,
            request_id       text,
            created_at       timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_low_conf_logged_at "
        "ON compliance.ai_low_confidence_log (logged_at)"
    )

    # Enforce the single-active-per-type disclaimer invariant atomically at the DB
    # level (closes the concurrent-activation TOCTOU the application layer cannot).
    # Partial unique: at most one row per `type` may have `active = TRUE`.
    op.execute(
        "CREATE UNIQUE INDEX uq_disclaimer_active_per_type "
        "ON compliance.disclaimers (type) WHERE active"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS compliance.uq_disclaimer_active_per_type")
    op.execute(
        "DROP TABLE IF EXISTS compliance.ai_low_confidence_log CASCADE"
    )
    op.execute(
        "DROP TABLE IF EXISTS compliance.rating_engine_changelog CASCADE"
    )
