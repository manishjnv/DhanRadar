# Canonical OpenAPI Alignment

**Stage 1 — Contract Reconciliation. Documentation only; no runtime code changed.**
**Date:** 2026-06-05
**Authority order (binding):** `DhanRadar_Architecture_Final.md` → `DhanRadar_Implementation_Plan.md` → existing implementation → `docs/features` → `docs/ui-system` → UI mockups.

This document defines the **canonical API contract** the repo will converge on. It supersedes the UI package's `contracts/openapi.yaml` wherever they differ. It does not change code; it is the specification a future Stage-2 task will implement and from which a corrected `openapi.yaml` will be regenerated.

---

## 1. Canonical cross-cutting decisions

| Concern | Canonical decision | Loses to it |
|---|---|---|
| Base path | **`/api/v1`** on every endpoint (no exceptions) | UI package `/v1`; architecture's own stray `/api/news`, `/api/search`, unversioned `/market/*` |
| Auth transport | **RS256 JWT in HttpOnly cookies** `__Host-access` (15 m) + `__Host-refresh` (7 d); silent refresh via rotation + reuse detection | UI package `bearerAuth` Authorization header + body refresh |
| Auth status codes | **401** not authenticated · **402** `{upgrade_url}` tier-gate · **403** consent/role/ownership denied | — (existing + architecture already agree) |
| Error body | **RFC7807 Problem+JSON** with stable `type` taxonomy + `request_id` (see §4) | existing FastAPI `{"detail": "..."}` |
| Idempotency | **`Idempotency-Key` header required** on all mutating + payment endpoints; consumers dedupe by key | — (both agree) |
| Tier dependency | `Depends(require_tier("free"\|"pro"\|"pro_plus"))` (class, not closure) + `Depends(current_user_or_anonymous)` | — |
| Signal vocabulary | **Non-advisory only** — `in_form` / `on_track` / `off_track` / `out_of_form` (see §5) | UI package `strong_buy/buy/hold/caution/avoid` (**rejected, non-negotiable #2**) |
| Score numerics | Numeric score + factor **weights never in the DOM**; public payload = label + confidence **band**; numeric score/factors/fair-value behind tier gate | UI package returning raw `score`, `factors`, `fair_value` to all clients |
| Confidence | **Band only** (`high`/`medium`/`low`) until calibration reliability-curve is within ±10%; numeric % suppressed | UI package exposing integer `confidence` |

**Why `/api/v1`:** the existing FastAPI app mounts every router under `/api/v1`, and the cloudflared ingress routes `^/api/.*` → FastAPI. A bare `/v1` path would not even reach the backend through the tunnel. The architecture doc is internally inconsistent (mixes `/api/v1`, `/api/news`, `/market/*`); we standardise on the existing code's uniform `/api/v1`.

---

## 2. Canonical authentication model

Existing implementation is the source of truth (non-negotiable #4). Confirmed against architecture Global §2.

- **Tokens:** access JWT 15 min, refresh JWT 7 days, both RS256, both in `__Host-`-prefixed HttpOnly+Secure cookies. JS never reads token values.
- **Endpoints (canonical, all `/api/v1/auth/*`):**
  - `POST /api/v1/auth/signup` — email + password → 201, sets cookies. *(D2: password-immediate kept; no OTP-first.)*
  - `POST /api/v1/auth/login` — → 200, sets cookies; generic `401 invalid_credentials` on any failure (no enumeration).
  - `POST /api/v1/auth/logout` — clears cookies, revokes refresh jti in Redis, revokes still-valid access jti.
  - `POST /api/v1/auth/refresh` — rotation + reuse detection; reads `__Host-refresh` cookie (no request body).
  - `GET  /api/v1/auth/me` — current profile; 401 if anonymous.
  - `POST /api/v1/auth/totp/setup` · `POST /api/v1/auth/totp/verify` — optional 2FA.
- **Rejected from UI package:** `bearerAuth`, `Authorization: Bearer`, `POST /auth/token/refresh` with `TokenRefreshRequest` body, `POST /auth/otp/verify`.
- **OTP preserved-not-activated (D2):** keep the UI package's `otp_codes` schema + signup-OTP docs as a future additive phase; do not wire it.
- **Tier cache:** `auth:tier:{user_id}` 15 m in Redis; miss → active Razorpay subscription in Postgres. Founder-lifetime stored on `users` directly.

Frontend api-client implication (documented, not implemented): requests use `credentials: 'include'`; **no** Authorization header; refresh is a silent `POST /api/v1/auth/refresh` on 401.

---

## 3. Canonical endpoint inventory

Reconciles three sources. Status legend: **LIVE** (implemented now) · **SPEC** (architecture-defined, to build in phase) · **ADAPT** (UI-package endpoint kept but renamed/repathed to canonical) · **REJECT** (UI-package endpoint dropped).

### 3.1 Auth & account

| Canonical path | Method | Status | Notes |
|---|---|---|---|
| `/api/v1/auth/signup` | POST | LIVE | UI package's 202+OTP REJECTED; password-immediate kept |
| `/api/v1/auth/login` | POST | LIVE | |
| `/api/v1/auth/logout` | POST | LIVE | |
| `/api/v1/auth/refresh` | POST | LIVE | cookie-based; UI package `/auth/token/refresh` ADAPT→this |
| `/api/v1/auth/me` | GET | LIVE | UI package had no equivalent |
| `/api/v1/auth/totp/setup` · `/verify` | POST | LIVE | |

### 3.2 Billing & subscription

| Canonical path | Method | Status | Notes |
|---|---|---|---|
| `/api/v1/billing/plans` | GET | SPEC/ADAPT | from UI package `/billing/plans`; public; backed by new `plans` catalog (D4) |
| `/api/v1/billing/checkout` | POST | SPEC/ADAPT | Razorpay order; `Idempotency-Key`; from UI package `/billing/checkout` |
| `/api/v1/billing/webhook` | POST | LIVE/ADAPT | **existing handler kept** (`subscriptions/webhook` logic: verify-before-parse + event dedup) re-mounted at `billing/webhook`; do not duplicate receivers |
| `/api/v1/subscriptions/webhook` | POST | LIVE | current path; retire after `billing/webhook` lands (keep alias one release) |

Decision: standardise the public surface on `billing/*`; preserve the existing webhook's security logic verbatim.

### 3.3 Instruments / scores (public read, numerics gated)

| Canonical path | Method | Status | Notes |
|---|---|---|---|
| `/api/v1/instruments/search` | GET | SPEC/ADAPT | UI `/instruments/search`; architecture `/api/search` family — unify here; Postgres FTS + pg_trgm (no ES) |
| `/api/v1/search/suggest` | GET | SPEC | architecture typeahead; <50 ms target |
| `/api/v1/search/interpret` | GET | SPEC | Pro; NL query |
| `/api/v1/stocks/{symbol}` | GET | SPEC | label + band public; numerics gated |
| `/api/v1/funds/{isin}` | GET | SPEC | architecture MF module |
| `/api/v1/etfs/{isin}` | GET | SPEC | architecture ETF module |
| `/api/v1/instruments/{symbol}/score` | GET | SPEC/ADAPT | returns **label + confidence band**; numeric score/factors only when tier-gated |
| `/api/v1/instruments/{symbol}/score/history` | GET | SPEC | track-record grouping |
| `/api/v1/instruments/{symbol}/fair-value` | GET | SPEC | Pro; 402 if free tier |
| `/api/v1/explain/{entity_type}/{id}` | GET | SPEC | architecture "Why this ranking" drawer (`RankingExplainer`) |

### 3.4 Mutual fund (architecture Phase-1 launch surface — MF-first)

`/api/v1/mf/upload/cas` (POST), `/mf/upload/cas/{job_id}/status` (GET), `/mf/portfolio/{user_id}` (GET), `/mf/portfolio/{user_id}/report` (GET), `/mf/fund/{isin}` (GET), `/mf/fund/{isin}/nav/history` (GET), `/mf/portfolio/{user_id}/overlap` (GET), `/mf/portfolio/{user_id}/refresh` (POST, 1/h). **Status: SPEC.** The UI package has **no CAS-upload screen** — that screen must be created in-system (UI package `agent.md` permits it).

### 3.5 ETF · Stock · Recommendations

- ETF: `/api/v1/etf/*` mirrors MF (SPEC).
- Stock: `/api/v1/stocks/{ticker}/{analysis,score,swot,history}`, `/api/v1/market/movers/{date}[/{ticker}]`, `/api/v1/stocks/picks` (anon top-5 no thesis / authed full-10). **Note:** architecture uses `/api/stocks/*` and `/market/*` unversioned — canonicalise to `/api/v1/stocks/*`, `/api/v1/market/*`.
- `/api/v1/recommendations` (GET, bearer) — UI package param `signal` enum **REJECTED**; replace with `label` ∈ canonical 4-label set; `sector`, `cursor` kept.

### 3.6 Portfolio · Watchlist · Alerts

- Portfolio: `/api/v1/portfolio` (POST/GET), `/portfolio/{id}/{sync,analytics,overlap,report-card}` (analytics = Pro, 402). UI package `/portfolio/holdings` ADAPT under this family.
- Watchlists: `/api/v1/watchlists` (GET/POST), `/watchlists/{id}/items` (from UI package; SPEC).
- Alerts: `/api/v1/alerts` (GET/POST, `Idempotency-Key`); `alert_rules.type` ∈ price/score/risk/earnings, `operator` ∈ gt/lt/eq/crosses (UI package enums kept — non-advisory, fine).

### 3.7 AI layer (governed OpenRouter — non-negotiable #5)

`/api/v1/ai/search` (POST, quota-gated, 429 on quota), `/api/v1/ai/assistant` (POST, SSE), `/api/v1/ai/explain/{symbol}` (GET). Every `AIAnswer` carries `answer → reasoning → confidence band → sources` + `NOT_ADVICE`. UI package's generic LLM assumption REJECTED in favour of the budget-governed gateway.

### 3.8 News · Mood · Track-record

- News: `/api/v1/news`, `/news/{article_id}`, `/news/ticker/{ticker}`, `/news/sector/{sector}`, `/news/today-summary` (canonicalised to `/api/v1`).
- Mood Compass: `/api/v1/market/mood`, `/market/mood/history`, `/market/why-today`, `/market/mood/embed`.
- Track-record: `/api/v1/track-record`, `/track-record/band/{band}`, `/track-record/sector/{sector}`, `/track-record/picks`, `/track-record/og-image`, `POST /api/v1/backtest/run` (Pro+), `GET /api/v1/backtest/{job_id}` (Pro+).

### 3.9 Consent / DPDP / Admin (architecture Global §3/§4/§9)

- Consent: `GET /api/v1/consent/status`, `POST /consent/{grant,revoke}`, `POST /data-rights/request`, `GET /data-rights/requests`.
- Compliance: `GET /api/v1/disclaimers/{type}`, admin disclaimer + label-churn endpoints.
- Onboarding: `/api/v1/onboarding/*`, `POST /onboarding/risk-quiz`, `/risk-profile/{history,retake}`.
- Admin/Governance: prompts/ranking-config/batches-approve/signal-health/content-moderation, `source-reliability` — all role-gated (needs `roles`/`user_roles`, see design/data docs).
- Internal: `GET /internal/v1/score/{instrument_type}/{identifier}` (engine; not public).

### 3.10 Rejected from UI package

- `/v1/*` base path (all) → repath `/api/v1/*`.
- `bearerAuth` security scheme → cookie auth.
- `/auth/otp/verify`, 202-OTP signup → preserved-not-activated.
- `screener/stocks` "Elasticsearch-backed" → re-spec on Postgres FTS (non-negotiable #3); path may stay `/api/v1/screener/stocks`, backend changes.
- `Signal` advisory enum everywhere → 4-label non-advisory set.

---

## 4. RFC7807 error mapping (canonical, D3 approved)

**Media type:** `application/problem+json`. **Every** error body:

```json
{
  "type": "https://dhanradar.com/errors/<slug>",
  "title": "<human summary>",
  "status": <http-code>,
  "detail": "<instance-specific message>",
  "request_id": "<uuid>",
  "instance": "/api/v1/<path>"
}
```

**Request-ID strategy:** middleware generates a UUID per request (or honours inbound `X-Request-ID`), attaches it to logs + the `request_id` field + a `X-Request-ID` response header. This is the correlation key across API logs, Sentry, and the audit trail.

**Canonical `type` taxonomy** (maps existing `detail` codes + UI-package catalog):

| `type` slug | HTTP | Replaces existing `detail` | Client treatment |
|---|---|---|---|
| `validation_error` | 400 | (FastAPI 422 default) | inline field errors |
| `unauthorized` | 401 | `not_authenticated`, `missing_refresh_token`, `invalid_refresh_token`, `user_not_found` | refresh-then-redirect to login |
| `invalid_credentials` | 401 | `invalid_credentials` | generic login error (no enumeration) |
| `upgrade_required` | 402 | tier-gate raise | contextual paywall (not an error card) |
| `consent_required` | 403 | consent-gate raise | consent prompt |
| `forbidden` | 403 | role/ownership | access-denied page |
| `not_found` | 404 | unknown resource | empty/not-found state |
| `conflict` | 409 | `duplicate email`, idempotency violation | inline message |
| `unprocessable` | 422 | semantic validation | inline |
| `rate_limited` | 429 | RateLimit, AI quota | `Retry-After`; AI quota → upgrade prompt |
| `invalid_signature` | 400 | `missing_signature`, `invalid_signature` (webhook) | n/a (server-to-server) |
| `internal` | 500 | unhandled | error card + retry + support link |
| `upstream_unavailable` | 502/503 | feed/model down | degraded mode: last-good data + banner |

**Note:** the Razorpay webhook keeps returning `400` on signature/JSON failure but in RFC7807 shape; payment idempotency unchanged (verify-before-parse + event dedup preserved).

---

## 5. Signal/label canonicalisation (non-negotiable #2)

The UI package score bands (`≥85 strong_buy / 70–84 buy / 55–69 hold / 40–54 caution / <40 avoid`) are **rejected**. Canonical non-advisory labels (architecture §S2.2):

| Canonical label | enum | Maps from UI band | Meaning (educational) |
|---|---|---|---|
| 🟢 In-form | `in_form` | strong_buy + buy | outperforming category, controlled drawdown |
| 🟡 On-track | `on_track` | hold | matching category, no red flags |
| 🟠 Off-track | `off_track` | caution | underperforming 12 m+ or structural concern emerging |
| 🔴 Out-of-form | `out_of_form` | avoid | sustained underperformance + structural concern |
| — Insufficient data | `insufficient_data` | confidence floor breach | refuse to label (confidence < 0.30) |

Confidence band enum: `high` / `medium` / `low` (UI package "Moderate" → `medium`). No numeric % in responses until the calibration gate passes.

---

## 6. API migration notes (for Stage 2 — not executed here)

1. **Regenerate `openapi.yaml`** into the repo from this spec: base `/api/v1`, cookie security scheme, RFC7807 components, 4-label enum, gated numerics. Then `npm run gen:api` produces a client that matches the live backend.
2. **Add a global RFC7807 exception handler** + request-id middleware (backend). **Security-adjacent? No** — error shaping is not auth logic, but it touches the auth error surface; review in Phase-3 critique.
3. **Re-mount the webhook** at `/api/v1/billing/webhook` preserving the verify-before-parse + dedup logic; keep `/subscriptions/webhook` as a temporary alias.
4. **Tier-gate + numeric-gating audit:** ensure every score/fair-value/factor field is suppressed on public/free responses at the serializer.
5. **No bearer tokens, no OTP activation, no Elasticsearch** — enforced by grep guard in CI (Stage 6).
6. Endpoints marked SPEC are built in their architecture phase; this doc only fixes their **shape**, not their schedule.

**~~Open item~~ RESOLVED (ADR-0011 / REC-D1):** the `factors` key set is **frozen** as `quality / valuation / momentum / risk / trend` (5-axis "Trend"; Growth nested as sub-factors within Trend). See `FINAL_SCORING_SPEC.md` §2.4/§3 and `ARCHITECTURE_DECISIONS.md` ADR-0011. The `openapi.yaml` `FactorAxis` enum reflects this and is correct.
</content>
