"""B81 — schema-wide Row-Level Security (I5): FORCE RLS owner-scoping on the mf.* personal tables
+ the dhanradar_admin BYPASSRLS role for legitimate cross-user readers.

Owner-scoping becomes PHYSICAL: each personal row is visible/writable only when the request's
`app.user_id` GUC equals the row's `user_id` (set in deps.current_user_or_anonymous / the CAS task).
FORCE so even the table owner is bound; dhanradar_app is NOSUPERUSER NOBYPASSRLS (B80) so it is too.
Cross-user readers (admin console, Celery aggregate jobs, webhooks) connect as dhanradar_admin
(BYPASSRLS).

STAGED rollout (founder 2026-06-27): this migration ENFORCES RLS on the 8 mf.* core tables; the
remaining classified-PERSONAL tables (signal/notify/auth/compliance) flip on in a PR-2 migration once
their readers are wired. The DDL is db_security.rls_statements (single source — conftest + the RLS
tests apply the SAME), so the policy shape can't drift; the table list is inlined (frozen + so the
B83 drift text-assert can verify it == db_security.RLS_ENFORCED).

Revision ID: 0053
Revises: 0052
Create Date: 2026-06-27
"""

from __future__ import annotations

from alembic import op
from dhanradar.db_schemas import APP_SCHEMAS
from dhanradar.db_security import rls_downgrade_statements, rls_statements

revision: str = "0053"
down_revision: str | None = "0052"
branch_labels = None
depends_on = None

# Inlined as literals (frozen + greppable by the B83 drift text-assert). MUST equal
# db_security.RLS_ENFORCED — the drift test asserts it.
_RLS_TABLES = [
    "mf.mf_portfolios",
    "mf.mf_user_holdings",
    "mf.portfolio_transactions",
    "mf.mf_portfolio_snapshots",
    "mf.mf_cas_jobs",
    "mf.mf_user_fund_score_history",
    "mf.user_fund_scores",
    "mf.mf_sip_transactions",
]
_SCHEMA_ARRAY = "ARRAY[" + ", ".join(f"'{s}'" for s in APP_SCHEMAS) + "]"


def upgrade() -> None:
    # 1. dhanradar_admin — BYPASSRLS role for cross-user readers. Same DML grants as dhanradar_app
    #    (so it can read every personal table), but BYPASSRLS so RLS does not scope it. NOT superuser
    #    (cannot disable the append-only trigger). Audit tables stay immutable to it too.
    op.execute(
        f"""
        DO $$
        DECLARE s text;
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dhanradar_admin') THEN
                CREATE ROLE dhanradar_admin NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS LOGIN;
            END IF;
            EXECUTE format('GRANT CONNECT ON DATABASE %I TO dhanradar_admin', current_database());
            EXECUTE format('REVOKE CREATE ON DATABASE %I FROM dhanradar_admin', current_database());
            FOREACH s IN ARRAY {_SCHEMA_ARRAY} LOOP
                IF to_regnamespace(s) IS NULL THEN CONTINUE; END IF;
                EXECUTE format('GRANT USAGE ON SCHEMA %I TO dhanradar_admin', s);
                EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO dhanradar_admin', s);
                EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO dhanradar_admin', s);
                EXECUTE format('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA %I TO dhanradar_admin', s);
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO dhanradar_admin', s);
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT USAGE, SELECT ON SEQUENCES TO dhanradar_admin', s);
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT EXECUTE ON FUNCTIONS TO dhanradar_admin', s);
            END LOOP;
            -- Audit ledger stays append-only for the admin role too (it reads audit, never mutates).
            IF to_regnamespace('audit') IS NOT NULL THEN
                EXECUTE 'REVOKE UPDATE, DELETE ON ALL TABLES IN SCHEMA audit FROM dhanradar_admin';
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA audit REVOKE UPDATE, DELETE ON TABLES FROM dhanradar_admin';
            END IF;
            IF to_regclass('compliance.ai_recommendation_audit') IS NOT NULL THEN
                EXECUTE 'REVOKE UPDATE, DELETE ON TABLE compliance.ai_recommendation_audit FROM dhanradar_admin';
            END IF;
        END $$;
        """
    )

    # 2. FORCE RLS + owner policy on each enforced personal table (DDL from db_security, to_regclass-guarded).
    for table in _RLS_TABLES:
        body = ";\n                ".join(rls_statements(table)) + ";"
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('{table}') IS NOT NULL THEN
                {body}
                END IF;
            END $$;
            """
        )


def downgrade() -> None:
    for table in _RLS_TABLES:
        body = ";\n                ".join(rls_downgrade_statements(table)) + ";"
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('{table}') IS NOT NULL THEN
                {body}
                END IF;
            END $$;
            """
        )
    # Drop the admin role (CI-only; deploy never downgrades). DROP OWNED BY removes its grants first.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dhanradar_admin') THEN
                DROP OWNED BY dhanradar_admin;
                DROP ROLE dhanradar_admin;
            END IF;
        END $$;
        """
    )
