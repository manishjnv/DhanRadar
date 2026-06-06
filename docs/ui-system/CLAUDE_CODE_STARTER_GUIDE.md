# CLAUDE CODE — Starter Guide (begin immediately, zero ambiguity)

You are implementing **DhanRadar** from this package. Read this first, then build in the order below. Everything referenced exists in the package.

## 0. Orientation (read, in order)
1. `PACKAGE_MANIFEST.md` — file map.
2. `docs/01-product-strategy.md`, `docs/02-information-architecture.md` — what & why.
3. `docs/03-backend-architecture.md`, `docs/05-frontend-architecture.md` — how.
4. `contracts/*` — the **machine-readable truth** (openapi.yaml, schema.sql, seed-data.json, score-model.md, route-map.md, error-catalog.md, analytics-events.md).
5. `recommendation-engine/*`, `ai-governance/*`, `compliance/*` — the rules that must not be violated.

## 1. Bootstrap (exact)
```
cd project-config && cp .env.example .env   # fill: JWT keys, LLM, Razorpay
docker compose up -d                          # postgres(+schema.sql), redis, elasticsearch
# api:
cd ../api && uv sync --frozen && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
# web:
cd ../web && npm ci && npm run gen:api        # types from contracts/openapi.yaml
cp ../tokens/css-variables.css src/styles/tokens.css
npm run dev
# seed: load contracts/seed-data.json
```
Verify: dashboard renders seed instruments + scores; theme toggles; /docs matches openapi.yaml.

## 2. Build order (do not reorder)

1. **Tokens + components/ui** — from canonical `frontend/` tokens (`frontend/styles/tokens.json`) + `frontend/src/components/`, using `/components/*.md` here as spec reference only (Button, Card, ScoreRing exist). Lint: no magic numbers.
2. **Backend core** — schema (contracts/schema.sql), auth (claude-code/auth-spec), instruments/scores read API (openapi.yaml). Repository→service→router layering.
3. **Score engine** — implement exactly per `recommendation-engine/score-formula.md` + `confidence-formula.md`. Deterministic; `scores` table read-only except scoring worker; `scoring` must NOT import `billing`.
4. **Frontend core** — App Router groups per `route-map.md`; public stock page SSR/ISR with ungated score; four states on every data component.
5. **AI** — AI Gateway first (ai-governance/ai-governance.md); every output: answer→reasoning→confidence→sources + NOT_ADVICE; prohibited-language gate (compliance).
6. **Events** — wire the event bus (event-architecture); MarketDataUpdated→scoring→alerts→notify.
7. **Billing, watchlist/alerts, portfolio** — per /screens specs.
8. **Observability + analytics** — instrument per `/observability` + `/analytics` (typed track()).

## 3. Non-negotiable invariants (enforce in code + tests)
- **Scores read-only** to all but the scoring worker (DB grant); `scoring` cannot import `billing` (import-lint).
- **AI never advises / never invents numbers** — numbers injected from data; prohibited-language classifier blocks "you should buy"; every output carries NOT_ADVICE.
- **Risk profile never feeds the score** (compliance separation; test it).
- **Idempotency-Key** on all mutating/payment endpoints; consumers dedupe by event_id.
- **Disclosures** rendered via the Compliance Gate + logged to recommendation_audit.
- **Freshness honesty** — stale/offline data shown "as of"; lowers confidence; never implied live.
- **Confidence %** not exposed to users until calibrated (band-only).
- **A11y** — four states, focus rings, chart text-alternatives; axe + Lighthouse budgets in CI.

## 4. Definition of done (per feature)
Four states (loading/empty/error/success) · a11y pass · analytics events fired · error-catalog mapping · tests (unit + e2e for critical flows) · disclosures where applicable · within perf/bundle budget.

## 5. Where to look (quick map)
- API shape → `contracts/openapi.yaml` · DB → `contracts/schema.sql` · score math → `recommendation-engine/` · AI rules → `ai-governance/` + `compliance/` · screens → `/screens/*.md` · components → `/components/*.md` · events → `/event-architecture/` · ops → `/observability` + `docs/06` · mobile → `/mobile` · what to build when → `IMPLEMENTATION_ROADMAP.md`.

**Start now:** Section 1 → Section 2 step 1. Ask nothing; the answers are in the referenced files. For business decisions (pricing values, vendor choice), use the documented defaults and flag for PM.
