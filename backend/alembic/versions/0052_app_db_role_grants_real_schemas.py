"""B80 grant-gap fix: grant dhanradar_app on the REAL schema set (the 13 migrations create).

Migration 0051 granted an *aspirational* 17-schema list copied from 01_init.sql — missing 7
schemas the app/Celery actually write (audit, billing, bse, concepts, education, notify [typo'd
`notif`], signal) and granting ~11 phantom schemas. The config fallback masked it, but the deploy
that sets DHANRADAR_APP_DB_PASSWORD switches the app to dhanradar_app and every query into those 7
schemas would fail `permission denied` → prod outage. This re-grants the canonical 13 idempotently
(superset of 0051, so re-granting the 6 it got right is a no-op), with EXECUTE + future-table
defaults, guarding each schema's existence (to_regnamespace) so a DB missing a schema NOTICE-skips
instead of erroring.

The 13 below MUST match `dhanradar.db_schemas.APP_SCHEMAS` (the single source the conftest fixtures
and the per-schema regression test read; the test fails if the live set drifts).

Revision ID: 0052
Revises: 0051
Create Date: 2026-06-27
"""

from __future__ import annotations

from alembic import op

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels = None
depends_on = None

# Keep in sync with dhanradar.db_schemas.APP_SCHEMAS (frozen here per Alembic convention).
_SCHEMAS = [
    "auth", "billing", "mf", "notify", "compliance", "mood", "consent",
    "audit", "education", "news", "concepts", "signal", "bse",
]
_SCHEMA_ARRAY = "ARRAY[" + ", ".join(f"'{s}'" for s in _SCHEMAS) + "]"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        DECLARE s text;
        BEGIN
            FOREACH s IN ARRAY {_SCHEMA_ARRAY} LOOP
                IF to_regnamespace(s) IS NULL THEN
                    RAISE NOTICE 'schema % absent — skipping dhanradar_app grants', s;
                    CONTINUE;
                END IF;
                EXECUTE format('GRANT USAGE ON SCHEMA %I TO dhanradar_app', s);
                EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO dhanradar_app', s);
                EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO dhanradar_app', s);
                EXECUTE format('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA %I TO dhanradar_app', s);
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO dhanradar_app', s);
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT USAGE, SELECT ON SEQUENCES TO dhanradar_app', s);
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT EXECUTE ON FUNCTIONS TO dhanradar_app', s);
            END LOOP;

            -- Append-only audit integrity (SEBI 7-yr / DPDP): the runtime role WRITES + READS
            -- audit records but must NEVER mutate or delete them. Revoke UPDATE/DELETE on the audit
            -- ledger (all of schema audit) + the immutable ai_recommendation_audit, and reset the
            -- audit-schema future-table default to INSERT/SELECT. DB-level enforcement until the
            -- deferred audit-immutability trigger ships (least-privilege on the audit path).
            IF to_regnamespace('audit') IS NOT NULL THEN
                EXECUTE 'REVOKE UPDATE, DELETE ON ALL TABLES IN SCHEMA audit FROM dhanradar_app';
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA audit REVOKE UPDATE, DELETE ON TABLES FROM dhanradar_app';
            END IF;
            IF to_regclass('compliance.ai_recommendation_audit') IS NOT NULL THEN
                EXECUTE 'REVOKE UPDATE, DELETE ON TABLE compliance.ai_recommendation_audit FROM dhanradar_app';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # No-op: grants are additive + idempotent, and 0051's downgrade (DROP OWNED BY + DROP ROLE)
    # already removes every grant and the role itself when the chain unwinds. Reversing only this
    # migration's grants would wrongly strip the overlapping grants 0051 made.
    pass
