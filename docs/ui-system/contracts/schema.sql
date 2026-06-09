-- =====================================================================
-- ⛔ DO NOT ADOPT — HARVEST-NOT-ADOPT REFERENCE ONLY (B41)
-- This schema is from the docs/ui-system kit and CONFLICTS with the binding
-- architecture. It is NOT a source of truth; do NOT run it or migrate from it.
-- Violations: flat `public` schema (non-neg #7 = schema-per-concern, no flat
-- public), an auth/users model that diverges from the live backend, and a
-- stack that conflicts with the locks (#8). The real schema is the live
-- backend/alembic migrations. Authority: docs/DhanRadar_Architecture_Final.md;
-- apply only per docs/project-state/MIGRATION_STRATEGY_FINAL.md.
-- =====================================================================
-- DhanRadar — PostgreSQL schema (runnable). Requires: pgcrypto, citext, (optional) timescaledb, vector.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email CITEXT UNIQUE NOT NULL,
  phone TEXT UNIQUE,
  password_hash TEXT,
  full_name TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','deleted')),
  email_verified BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE auth_identities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL, provider_uid TEXT NOT NULL,
  UNIQUE(provider, provider_uid)
);
CREATE TABLE roles (id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);
INSERT INTO roles(name) VALUES ('user'),('admin'),('ml_ops'),('support');
CREATE TABLE user_roles (user_id UUID REFERENCES users(id) ON DELETE CASCADE, role_id INT REFERENCES roles(id), PRIMARY KEY(user_id, role_id));
CREATE TABLE sessions (
  jti UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  device TEXT, ip INET, user_agent TEXT, expires_at TIMESTAMPTZ NOT NULL, revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE otp_codes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  purpose TEXT NOT NULL, code_hash TEXT NOT NULL, attempts INT DEFAULT 0,
  expires_at TIMESTAMPTZ NOT NULL, consumed_at TIMESTAMPTZ
);
CREATE TABLE plans (id TEXT PRIMARY KEY, name TEXT, price_inr INT, interval TEXT, features JSONB NOT NULL);
INSERT INTO plans(id,name,price_inr,interval,features) VALUES
 ('free','Free',0,'month','{"lookups":20,"ai_queries":5,"watchlists":1,"fair_value":false,"screener_save":false}'),
 ('pro','Pro',399,'month','{"lookups":-1,"ai_queries":-1,"watchlists":10,"fair_value":true,"screener_save":true,"analytics":true}'),
 ('premium','Premium',899,'month','{"everything_pro":true,"tax":true,"api":true,"curated":true}');
CREATE TABLE subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id),
  plan_id TEXT NOT NULL REFERENCES plans(id),
  status TEXT NOT NULL CHECK (status IN ('trialing','active','past_due','canceled')),
  current_period_end TIMESTAMPTZ, gateway_sub_id TEXT, trial_end TIMESTAMPTZ, cancel_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX one_active_sub ON subscriptions(user_id) WHERE status IN ('trialing','active');
CREATE TABLE invoices (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), subscription_id UUID REFERENCES subscriptions(id), amount_inr INT, gst_inr INT, status TEXT, gateway_payment_id TEXT, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE usage_counters (user_id UUID, metric TEXT, period DATE, count INT DEFAULT 0, PRIMARY KEY(user_id, metric, period));
CREATE TABLE instruments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), symbol TEXT UNIQUE NOT NULL, exchange TEXT,
  type TEXT NOT NULL CHECK (type IN ('stock','fund','etf')), name TEXT, sector TEXT, meta JSONB, is_active BOOLEAN DEFAULT true
);
CREATE TABLE instrument_prices (instrument_id UUID REFERENCES instruments(id), ts TIMESTAMPTZ NOT NULL, open NUMERIC, high NUMERIC, low NUMERIC, close NUMERIC, volume BIGINT, PRIMARY KEY(instrument_id, ts));
CREATE TABLE scores (
  instrument_id UUID REFERENCES instruments(id), as_of DATE NOT NULL, model_version TEXT NOT NULL,
  score INT, signal TEXT, factors JSONB, fair_value NUMERIC, confidence INT,
  PRIMARY KEY(instrument_id, as_of, model_version)
);
CREATE INDEX scores_latest ON scores(instrument_id, as_of DESC);
CREATE TABLE broker_links (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID REFERENCES users(id), broker TEXT, consent_id TEXT, status TEXT, last_sync TIMESTAMPTZ);
CREATE TABLE holdings (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(id), instrument_id UUID REFERENCES instruments(id), qty NUMERIC, avg_price NUMERIC, source TEXT, updated_at TIMESTAMPTZ DEFAULT now(), UNIQUE(user_id, instrument_id, source));
CREATE TABLE transactions (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID, instrument_id UUID, side TEXT, qty NUMERIC, price NUMERIC, executed_at TIMESTAMPTZ);
CREATE TABLE watchlists (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID REFERENCES users(id), name TEXT, position INT);
CREATE TABLE watchlist_items (watchlist_id UUID REFERENCES watchlists(id) ON DELETE CASCADE, instrument_id UUID REFERENCES instruments(id), PRIMARY KEY(watchlist_id, instrument_id));
CREATE TABLE alert_rules (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID REFERENCES users(id), instrument_id UUID, type TEXT, operator TEXT, threshold NUMERIC, active BOOLEAN DEFAULT true, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE alert_events (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), rule_id UUID REFERENCES alert_rules(id), triggered_at TIMESTAMPTZ DEFAULT now(), payload JSONB, delivered BOOLEAN DEFAULT false);
CREATE TABLE ai_conversations (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE ai_messages (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), conversation_id UUID REFERENCES ai_conversations(id), role TEXT, content TEXT, sources JSONB, confidence INT, model_version TEXT, feedback SMALLINT, tokens INT, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE corporate_actions (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), instrument_id UUID REFERENCES instruments(id), type TEXT, ex_date DATE, record_date DATE, ratio NUMERIC, amount NUMERIC, meta JSONB);
CREATE TABLE ingest_runs (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), source TEXT, started TIMESTAMPTZ DEFAULT now(), finished TIMESTAMPTZ, status TEXT, counts JSONB);
CREATE TABLE audit_log (id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL DEFAULT now(), actor_id UUID, actor_role TEXT, action TEXT NOT NULL, resource_type TEXT, resource_id TEXT, ip INET, request_id UUID, meta JSONB, prev_hash TEXT, hash TEXT);
-- Integrity guarantee: grant scoring_worker write on scores; all other app roles get SELECT only.
-- REVOKE INSERT,UPDATE,DELETE ON scores FROM app_role; GRANT INSERT ON scores TO scoring_worker;
