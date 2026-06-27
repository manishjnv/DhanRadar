"""De-superuser the runtime DB role (B80): ensure dhanradar_app + least-privilege grants.

BLOCKERS B80. The app currently connects as the Postgres SUPERUSER (POSTGRES_USER=dhanradar),
which silently skips the mf.portfolio_transactions append-only trigger (SET
session_replication_role='replica' / ALTER TABLE … DISABLE TRIGGER). So I12 is only a guardrail
today, not a hard invariant. This migration makes the least-privilege `dhanradar_app` role real
and fully granted so the runtime DSN can switch to it (config.py) — migrations keep using the
owner/superuser DSN.

TRAP (why this is a migration, not an 01_init.sql edit): init SQL runs ONLY on a fresh PGDATA
volume; prod already exists, so the scaffolded role + grants never auto-applied there. This
idempotent migration is the prod fix. DEPLOY ORDER: run this migration FIRST (role + grants),
THEN set DHANRADAR_APP_DB_PASSWORD in .env and `ALTER ROLE dhanradar_app PASSWORD …` out-of-band
(kept out of migration SQL so no secret reaches the migration logs), THEN `compose up` so the app
reconnects as dhanradar_app. The role is created WITHOUT a password here; on prod it already
exists (from init) — this only (re)asserts grants.

dhanradar_app is NOSUPERUSER NOBYPASSRLS (so it cannot disable the trigger and is subject to the
RLS that B81 adds) but CAN still `SET LOCAL mf.allow_ledger_purge` (a custom namespaced GUC,
settable by any role) so delete_portfolio's controlled purge keeps working.

Revision ID: 0051
Revises: 0050
Create Date: 2026-06-27
"""

from __future__ import annotations

from alembic import op

revision: str = "0051"
down_revision: str | None = "0050"
branch_labels = None
depends_on = None

# Every app schema (mirrors infra/postgres/init/01_init.sql). Granting on an empty schema is a
# no-op, so this is safe even where no tables exist yet.
_SCHEMAS = [
    "auth", "consent", "compliance", "admin", "mf", "etf", "stock", "news", "search",
    "portfolio", "mood", "scoring", "market_data", "ai", "notif", "gamif", "onboarding",
]
_SCHEMA_ARRAY = "ARRAY[" + ", ".join(f"'{s}'" for s in _SCHEMAS) + "]"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        DECLARE s text;
        BEGIN
            -- Idempotent role create (Postgres has no CREATE ROLE IF NOT EXISTS). NOSUPERUSER +
            -- NOBYPASSRLS are the security-critical flags; no password (set out-of-band on deploy).
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dhanradar_app') THEN
                CREATE ROLE dhanradar_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS LOGIN;
            END IF;

            EXECUTE format('GRANT CONNECT ON DATABASE %I TO dhanradar_app', current_database());
            -- Least-privilege (B80): dhanradar_app must NOT create schemas/objects. init's
            -- GRANT CREATE ON DATABASE is revoked here for the already-provisioned prod DB
            -- (no-op when the grant is absent — e.g. a fresh install).
            EXECUTE format('REVOKE CREATE ON DATABASE %I FROM dhanradar_app', current_database());

            FOREACH s IN ARRAY {_SCHEMA_ARRAY} LOOP
                EXECUTE format('GRANT USAGE ON SCHEMA %I TO dhanradar_app', s);
                -- Existing objects:
                EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO dhanradar_app', s);
                EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO dhanradar_app', s);
                EXECUTE format('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA %I TO dhanradar_app', s);
                -- Future objects created by the owner (migrations run as the owner):
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO dhanradar_app', s);
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT USAGE, SELECT ON SEQUENCES TO dhanradar_app', s);
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT EXECUTE ON FUNCTIONS TO dhanradar_app', s);
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    # DROP OWNED BY removes every grant + default-privilege entry made TO the role; then the role
    # can be dropped. Runs only in CI/dev (deploy never downgrades). Guarded so it is idempotent.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dhanradar_app') THEN
                DROP OWNED BY dhanradar_app;
                DROP ROLE dhanradar_app;
            END IF;
        END $$;
        """
    )
