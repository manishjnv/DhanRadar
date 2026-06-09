# Review — G8 Tax-Education Engine (FY-aware educational content)

**Change-id:** g8-tax-education
**Date:** 2026-06-09
**Branch:** `feat/g8-tax-education`
**Tier:** A (standard feature) + **inline Compliance** (public-facing financial-education
content — the highest advice-adjacency surface in the build; Compliance NOT deferred).
**Decision driver:** G8 — a financial-year-aware educational engine on Indian MF taxation
(LTCG/STCG, ₹1.25L exemption, ELSS lock-in + 80C, IDCW, exit loads, FY key dates), static /
calendar-driven, no AI / no live data / no scoring, anonymous + crawlable (SEO).

## What changed

- **Migration 0015** (`0014`→`0015`, single head): `education` schema +
  `tax_education_articles` table (ships empty). `models/education.py`; registered in
  `env.py` + the test `db_tables` fixture.
- **`backend/dhanradar/education/`**: `content.py` (6 authored FY 2025-26 articles —
  ci_guards-scanned), `calendar.py` (pure FY logic + IST `today`), `schemas.py`,
  `service.py` (education schema reads only), `seed.py` (idempotent
  `python -m dhanradar.education.seed`), `router.py` (3 PUBLIC-read endpoints). One
  `include_router` line in `main.py`.
  - `GET /learn/tax` (list + category/fy filters), `GET /learn/tax/calendar` (FY key
    dates, computed from IST today), `GET /learn/tax/{slug}` (RFC7807 404 on bad slug).
- **Frontend**: server-rendered crawlable `/learn/tax` index + `[slug]` + `calendar`
  pages (`app/learn/tax/*`), per-page SEO `metadata`, `react-markdown` (server-side),
  `notFound()` on 404; `features/learn/api.ts` server-safe fetch (absolute base). Every
  page renders the contextual `<DisclosureBundle>` + standing `<Disclaimer/>`.

Public-read, no auth, no numeric surface. Every figure dated + FY-cited. No migration to
existing tables.

## Deterministic gates

ruff clean (touched); **565 backend unit pass + 1 xfail**; `ci_guards.py` advisory-verb
scan **clean** on the seed content; FE `tsc` clean, eslint clean, **73 vitest pass** (16
new for `learn`). 6 integration tests collect (run on CI Postgres). markdownlint on docs.

## Inline review panel (independent agents)

### Compliance (Opus) — ACCEPT-WITH-CONDITIONS → **blocker fixed inline**

Content clears the SEBI educational boundary cleanly: every article describes rules and
never recommends an action; the two choice-adjacent sections explicitly self-label "a
factual distinction, not a recommendation"; figures are FY-cited; tax rules read correct
for FY 2025-26 / Finance Act 2024.

- **BLOCKER (FIXED):** the `not_advice` field used the platform `NOT_ADVICE` marker, which
  is the literal token `"NOT_ADVICE"` — it would render as the bare word on every public
  tax page (non-neg #9 failure). Fixed **lane-safely** (the token lives in
  `scoring/engine/schemas.py`, Session A's lane — not edited): the education module now
  supplies its own human line `EDUCATION_NOT_ADVICE = "Not tax or investment advice."`.
- Cond (FIXED): ELSS STCG clause clarified to "the equity rate of 20% (Section 111A)".
- Cond → **G8-f1 (DEFERRED):** add `rehype-sanitize` + reject non-http(s) `href` schemes
  in the markdown renderer before any admin content-write path exists (content is fully
  trusted today; react-markdown v10 renders no raw HTML).
- **Human CA must verify before deploy** (compliance signs the *advice boundary*, not the
  numbers): equity 20%/12.5%/₹1.25L; specified-fund §50AA slab + 1-Apr-2023 cut-off;
  pre-Apr-2023 debt 12.5% no-indexation >36m; IDCW slab + §194K 10% over ₹5,000; ELSS
  3-yr lock-in + 80C old-regime-only; advance-tax dates + 31-Jul ITR.

### Architect (Sonnet) — ACCEPT-WITH-CONDITIONS

Migration chain (single head), module isolation (education schema only; reads
`scoring.engine.schemas` constants read-only like mood; no dashboard import; no writes),
public-read auth, route order (`/calendar` before `/{slug}`), seed idempotency, and the
SSR base fix all confirmed correct.

- Cond (FIXED): IST FY boundary — `date.today()` on a UTC server showed the old FY for
  00:00–05:30 IST on 1 April; now computed in IST (fixed +5:30, no tzdata dep).
- Cond (FIXED): FE `source_note` typed `string | null` to match the nullable backend.
- Cond (FIXED): `conftest` `db_session` teardown now truncates `education.*` for
  consistency (the integration test also truncates it).
- Cond → **G8-f2 (DEFERRED, deploy step):** the table ships empty — prod must run
  `python -m dhanradar.education.seed` after `alembic upgrade`, and the nextjs container
  must set `INTERNAL_API_URL=http://dhanradar-fastapi:8000/api/v1` for SSR fetches.
  Documented in `docs/features/education.md`; no deploy this session.

## Ledger

| Gate | Status |
|---|---|
| Deterministic (unit · ruff · ci_guards · FE tsc/eslint/vitest) | ✅ green |
| Compliance (Opus) | ✅ ACCEPT — blocker + conds fixed inline; human-CA list logged |
| Architect | ✅ ACCEPT-WITH-CONDITIONS — conds fixed; G8-f1/f2 deferred |
| **Merge-eligible** | ✅ yes (pending CI green on PR) |
| **Deploy-eligible** | needs the G8-f2 deploy steps + human CA tax sign-off + approval |

**Lane honored:** no edits to `scoring/engine/*`, `mf/signals.py`, `mf/scoring_bridge.py`
(Session A) or `dashboard/*` + `frontend/src/features/dashboard/*` (Session B); `main.py`
got exactly one `include_router` line.
