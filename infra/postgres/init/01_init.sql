-- =============================================================================
-- DhanRadar — Postgres initialisation script
-- Runs once on first container start via /docker-entrypoint-initdb.d
--
-- IMPORTANT: pg_cron and pg_partman require the following server settings to be
-- active BEFORE this script runs — they are passed via the compose command:
--   shared_preload_libraries = 'timescaledb,pg_cron'
--   cron.database_name       = 'dhanradar'
-- timescaledb-ha already preloads timescaledb; pg_cron must be added explicitly.
-- Re-verify extension availability on KVM4 per Implementation Plan Phase 1
-- step 2(c) before first production deploy:
--   SELECT name, default_version FROM pg_available_extensions
--   WHERE name IN ('pg_cron','pg_partman','vector','pg_trgm');
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_partman;
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- ---------------------------------------------------------------------------
-- Application role (non-superuser)
-- The database itself is created by the image via POSTGRES_DB=dhanradar.
--
-- PHASE-1 NOTE: in Phase 1 the app connects as the image superuser
-- (POSTGRES_USER=dhanradar). This least-privilege `dhanradar_app` role exists
-- so the schema/grant model is in place, but is not yet used. Phase 2 MUST
-- (a) switch the app DSN to dhanradar_app and (b) source its password from an
-- env var (DHANRADAR_APP_DB_PASSWORD) instead of the literal placeholder below.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dhanradar_app') THEN
        CREATE ROLE dhanradar_app WITH LOGIN PASSWORD 'changeme_in_env';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE dhanradar TO dhanradar_app;
GRANT CREATE ON DATABASE dhanradar TO dhanradar_app;

-- ---------------------------------------------------------------------------
-- Schemas per domain concern
-- (Tables are created by Alembic migrations in later phases)
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS consent;
CREATE SCHEMA IF NOT EXISTS compliance;
CREATE SCHEMA IF NOT EXISTS admin;
CREATE SCHEMA IF NOT EXISTS mf;
CREATE SCHEMA IF NOT EXISTS etf;
CREATE SCHEMA IF NOT EXISTS stock;
CREATE SCHEMA IF NOT EXISTS news;
CREATE SCHEMA IF NOT EXISTS search;
CREATE SCHEMA IF NOT EXISTS portfolio;
CREATE SCHEMA IF NOT EXISTS mood;
CREATE SCHEMA IF NOT EXISTS scoring;
CREATE SCHEMA IF NOT EXISTS market_data;
CREATE SCHEMA IF NOT EXISTS ai;
CREATE SCHEMA IF NOT EXISTS notif;
CREATE SCHEMA IF NOT EXISTS gamif;
CREATE SCHEMA IF NOT EXISTS onboarding;

-- Grant usage on all schemas to the app role
GRANT USAGE ON SCHEMA
    auth, consent, compliance, admin,
    mf, etf, stock, news, search, portfolio,
    mood, scoring, market_data, ai, notif, gamif, onboarding
TO dhanradar_app;

-- Grant default privileges for future tables/sequences
ALTER DEFAULT PRIVILEGES IN SCHEMA
    auth, consent, compliance, admin,
    mf, etf, stock, news, search, portfolio,
    mood, scoring, market_data, ai, notif, gamif, onboarding
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO dhanradar_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA
    auth, consent, compliance, admin,
    mf, etf, stock, news, search, portfolio,
    mood, scoring, market_data, ai, notif, gamif, onboarding
GRANT USAGE, SELECT ON SEQUENCES TO dhanradar_app;
