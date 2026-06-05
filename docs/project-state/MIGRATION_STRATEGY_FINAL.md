# Migration Strategy — Final Classification

**Stage 1 — Contract Reconciliation. Documentation only; no code, schema, or infra changed.**
**Date:** 2026-06-05
**Authority order (binding):** `DhanRadar_Architecture_Final.md` → `DhanRadar_Implementation_Plan.md` → existing implementation → `docs/features` → `docs/ui-system` → mockups.

Classifies every asset across 8 domains as **KEEP** / **MERGE** / **REPLACE** / **IGNORE**, relative to the existing repo.

- **KEEP** — existing repo is canonical; do not change.
- **MERGE** — keep existing; harvest specific additive value from the UI package.
- **REPLACE** — existing is a placeholder/skeleton; adopt the UI package's (retokenized/repathed) version.
- **IGNORE** — UI-package asset rejected outright (conflicts with a non-negotiable).

---

## 1. Backend

| Item | Class | Rationale |
|---|---|---|
| `dhanradar` Python package + module layout (`dhanradar.main`, `dhanradar.celery_app`) | **KEEP** | wired into compose/tunnel; UI package's `app.*` ignored (non-neg #6) |
| FastAPI app, lifespan startup, `/api/v1` router mounting | **KEEP** | matches architecture |
| Auth slice (cookie JWT, refresh rotation, TOTP) | **KEEP** | non-neg #4; security-reviewed |
| Razorpay webhook (verify-before-parse + event dedup) | **KEEP** | preserve logic; re-mount path under billing (MERGE at API layer) |
| Celery batch/mood/misc + beat, IST timezone | **KEEP** | architecture §B6 |
| Budget governor (`budget.py`), OpenRouter env | **KEEP** | non-neg #5 |
| RFC7807 exception handler + request-id middleware | **MERGE** | adopt UI package error catalog onto existing app (D3) |
| `roles`/`user_roles` admin RBAC, `plans`, `usage_counters` concepts | **MERGE** | harvest UI-package tables for admin/quota surfaces (additive) |
| UI package `app.workers.*`, generic LLM client, SES email | **IGNORE** | conflicts with package name / OpenRouter / Resend |

## 2. Frontend

| Item | Class | Rationale |
|---|---|---|
| `frontend/` dir name, Next 14 + React 18 base | **KEEP** | wired to compose/tunnel |
| Canonical tokens (`tokens.json/.css`, `tailwind.config.js` — Geist/warm) | **KEEP** | D1 winner |
| `src/` feature-slice structure (features/components/lib/hooks/types) + ESLint import isolation | **REPLACE** | existing is an empty skeleton; adopt UI-package structure inside `frontend/` |
| Dependency set (TanStack Query, Zustand, RHF, Zod, Radix, CVA, tailwind-merge, sonner, next-pwa, vitest, playwright, msw, openapi-typescript) | **REPLACE** | skeleton has none; adopt UI-package set |
| reference-impl components (Button, Card, ScoreRing, apiClient, cn, queryKeys) | **MERGE** | adopt but retokenize (Geist/warm) + apiClient→cookie auth + `/api/v1`; ScoreRing→band not numeric |
| UI-package Manrope/cool tokens, `tailwind.preset.ts` | **IGNORE/RETIRE** | competes with D1 winner |

## 3. APIs

| Item | Class | Rationale |
|---|---|---|
| `/api/v1` base path | **KEEP** | existing + ingress; UI `/v1` ignored |
| Cookie auth scheme | **KEEP** | non-neg #4; UI bearerAuth ignored |
| Auth/subscription endpoints (existing) | **KEEP** | |
| RFC7807 error shape + catalog + `type` taxonomy | **MERGE** | D3; adopt from UI package |
| `billing/*` (plans, checkout), instruments/scores/portfolio/watchlist/alerts/ai/news/mood/track-record shapes | **MERGE** | adopt UI-package + architecture shapes, repathed `/api/v1`, relabelled non-advisory |
| Regenerated `openapi.yaml` | **REPLACE** | rewrite UI-package spec to canonical (see OpenAPI doc) |
| `/v1` paths, bearerAuth, `/auth/otp/verify`, 202-OTP signup, advisory `Signal` enum, ES-backed screener | **IGNORE** | non-negotiables #2/#3/#4 + D2 |

## 4. Database

| Item | Class | Rationale |
|---|---|---|
| `auth` schema, `auth.users` (+ DPDP/TOTP fields), `auth.subscriptions`, migration 0001 | **KEEP** | matches architecture Global §2; non-neg #6 |
| Schema-per-concern namespacing | **KEEP** | architecture §B5 decoupling invariant; UI flat `public` ignored |
| Existing column names (`hashed_password`, `razorpay_subscription_id`, `plan`) | **KEEP** | already migrated |
| `plans` catalog + `subscriptions.plan_id` FK | **MERGE** | D4; additive migration, backward-compatible (keep `plan` text during transition) |
| `roles`/`user_roles`, `sessions`, `usage_counters`, `audit_log` (hash-chained), watchlist/alert/ai/news/corporate_actions/ingest_runs tables | **MERGE** | harvest from UI package, schema-qualified, built per architecture phase |
| `otp_codes` table | **MERGE (dormant)** | preserve schema/doc; not activated (D2) |
| Per-module tables (`mf_funds`, `etf_metadata`, `stocks`, hypertables) | **KEEP (SPEC)** | architecture module-isolated model |
| UI-package unified `instruments`/`instrument_prices`/flat `scores` as *physical* schema | **IGNORE** | violates module-isolation; usable only as a serializer read-shape |
| TimescaleDB requirement | **KEEP** | non-neg #6; UI plain-pg16 ignored |

## 5. Design System

| Item | Class | Rationale |
|---|---|---|
| Geist/warm brand tokens (repo + `ui-system/brand/`) | **KEEP** | D1 winner |
| reference-impl components | **MERGE** | retokenize to canonical |
| component specs `/components/*.md`, screens `/screens/*.md`, figma `/figma/*` | **MERGE** | retokenize + relabel advisory copy; rebuild in canonical |
| `ui-system/design-system/` + `ui-system/tokens/` (Manrope/cool) | **IGNORE/RETIRE** | duplicate competing language |
| `/html/*` mockups | **KEEP (reference-only)** | visual reference, not build source |

## 6. Infrastructure

| Item | Class | Rationale |
|---|---|---|
| `docker-compose.yml` (8-container, no host ports) + `override` | **KEEP** | non-neg #6 |
| cloudflared dedicated tunnel model | **KEEP** | non-neg #6; security-critical |
| `timescale/timescaledb-ha:pg16`, dedicated redis | **KEEP** | non-neg #3/#6 |
| Reuse `shared_prometheus`/`shared_grafana` | **KEEP** | architecture infra-reuse |
| GitHub Actions CI workflow | **MERGE** | adapt UI-package CI to `backend/`+`frontend/`, `dhanradar`, ruff/mypy/pytest + vitest/playwright + grep guards |
| OpenTelemetry instrumentation | **MERGE** | export to reused Prometheus, no parallel stack |
| UI-package compose (published ports, Elasticsearch service, plain pg16, no tunnel) | **IGNORE** | non-neg #3/#6 |

## 7. AI Layer

| Item | Class | Rationale |
|---|---|---|
| OpenRouter gateway, free-pool→Sonnet spillover, `budget_guard()`, hard/soft caps | **KEEP** | non-neg #5 |
| `AIOutputBase` contract (answer→reasoning→confidence band→sources + NOT_ADVICE), prohibited-language gate | **KEEP** | architecture §B3/§C |
| AI endpoint shapes (`/ai/search`, `/ai/assistant` SSE, `/ai/explain`) | **MERGE** | adopt UI-package shapes, repathed `/api/v1`, governed gateway |
| UI-package generic `LLM_API_KEY`/`LLM_BASE_URL`, ungoverned model | **IGNORE** | replaces governance; rejected |
| `ai-governance/*` docs (prompt versioning, eval, hallucination controls) | **MERGE** | harvest as governance reference aligning with architecture §C |

## 8. Recommendation Engine

| Item | Class | Rationale |
|---|---|---|
| §S contract: label taxonomy, no-numeric-in-DOM, confidence floor, hysteresis, churn gate, methodology changelog, risk-profile exclusion | **KEEP** | architecture is canonical |
| Factor sub-weights, winsorize/z-score normalization, missing-data, fair-value blend, risk sub-formula, confidence input weights, benchmark, backtesting, version lifecycle | **MERGE** | adopt UI-package numbers as `ranking_configs` v1 proposal (subject to pass-gates) |
| Advisory `strong_buy/buy/hold/caution/avoid` labels | **IGNORE** | non-neg #2 |
| `Growth` vs `Trend` axis | **MERGE (pending REC-D1)** | architecture owns the name; recommend amend to Growth + adopt sub-factors |
| Risk-profile questionnaire content | **MERGE** | 8 questions usable, re-scaled to architecture buckets + `not_set` |

---

## 9. Classification tally
- **KEEP:** all load-bearing backend, auth, DB schema, infra, AI governance, engine contract.
- **MERGE:** RFC7807, plans catalog, admin/quota/session/audit tables, retokenized components, CI, engine quantitative detail.
- **REPLACE:** frontend `src/` structure + dependency set + regenerated `openapi.yaml` (skeleton → real).
- **IGNORE:** UI `/v1` paths, bearerAuth, OTP-first, advisory labels, Elasticsearch, plain-pg16, published-ports compose, Manrope/cool tokens, generic LLM client, flat `public` schema, unified physical `instruments` table.

No asset is deleted or modified by this document. This is the instruction set for Stage 2.
</content>
