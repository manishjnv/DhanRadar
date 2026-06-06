"""compliance_schema — Compliance Audit module schema (architecture Global §4, B26).

Creates the `compliance` schema + the `disclaimers` registry (seeded with the
in-force disclaimer) + the immutable 7-yr `ai_recommendation_audit` trail.

`ai_recommendation_audit` is RANGE-partitioned monthly on `served_at` via raw SQL
(alembic's create_table can't express PARTITION BY). A **DEFAULT partition** is
created so an insert ALWAYS lands even before monthly partitions exist — a
never-lose-an-audit-row guarantee. pg_partman registration (auto monthly partitions
+ ~7-yr/84-month retention) is attempted but guarded: if the extension is absent or
the signature differs, it is skipped and the DEFAULT partition keeps the table fully
functional (the CI test DB builds the plain table from ORM metadata, not this file).

Additive + reversible. `user_id` has NO FK (the audit outlives a DPDP user erasure);
`disclaimer_version` is denormalized text (no hard FK) so a write is never lost.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-06
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# In-force disclaimer (mirrors dhanradar.scoring.engine.schemas DISCLAIMER_VERSION /
# DISCLOSURE_BUNDLE). Hardcoded here so the migration does not import app code.
_DISCLAIMER_VERSION = "2026-06-06.v1"
_DISCLOSURE_BUNDLE = (
    "Educational analysis only — not investment advice. Labels describe "
    "category-relative form, not a recommendation to buy, sell, hold, or switch."
)


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS compliance")

    op.execute(
        """
        CREATE TABLE compliance.disclaimers (
            version        text PRIMARY KEY,
            type           text NOT NULL DEFAULT 'ai_recommendation',
            content        text NOT NULL,
            active         boolean NOT NULL DEFAULT true,
            effective_from timestamptz NOT NULL DEFAULT now(),
            effective_to   timestamptz,
            created_at     timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # Dollar-quoted bundle text so the em-dash / commas need no escaping.
    op.execute(
        "INSERT INTO compliance.disclaimers (version, type, content, active) VALUES "
        f"('{_DISCLAIMER_VERSION}', 'ai_recommendation', $bundle${_DISCLOSURE_BUNDLE}$bundle$, true)"
    )

    op.execute(
        """
        CREATE TABLE compliance.ai_recommendation_audit (
            id                  uuid NOT NULL DEFAULT gen_random_uuid(),
            served_at           timestamptz NOT NULL DEFAULT now(),
            user_id             uuid,
            recommendation_type text NOT NULL,
            label               text,
            content_hash        text NOT NULL,
            model               text,
            prompt_version      text,
            confidence_score    numeric(5,4),
            confidence_band     text,
            disclaimer_version  text NOT NULL,
            surface             text,
            session_id          text,
            request_id          text,
            created_at          timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_audit_recommendation_type
                CHECK (recommendation_type IN ('educational_label', 'mood_regime')),
            PRIMARY KEY (id, served_at)
        ) PARTITION BY RANGE (served_at)
        """
    )
    op.execute(
        "CREATE INDEX ix_audit_user ON compliance.ai_recommendation_audit (user_id)"
    )
    op.execute(
        "CREATE INDEX ix_audit_served_at ON compliance.ai_recommendation_audit (served_at)"
    )
    # DEFAULT partition — guarantees every insert lands (never lose an audit row).
    op.execute(
        "CREATE TABLE compliance.ai_recommendation_audit_default "
        "PARTITION OF compliance.ai_recommendation_audit DEFAULT"
    )
    # pg_partman auto-partitioning + 7-yr (84-month) retention — guarded, optional.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_partman') THEN
            BEGIN
              PERFORM partman.create_parent(
                p_parent_table => 'compliance.ai_recommendation_audit',
                p_control      => 'served_at',
                p_type         => 'range',
                p_interval     => '1 month',
                p_premake      => 4);
              UPDATE partman.part_config
                 SET retention = '84 months', retention_keep_table = false
               WHERE parent_table = 'compliance.ai_recommendation_audit';
            EXCEPTION WHEN OTHERS THEN
              RAISE NOTICE 'pg_partman registration skipped: %', SQLERRM;
            END;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS compliance.ai_recommendation_audit CASCADE")
    op.execute("DROP TABLE IF EXISTS compliance.disclaimers")
    op.execute("DROP SCHEMA IF EXISTS compliance")
