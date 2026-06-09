# Feature — Dashboard (Post-Login Home Screen)

**Status:** B56 built (read-only aggregation, 3 live endpoints, 1 deferred); merge-eligible, NOT
deployed · **Phase:** B56 · **Last updated:** 2026-06-09

## Purpose & scope

The post-login home screen (`/dashboard`). Aggregates the authenticated user's own portfolio
summary, live market index levels, and their top-scored funds into a single read-only view. Replaces
the prior 404 mock-only stub that caused a blank home screen on login.

The dashboard owns NO data — it is a pure reader. Every endpoint delegates to the module that owns
the data (`mf` schema, Yahoo Finance helpers, Redis).

## Non-goals

- Does not own or write to any table.
- Does not re-compute scores, signals, or labels (those are the scoring engine's and MF module's
  domain).
- Does not render a numeric score, factor weight, or fair value to the client (non-neg #2).
- Does not serve a news feed (the `/news` widget is deferred — no source wired; widget stays on its
  empty state).
- Risk profile never feeds any dashboard output (non-neg #3).

## Public interface (all under `/api/v1`, all authenticated — anonymous → 401)

### `GET /portfolio/summary`

The requesting user's own MF portfolio rollup. Reads `mf.mf_portfolios`,
`mf.mf_user_holdings`, `mf.mf_portfolio_snapshots`, and `mf.user_fund_scores`.

**Response (`PortfolioSummaryResponse`):**

| Field | Type | Notes |
|---|---|---|
| `current_value` | `float \| null` | May be null — snapshot not yet computed |
| `xirr_pct` | `float \| null` | User's own XIRR; null until NAV pipeline seeded (B29) |
| `fund_count` | `int` | Total distinct funds held |
| `last_updated` | `datetime \| null` | Timestamp of the latest snapshot |
| `funds` | `list[FundSummaryItem]` | Per-fund label + band only — no numeric |
| `disclosure` | `str` | Injected by the service layer |
| `not_advice` | `str` | "NOT_ADVICE" constant (non-neg #9) |
| `disclaimer_version` | `str` | In-force disclaimer version |

Each `FundSummaryItem`: `{isin, scheme_name, label, confidence_band}` — `unified_score` is never
serialized (explicit Pydantic allowlist).

**404 on cold-start:** if the user has no portfolio or no holdings, the endpoint returns RFC7807
`404 portfolio_not_found`. The frontend hook treats this as the empty / onboarding state (not an
error screen).

### `GET /indices`

Live market index levels. Reuses the existing Yahoo Finance provider helpers
(`dhanradar/market/yahoo.py`) — NSE direct endpoints are geo-blocked on KVM4.

**Response** — array of `IndexLevel`:

| Ticker | Name |
|---|---|
| `^NSEI` | NIFTY 50 |
| `^BSESN` | SENSEX |
| `^NSEBANK` | NIFTY Bank |
| `NIFTYMIDCAP150.NS` | NIFTY Midcap 150 |

Each item: `{name, value, change_pct}`.

**Caching:** Redis key `dashboard:indices`, TTL 60 s. On a Yahoo outage or Redis miss that cannot be
refreshed, degrades to `[]` (empty array) — the widget shows its empty state rather than
erroring.

### `GET /instruments/top-scored`

Query param: `type=fund` (only value supported at launch).

**Response (`TopScoredResponse`):**

| Field | Type | Notes |
|---|---|---|
| `funds` | `list[TopScoredFund]` | User-scoped, ranked by label severity |
| `disclosure` | `str` | Injected disclosure bundle |
| `not_advice` | `str` | "NOT_ADVICE" constant (non-neg #9) |
| `disclaimer_version` | `str` | In-force disclaimer version |

Each `TopScoredFund`: `{isin, scheme_name, category, label, confidence_band}` — no numeric.

**User-scoped:** reads only `mf.user_fund_scores` rows owned by the requesting `user_id`. This is
NOT a platform-wide recommendation or a leaderboard — it is the user's own funds ranked by label
severity. `type != fund` returns an empty `funds` list.

**Quality note:** results improve automatically once NAV data (B29) and B58 cohort labels populate.
Until then, most entries will carry `insufficient_data`.

### `/news` (widget only — DEFERRED)

No news source is wired. The frontend widget renders its built-in empty state. No backend route is
mounted for this path.

## Module isolation

The dashboard module reads ONLY:

- `mf` schema tables: `mf_portfolios`, `mf_user_holdings`, `mf_portfolio_snapshots`,
  `mf_user_fund_scores`, `mf_funds`.
- Shared helpers: `dhanradar/market/yahoo.py` (Yahoo Finance provider) and Redis (indices cache).

No reach-in to the scoring engine, billing, consent, notifications, or any other module. No writes.
No Alembic migration (schema-free consumer).

## Compliance

- **No numeric in DOM** — all three Pydantic response schemas have an explicit field allowlist;
  `unified_score` and factor weights are never serialized (non-neg #2).
- **Disclosure bundle on every label surface** — `portfolio/summary` and `instruments/top-scored`
  both carry `disclosure`, `not_advice`, and `disclaimer_version` in every response (non-neg #9).
- **Cookie-only auth** — `__Host-` HttpOnly RS256 JWT; anonymous requests → 401 before any DB read
  (non-neg #5). No `Authorization` header.
- **RFC7807 errors** — 404 `portfolio_not_found` on cold-start; 422 on bad params.
- **No advisory labels** — labels are drawn from the SEBI-educational allowlist
  (`in_form/on_track/off_track/out_of_form/insufficient_data`); advisory verbs are rejected by
  `ci_guards.py` (non-neg #1).

## Files

### Backend

| Path | Purpose |
|---|---|
| `backend/dhanradar/dashboard/schemas.py` | Pydantic response models (explicit allowlist — no `unified_score`) |
| `backend/dhanradar/dashboard/service.py` | Portfolio summary + top-scored assembly; disclosure injection |
| `backend/dhanradar/dashboard/indices.py` | Yahoo Finance fetch + Redis cache logic |
| `backend/dhanradar/dashboard/router.py` | FastAPI router — mounts the 3 endpoints |
| `backend/dhanradar/main.py` | `app.include_router(dashboard_router, prefix="/api/v1")` mount |

### Frontend

| Path | Purpose |
|---|---|
| `frontend/src/features/dashboard/api.ts` | TanStack Query hooks for the 3 endpoints; treats 404 as empty state |
| `frontend/src/app/(app)/dashboard/page.tsx` | Dashboard page — orchestrates portfolio, indices, top-scored widgets |
| `frontend/src/mocks/handlers.ts` | MSW handlers for all 3 endpoints (dev + test) |

### Tests

| Path | Scope |
|---|---|
| `backend/tests/unit/test_dashboard.py` | Unit: schema no-numeric assertion, 404 cold-start, indices cache hit/miss, top-scored user-scoping, type filter |
| `backend/tests/integration/test_dashboard.py` | Integration: auth gate (401), portfolio summary round-trip, indices degraded path |
| `frontend/src/features/dashboard/api.test.ts` | FE: hook renders empty state on 404; MSW happy paths |

## Known follow-ups (filed)

- **B56-f1** — move disclosure-bundle constants (`disclosure`, `not_advice`, `disclaimer_version`
  injection) to a shared module so all consumers (MF report, top-scored, portfolio summary) use one
  source of truth.
- **B56-f2** — expose Yahoo Finance helpers as a public `market.yahoo` module API rather than
  importing from `market/` internals directly.
- **B56-f3** — composite index endpoint: parallel Yahoo fetch for all 4 tickers in a single async
  gather (currently sequential) to reduce latency.
- Cross-link: governance review ledger `docs/project-state/reviews/b56-dashboard-endpoints.md`.

## Changelog

- 2026-06-09 — B56 built: `GET /portfolio/summary`, `GET /indices` (Redis 60s + Yahoo degraded
  path), `GET /instruments/top-scored?type=fund` (user-scoped, label+band only); disclosure bundle
  on all label surfaces; no numeric in DOM (explicit Pydantic allowlist); RFC7807 cold-start 404;
  frontend hooks + page + MSW handlers; unit + integration + FE tests. `/news` deferred (empty
  state). Module isolation: `mf` schema + Yahoo/Redis; no writes; no migration. Tier-A change;
  Builder + Architect + UI reviews; Compliance inline (no numeric/advisory on any surface). Commit
  branch `feat/b56-dashboard-endpoints`; PR `#56`. Ledger: `reviews/b56-dashboard-endpoints.md`.
