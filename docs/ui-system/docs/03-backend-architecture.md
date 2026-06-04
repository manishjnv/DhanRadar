# DhanRadar — Backend Architecture

*Implementation-ready architecture for the DhanRadar platform. Stack: FastAPI · PostgreSQL · Redis · Elasticsearch · Celery.*

**Prepared by:** Principal Backend Architecture · **Date:** June 2026 · **Status:** v1 for build

---

## 0. Architecture at a glance

```
                              ┌─────────────┐
   Web / Mobile / PWA ──TLS──▶│   CDN/WAF   │
                              └──────┬──────┘
                                     ▼
                            ┌────────────────┐
                            │  API Gateway   │  (Kong / AWS ALB + nginx)
                            │  TLS, rate-limit│
                            └───────┬────────┘
                                    ▼
              ┌──────────────────────────────────────────┐
              │           FastAPI app tier (k8s)          │
              │  auth · instruments · portfolio · ai ·    │
              │  screener · billing · admin (ASGI/uvicorn)│
              └───┬───────┬────────┬────────┬─────────┬───┘
                  ▼       ▼        ▼        ▼         ▼
            ┌─────────┐┌──────┐┌────────┐┌──────────┐┌───────────┐
            │Postgres ││Redis ││Elastic ││ Celery   ││  Object   │
            │(primary ││cache ││ search ││ workers  ││  store    │
            │+replica)││+queue││ (instr ││ (beat +  ││  (S3)     │
            │         ││+lock ││  /news)││  workers)││  reports  │
            └─────────┘└──────┘└────────┘└────┬─────┘└───────────┘
                                              ▼
                          ┌──────────────────────────────────┐
                          │  External: market data feeds,     │
                          │  AA/broker APIs, Razorpay, LLM,    │
                          │  email (SES), SMS (OTP)            │
                          └──────────────────────────────────┘
```

**Design tenets**
1. **Stateless API tier** — all state in Postgres/Redis; horizontal scale behind the gateway.
2. **Read-heavy, async-everywhere** — FastAPI async handlers; heavy/slow work offloaded to Celery.
3. **Score is sacred** — recommendation pipeline is isolated, versioned, and never touched by billing or ads code paths.
4. **Defense in depth** — auth at gateway + app; row-level tenancy; audit everything sensitive.
5. **Cache aggressively, invalidate precisely** — instrument data and scores are cached with event-driven invalidation.

---

# PART A — HIGH-LEVEL DESIGN (HLD)

## A.1 Service decomposition (modular monolith → extractable services)

Start as a **modular monolith** (one FastAPI app, clear module boundaries) for velocity; each module is independently extractable to a microservice when load demands.

| Module | Responsibility | Hot path? | Extract priority |
|---|---|---|---|
| `auth` | Signup, login, OTP, JWT, sessions | Yes | Low (keep central) |
| `users` | Profile, preferences, brokers | Yes | Low |
| `instruments` | Stocks/funds/ETFs read API, search | Yes (read) | Medium |
| `scoring` | DhanRadar Score compute + serve | Yes (read) | **High** (isolate) |
| `portfolio` | Holdings, sync, analytics | Yes | Medium |
| `screener` | Filter/query over Elasticsearch | Yes | Medium |
| `watchlist_alerts` | Lists, alert rules, triggers | Medium | Medium |
| `ai` | Search, assistant, explainability (RAG) | Yes | **High** (GPU/cost) |
| `news` | Ingestion, tagging, feed | Medium | Low |
| `billing` | Subscriptions, Razorpay, invoices | Medium | Medium |
| `admin` | Ops console APIs | Low | Low |
| `notifications` | Push/email/in-app fan-out | Async | Low |
| `audit` | Append-only event log | Async | Low |

## A.2 Data-store responsibilities

| Store | Holds | Why |
|---|---|---|
| **PostgreSQL** | Users, subscriptions, holdings, watchlists, alerts, audit, score history, billing | ACID, relational integrity, source of truth |
| **Redis** | Session cache, rate-limit counters, hot instrument/score cache, Celery broker, distributed locks, pub/sub | Sub-ms reads, atomic counters |
| **Elasticsearch** | Instrument search index, screener queryable fields, news full-text | Fast filtering/full-text at scale |
| **S3 / object store** | Generated reports (PDF/CSV), exports, static factsheets | Cheap, durable blobs |

## A.3 Async/background topology (Celery)

```
Celery queues (priority-routed):
  realtime   → alert evaluation, OTP send, payment webhooks      (latency-sensitive)
  scoring    → daily score recompute, fair-value models          (CPU-heavy, batched)
  ingest     → market data, NAV, news ETL                        (scheduled)
  ai         → embeddings refresh, explanation pre-gen, evals     (GPU/cost-aware)
  reports    → PDF/CSV generation, portfolio health reports       (bursty)
  default    → emails, cache warmups, housekeeping
Celery Beat schedules:
  • 18:30 IST daily  → score recompute (post market close)
  • every 1 min      → alert evaluation sweep (delta-driven)
  • every 5 min      → NAV/price refresh, ES reindex deltas
  • hourly           → news ingest + tag
  • monthly 1st      → portfolio health reports
  • nightly          → audit archival, embedding refresh, eval suite
```

## A.4 Request lifecycle (read path: GET /stocks/{symbol})

```
1. Gateway: TLS terminate → WAF → rate-limit (Redis token bucket) → route
2. FastAPI middleware: request-id, JWT verify, tenant context, structured log start
3. Handler: check Redis cache `instr:{symbol}:v{n}` → hit? return (≈2ms)
4. Miss → Postgres read (instrument) + Redis `score:{symbol}` → assemble DTO
5. Gate premium fields by plan (authorization layer)
6. Write-through cache (TTL 60s for price-sensitive, 1h for fundamentals)
7. Emit usage event (async, fire-and-forget to audit/metering)
8. Response + ETag; middleware logs latency, status
```

---

# PART B — LOW-LEVEL DESIGN (LLD)

## B.1 FastAPI application layout

```
app/
├── main.py                 # ASGI app, middleware, router include
├── core/
│   ├── config.py           # pydantic-settings (env), feature flags
│   ├── security.py         # JWT, password hashing (argon2), OTP
│   ├── deps.py             # DI: get_db, get_redis, current_user, require_plan
│   ├── ratelimit.py        # token-bucket middleware (Redis)
│   ├── audit.py            # audit emitter
│   └── errors.py           # exception handlers → RFC7807 problem+json
├── db/
│   ├── base.py             # SQLAlchemy 2.0 async engine, session factory
│   ├── models/             # ORM models (one file per aggregate)
│   └── migrations/         # Alembic
├── modules/
│   ├── auth/               # router, schemas, service, repo
│   ├── instruments/
│   ├── scoring/
│   ├── portfolio/
│   ├── screener/
│   ├── ai/
│   ├── billing/
│   ├── watchlist_alerts/
│   ├── news/
│   └── admin/
├── workers/
│   ├── celery_app.py
│   └── tasks/              # one module per queue
└── tests/
```

**Layering per module:** `router` (HTTP, validation) → `service` (business logic, transactions) → `repository` (data access) → `models/schemas`. Services never touch HTTP; routers never touch the DB directly.

## B.2 Key cross-cutting components

**Dependency injection (`deps.py`)**
- `get_db()` — async SQLAlchemy session, per-request, auto-rollback on error.
- `current_user()` — verifies JWT, loads user + plan + roles into request context.
- `require_plan("pro")` / `require_role("admin")` — authorization guards (raise 402/403).
- `require_scope("ai:query")` — fine-grained for API keys.

**Caching strategy**
| Data | Key | TTL | Invalidation |
|---|---|---|---|
| Instrument fundamentals | `instr:{sym}:v{n}` | 1h | on ETL update event |
| Live price | `px:{sym}` | 5–15s | feed push |
| Score + factors | `score:{sym}` | until recompute | score-recompute event (pub/sub) |
| Screener result page | `scr:{hash}` | 5m | TTL only |
| Session | `sess:{jti}` | token TTL | on logout/revoke |
| Plan/entitlements | `ent:{user_id}` | 10m | on subscription change |

**Idempotency** — all POST that create/charge accept an `Idempotency-Key` header; stored in Redis (24h) → safe retries (critical for payments, alerts).

---

# PART C — DATABASE SCHEMA

## C.1 Core tables (PostgreSQL, abbreviated DDL)

```sql
-- ── Identity ──────────────────────────────────────────────
CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         CITEXT UNIQUE NOT NULL,
  phone         TEXT UNIQUE,
  password_hash TEXT,                       -- argon2id; null if social-only
  full_name     TEXT,
  status        TEXT NOT NULL DEFAULT 'active',  -- active|suspended|deleted
  email_verified BOOL NOT NULL DEFAULT false,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE auth_identities (              -- social / federated logins
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider    TEXT NOT NULL,                -- google|apple|password
  provider_uid TEXT NOT NULL,
  UNIQUE(provider, provider_uid)
);

CREATE TABLE roles (id SERIAL PRIMARY KEY, name TEXT UNIQUE);  -- user|admin|ml_ops|support
CREATE TABLE user_roles (
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  role_id INT  REFERENCES roles(id),
  PRIMARY KEY (user_id, role_id)
);

CREATE TABLE sessions (
  jti         UUID PRIMARY KEY,             -- refresh-token id
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  device      TEXT, ip INET, user_agent TEXT,
  expires_at  TIMESTAMPTZ NOT NULL,
  revoked_at  TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE otp_codes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  purpose TEXT NOT NULL,                    -- signup|login|reset
  code_hash TEXT NOT NULL, attempts INT DEFAULT 0,
  expires_at TIMESTAMPTZ NOT NULL, consumed_at TIMESTAMPTZ
);

-- ── Subscription / billing ────────────────────────────────
CREATE TABLE plans (
  id TEXT PRIMARY KEY,                      -- free|pro|premium
  name TEXT, price_inr INT, interval TEXT,  -- month|year
  features JSONB NOT NULL                   -- entitlement matrix
);
CREATE TABLE subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  plan_id TEXT NOT NULL REFERENCES plans(id),
  status TEXT NOT NULL,                     -- trialing|active|past_due|canceled
  current_period_end TIMESTAMPTZ,
  gateway_sub_id TEXT,                      -- Razorpay subscription id
  trial_end TIMESTAMPTZ, cancel_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE invoices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subscription_id UUID REFERENCES subscriptions(id),
  amount_inr INT, gst_inr INT, status TEXT,  -- paid|failed|refunded
  gateway_payment_id TEXT, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE usage_counters (              -- metering for Free limits
  user_id UUID, metric TEXT, period DATE,
  count INT DEFAULT 0, PRIMARY KEY(user_id, metric, period)
);

-- ── Instruments & scores ──────────────────────────────────
CREATE TABLE instruments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol TEXT UNIQUE NOT NULL, exchange TEXT,
  type TEXT NOT NULL,                       -- stock|fund|etf
  name TEXT, sector TEXT, meta JSONB,
  is_active BOOL DEFAULT true
);
CREATE TABLE instrument_prices (           -- time-series (consider Timescale)
  instrument_id UUID REFERENCES instruments(id),
  ts TIMESTAMPTZ NOT NULL, open NUMERIC, high NUMERIC,
  low NUMERIC, close NUMERIC, volume BIGINT,
  PRIMARY KEY (instrument_id, ts)
);
CREATE TABLE scores (
  instrument_id UUID REFERENCES instruments(id),
  as_of DATE NOT NULL,
  model_version TEXT NOT NULL,
  score INT, signal TEXT,                   -- strong_buy|buy|hold|caution|avoid
  factors JSONB,                            -- {valuation, growth, quality, momentum, risk}
  fair_value NUMERIC, confidence INT,
  PRIMARY KEY (instrument_id, as_of, model_version)
);
CREATE INDEX ON scores (instrument_id, as_of DESC);

-- ── Portfolio ─────────────────────────────────────────────
CREATE TABLE broker_links (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id), broker TEXT,
  consent_id TEXT, status TEXT, last_sync TIMESTAMPTZ
);
CREATE TABLE holdings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  instrument_id UUID REFERENCES instruments(id),
  qty NUMERIC, avg_price NUMERIC, source TEXT,  -- manual|broker
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, instrument_id, source)
);
CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID, instrument_id UUID, side TEXT, qty NUMERIC,
  price NUMERIC, executed_at TIMESTAMPTZ
);

-- ── Watchlist & alerts ────────────────────────────────────
CREATE TABLE watchlists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id), name TEXT, position INT
);
CREATE TABLE watchlist_items (
  watchlist_id UUID REFERENCES watchlists(id) ON DELETE CASCADE,
  instrument_id UUID REFERENCES instruments(id),
  PRIMARY KEY(watchlist_id, instrument_id)
);
CREATE TABLE alert_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  instrument_id UUID, type TEXT,            -- price|score|risk|earnings
  operator TEXT, threshold NUMERIC, active BOOL DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE alert_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id UUID REFERENCES alert_rules(id),
  triggered_at TIMESTAMPTZ DEFAULT now(), payload JSONB,
  delivered BOOL DEFAULT false
);

-- ── AI ────────────────────────────────────────────────────
CREATE TABLE ai_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE ai_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID REFERENCES ai_conversations(id),
  role TEXT, content TEXT, sources JSONB, confidence INT,
  model_version TEXT, feedback SMALLINT,    -- -1|0|+1
  tokens INT, created_at TIMESTAMPTZ DEFAULT now()
);

-- ── Audit (append-only) ───────────────────────────────────
CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor_id UUID, actor_role TEXT, action TEXT NOT NULL,
  resource_type TEXT, resource_id TEXT,
  ip INET, request_id UUID, meta JSONB,
  prev_hash TEXT, hash TEXT                 -- tamper-evident chain
);
```

## C.2 Indexing & partitioning notes
- `instrument_prices` and `audit_log` → **monthly range partitions**; archive cold partitions to S3.
- `scores` hot read → covering index `(instrument_id, as_of DESC) INCLUDE (score, signal, factors)`.
- `usage_counters` → composite PK doubles as the lookup; reset by partition drop per period.
- Consider **TimescaleDB** for `instrument_prices` if tick density grows.
- Read replicas serve instrument/score/screener reads; writes go to primary.

---

# PART D — ER DIAGRAM (logical)

```
users ──1:N── auth_identities
users ──M:N── roles (via user_roles)
users ──1:N── sessions
users ──1:N── otp_codes
users ──1:N── subscriptions ──N:1── plans
subscriptions ──1:N── invoices
users ──1:N── usage_counters
users ──1:N── broker_links
users ──1:N── holdings ──N:1── instruments
users ──1:N── transactions ──N:1── instruments
users ──1:N── watchlists ──1:N── watchlist_items ──N:1── instruments
users ──1:N── alert_rules ──1:N── alert_events
users ──1:N── ai_conversations ──1:N── ai_messages
instruments ──1:N── instrument_prices
instruments ──1:N── scores            (by as_of, model_version)
(all sensitive mutations) ──────────▶ audit_log   [append-only, hash-chained]
```

**Cardinality rules of note:** a user has exactly one *active* subscription (enforced by partial unique index `WHERE status IN ('trialing','active')`); a holding is unique per `(user, instrument, source)`; an alert rule belongs to one user and one instrument.

---

# PART E — API CATALOG

> Conventions: REST, JSON, cursor pagination (`?cursor=&limit=`), RFC7807 errors, `Authorization: Bearer <jwt>`, versioned under `/v1`. Premium fields gated server-side.

### Auth
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/v1/auth/signup` | public | rate-limited; sends OTP |
| POST | `/v1/auth/login` | public | password or social |
| POST | `/v1/auth/otp/verify` | public | consumes OTP → tokens |
| POST | `/v1/auth/token/refresh` | refresh | rotates refresh token |
| POST | `/v1/auth/logout` | user | revokes session |
| POST | `/v1/auth/password/forgot` · `/reset` | public | reset flow |

### Instruments & scores
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/v1/instruments/search?q=` | public | ES-backed autosuggest |
| GET | `/v1/stocks/{symbol}` | public* | *score ungated; fair-value gated |
| GET | `/v1/funds/{symbol}` · `/etfs/{symbol}` | public* | |
| GET | `/v1/instruments/{symbol}/score` | public | + factors |
| GET | `/v1/instruments/{symbol}/score/history` | user | track record |
| GET | `/v1/instruments/{symbol}/fair-value` | **pro** | multi-model |
| GET | `/v1/instruments/{symbol}/peers` | user | |

### Screener
| GET | `/v1/screener/stocks` | user | filters → ES; save gated |
| POST | `/v1/screener/save` | **pro** | saved screen |
| GET | `/v1/screener/saved` | user | |

### Portfolio
| GET | `/v1/portfolio` | user | overview + score |
| POST | `/v1/portfolio/holdings` | user | manual add (idempotent) |
| POST | `/v1/portfolio/sync` | user | broker/AA consent flow |
| GET | `/v1/portfolio/analytics` | **pro** | risk, attribution |
| GET | `/v1/portfolio/report` | **pro** | async → S3 link |

### Watchlist & alerts
| GET/POST | `/v1/watchlists` · `/{id}/items` | user | |
| GET/POST | `/v1/alerts` | user | create rule (idempotent) |
| GET | `/v1/alerts/events` | user | triggered |

### AI
| POST | `/v1/ai/search` | user | grounded answer (quota on Free) |
| POST | `/v1/ai/assistant` | user | chat; streaming (SSE) |
| GET | `/v1/ai/explain/{symbol}` | user | explainability |
| POST | `/v1/ai/messages/{id}/feedback` | user | thumbs → AI Ops |

### Billing
| GET | `/v1/billing/plans` | public | |
| POST | `/v1/billing/checkout` | user | Razorpay order (idempotent) |
| POST | `/v1/billing/webhook` | gateway | signed; idempotent |
| GET | `/v1/billing/subscription` | user | |
| POST | `/v1/billing/cancel` | user | |

### Admin (role-gated) & AI Ops
| GET | `/v1/admin/users` · `/{id}` | admin | audited |
| POST | `/v1/admin/users/{id}/suspend` · `/refund` | admin | audited, idempotent |
| GET | `/v1/admin/metrics` | admin | |
| GET/POST | `/v1/admin/content/*` | admin | CMS |
| GET | `/v1/aiops/models` · POST `/promote` | ml_ops | canary/rollback |
| GET | `/v1/aiops/evals` · `/safety` | ml_ops | |

---

# PART F — AUTHENTICATION

**Token model — short JWT access + rotating refresh**
- **Access token (JWT)**: 15-min TTL, signed **RS256** (rotate keys via JWKS). Claims: `sub`, `roles`, `plan`, `jti`, `exp`, `scopes` (for API keys).
- **Refresh token**: opaque, stored in `sessions` (`jti`), 30-day TTL, **rotated on every use** (detect reuse → revoke session family = theft signal).
- **OTP**: 6-digit, hashed (argon2), 10-min TTL, max 5 attempts, Redis-throttled per phone/IP.
- **Passwords**: argon2id (memory-hard), never logged; breach-check against k-anonymized HIBP on set.
- **Social**: Google/Apple OIDC → `auth_identities`; email auto-verified from provider.
- **Delivery**: access token in memory (web) / secure storage (mobile); refresh in **HttpOnly + Secure + SameSite=Strict** cookie for web; rotation endpoint sets new cookie.

**Verification middleware** validates signature (JWKS cache), `exp`, and that the session isn't revoked (Redis `sess:{jti}` lookup, fail-closed).

---

# PART G — AUTHORIZATION

**Three layers:**
1. **RBAC** — `user`, `admin`, `ml_ops`, `support`. Route guards via `require_role`. Admin/AI-Ops APIs live under separate routers with mandatory role + audit.
2. **Plan-based entitlements (ABAC-lite)** — `plans.features` JSONB defines an entitlement matrix; `require_plan("pro")` and field-level gating (e.g., `fair_value` stripped from DTO for Free). Entitlements cached `ent:{user_id}` (10m).
3. **Row-level tenancy** — every user-owned query is scoped by `user_id` from the token; enforced in the repository layer (and optionally Postgres **RLS** policies as a backstop). A user can never read another user's holdings/alerts/AI history.

**API keys (Premium)** — scoped tokens (`ai:query`, `data:read`), rate-limited per key, revocable, shown once.

**Decision flow:** `authenticated? → role allows route? → plan entitles feature? → owns resource? → scope (if API key)? → allow`.

---

# PART H — SUBSCRIPTION SYSTEM

**State machine:** `trialing → active → past_due → canceled` (+ `active → canceled` on user cancel at period end).

```
Checkout:  client → POST /billing/checkout (idempotent)
           → create Razorpay order → return order_id
           → client pays → Razorpay webhook (signed)
Webhook:   verify HMAC signature → idempotency check (event_id)
           → upsert subscription + invoice → set entitlements
           → invalidate ent:{user} cache → audit → email receipt
Renewal:   Razorpay subscription auto-charge → webhook updates period_end
Dunning:   payment.failed → status=past_due → Celery retry schedule
           (day 1/3/5 email) → grace 7d → downgrade to free
Trial:     14-day, no card; Celery beat T-1 reminder; expiry → free
Cancel:    set cancel_at=period_end; retain access until then
```

**Entitlement enforcement** is read at request time from cached `plans.features`; **metering** (`usage_counters`) enforces Free limits (e.g., 20 lookups/mo, 5 AI queries/mo) atomically via Redis `INCR` with daily/monthly period keys, reconciled to Postgres.

**Money invariants:** all amounts in integer paise; GST computed server-side; invoices immutable; refunds create a new negative invoice + audit entry. **No billing code path can read or write the `scores` table** — enforced by module boundary + code-owner review.

---

# PART I — RECOMMENDATION ENGINE

**Isolated, versioned pipeline.** Lives in `scoring` module; the API tier only *reads* materialized scores.

```
Daily (18:30 IST, Celery 'scoring' queue):
  1. Ingest: prices, fundamentals, fund NAVs → staging tables
  2. Factor compute (per instrument): valuation, growth, quality,
     momentum, risk  → normalize within sector/peer set (z-score → 0–100)
  3. Composite: weighted blend (weights = model_version config)
     → score 0–100 → signal band (≥85 SB / ≥70 B / ≥55 H / ≥40 C / <40 A)
  4. Fair value: DCF + relative + EPV (weighted) → target + confidence
  5. Write scores(as_of, model_version) — immutable row per day/version
  6. Diff vs prior → emit score-change events (→ alerts, cache invalidation)
  7. Pre-generate explanations (AI queue) for top-N + held instruments
```

**Explainability & confidence** are produced alongside the score (factor contributions stored in `scores.factors`; confidence reflects data freshness + factor agreement). **Versioning:** `model_version` lets AI Ops run a **canary** (e.g., v2.5 to 20% of read traffic via feature flag) and **roll back** instantly by repointing the active version — no data migration. Backtests run on historical `scores` partitions.

**Serving:** `GET /score` reads Redis `score:{sym}` (warmed post-recompute) → Postgres fallback. Recompute publishes invalidation on Redis pub/sub so all app nodes drop stale cache.

**Integrity guarantee:** the engine has **no dependency** on billing, ads, or user-tier — verified by import-linting (the `scoring` package may not import `billing`).

---

# PART J — ADMIN SYSTEM

- **Separate routers** (`/v1/admin/*`, `/v1/aiops/*`), separate frontend shell, **mandatory role + audit** on every endpoint.
- **Capabilities:** user management (view/suspend/refund/**impersonate**), billing ops, content CMS (blog/learn/glossary → triggers ES reindex + cache purge), score-model config (change requests routed to AI Ops with approval), data-source monitor (feed health), notification console, support tickets, feature flags, analytics.
- **Impersonation** is time-boxed, consent-flagged, and writes a prominent `audit_log` entry (`action=impersonate.start/stop`); impersonated sessions are visually marked and cannot change payment methods.
- **AI Ops** (`ml_ops` role): model versioning/backtest, prompt & RAG management, eval console, safety/hallucination monitor, feedback review, cost monitor.
- **Least privilege:** admin actions require re-auth (step-up) for destructive ops (refund, delete, model promote).

---

# PART K — AUDIT LOGGING

- **Append-only** `audit_log`, **hash-chained** (`hash = H(prev_hash || row)`) for tamper-evidence; periodic anchor of the latest hash to write-once storage.
- **What's logged:** auth events, authz denials, every admin/AI-ops action, billing mutations, data exports, consent grants/revokes, AI safety flags, PII access.
- **What's never logged:** raw passwords, OTP codes, full card numbers, tokens (only `jti`).
- **Emission:** non-blocking — handlers push to a Redis stream; a Celery consumer persists to Postgres and ships to the SIEM. Failure to persist audit for a *sensitive* action fails the request closed.
- **Retention:** 400 days hot, then S3 (WORM) for the regulatory window; access to audit is itself audited.
- **Correlation:** every log carries `request_id` (propagated from gateway) for end-to-end tracing (OpenTelemetry).

---

# PART L — RATE LIMITING

**Multi-tier, Redis token-bucket** (atomic Lua script for check-and-decrement):

| Scope | Limit (example) | Key |
|---|---|---|
| Per IP (unauth) | 60 req/min | `rl:ip:{ip}` |
| Per user (global) | 600 req/min | `rl:u:{uid}` |
| AI endpoints (Free) | 5/day, 1/10s burst | `rl:ai:{uid}:{day}` |
| AI endpoints (Pro) | 300/day | |
| Auth/OTP | 5/15min per phone+IP | `rl:otp:{phone}` |
| Search | 30/min | `rl:srch:{uid}` |
| API keys (Premium) | per-key tier | `rl:key:{kid}` |
| Webhooks | per-source allowlist | gateway |

- **Headers:** `X-RateLimit-Limit/Remaining/Reset`; `429` with `Retry-After`.
- **Layered:** coarse limits at the gateway (volumetric/DDoS), fine business limits in the app.
- **Cost-aware AI limiting:** AI requests also debit a token/cost budget (`aiops` monitors) — protects margins and the LLM bill.

---

# PART M — SECURITY CONTROLS

**Transport & edge** — TLS 1.3 everywhere, HSTS; WAF (OWASP CRS) + bot/DDoS protection at CDN; strict CORS allowlist; security headers (CSP, X-Content-Type-Options, Referrer-Policy).

**Application** — Pydantic validation on all input; parameterized queries (no string SQL); output DTOs prevent over-exposure (premium/PII stripping); CSRF protection for cookie auth; SSRF guard on outbound (broker/feed) calls via allowlist; idempotency on mutating endpoints; secrets via vault/KMS, never in code or logs.

**Data** — encryption at rest (Postgres TDE / disk + column-level for tokens/PII); argon2id passwords; PII minimization; **AA-framework** for broker data (consent-based, revocable, never store broker credentials); GDPR/DPDP: data export + right-to-erasure (soft-delete + scheduled purge, audit-preserved).

**AI-specific** — RAG grounded only on internal data (no open web); prompt-injection filtering; output safety classifier (advice-boundary, unsafe content) before render; the model **cannot** access billing or write any store; per-user data used for insights only with consent toggle.

**Operational** — least-privilege IAM; step-up auth for admin destructive ops; dependency scanning (SCA) + SAST/DAST in CI; secrets rotation; immutable infra; blue-green deploys; **the `scores` table is read-only to all services except the scoring worker** (DB-level grant) — the structural guarantee behind "no monetization stream touches a Score."

**Incident readiness** — structured logs + OpenTelemetry traces + metrics (Prometheus/Grafana); alerting on authz-denial spikes, payment-failure spikes, audit-write failures, and AI safety flags; runbooks; tested backups (PITR on Postgres) and restore drills.

---

## Appendix — non-functional targets

| Concern | Target |
|---|---|
| Read p99 (cached) | < 80 ms |
| Read p99 (DB) | < 250 ms |
| Score recompute (full universe) | < 30 min nightly |
| Alert latency (trigger → notify) | < 60 s |
| Availability | 99.9% API |
| RPO / RTO | 5 min / 30 min |
| Horizontal scale | stateless API; add pods on CPU/RPS |

---

## Addendum — Market Data subsystem (see /market-data)
The ingestion + market-data layer is specified in detail under `/market-data`:
- `market-data-architecture.md` — NSE/BSE/AMFI feeds, DataProvider abstraction, corporate actions, fundamentals/technical, historical.
- `data-quality-framework.md` · `market-data-sla.md` · `data-reconciliation-engine.md` · `historical-storage-strategy.md` · `holiday-and-recovery.md`.

Backend integration points: the `instruments`/`scoring` modules consume the DataProvider interface; `instrument_prices` is a TimescaleDB hypertable (raw + adj_close); corporate-action adjustments write through the reconciliation engine and audit every change; freshness SLA breaches lower downstream AI confidence and surface in the Admin Data Source Monitor. Scores recompute only on trading days (holiday-aware), reading authoritative EOD.

## Addendum — Event-Driven Architecture (see /event-architecture)
The modular monolith is wired with an internal event bus (Redis Streams, Kafka-ready abstraction). Services publish versioned domain events (MarketDataUpdated, RecommendationGenerated, NewsProcessed, PortfolioUpdated, AlertTriggered, SubscriptionActivated, NotificationSent, plus audit/consent events) consumed by independently-scaled workers with at-least-once delivery, idempotent handlers (dedupe by event_id), exponential-backoff retry, per-topic DLQ + replay, and audit events feeding the hash-chained audit_log + recommendation_audit. See /event-architecture for catalog, contracts, and flow diagrams.

*Implementation-ready. Suggested next artifacts: OpenAPI spec generation from the FastAPI routers, Alembic migration set for Part C, and a Terraform/Helm baseline for the k8s + managed Postgres/Redis/ES topology.*
