# Concept-Explainer "Learn" Library (C1) — as built

**Status:** built 2026-06-11 · branch `feat/c1-concept-explainers` · Plan: GROWTH_BACKLOG C1
(Tier 1, "build now") · Pattern sibling of the G8 tax-education module
(`docs/features/education.md`) — different module, different schema, different table.

## What it is

A static library of evergreen plain-language explainers for core investing concepts —
what they are and why they matter. PURE education: no live data, no AI, no scoring, no
personalization. Anonymous-first crawlable SEO/acquisition asset.

Launch set (8 concepts): risk · volatility · drawdown · diversification · asset
allocation · expense ratio (TER) · SIP/rupee-cost averaging · compounding.

## Backend (`backend/dhanradar/concepts/`)

```text
backend/dhanradar/concepts/
  __init__.py
  router.py        # APIRouter(tags=["learn"]); /learn/concepts + /learn/concepts/{slug}
  schemas.py       # ConceptSummary, ConceptListResponse, ConceptDetail (+ disclosure mixin)
  service.py       # async reads over concepts.concept_explainers only
  content.py       # the 8 authored explainers (ci_guards-scanned) + disclosure constants
  seed.py          # python -m dhanradar.concepts.seed (idempotent upsert by slug)
backend/dhanradar/models/concepts.py   # ConceptExplainer ORM (schema "concepts")
backend/alembic/versions/0017_concepts_schema.py  # concepts schema + table (revises 0016)
```

### Endpoints (anonymous-read, crawlable; base `/api/v1`)

- `GET /learn/concepts` — list, optional `category` filter; unmatched filter → 200 `[]`.
- `GET /learn/concepts/{slug}` — one concept; unknown slug → RFC7807 404
  `concept_not_found`.

Every response carries the disclosure bundle (non-neg #9): module-own `disclosure` +
`not_advice` strings (`content.py`) + the shared in-force `disclaimer_version`
(read-only import, same precedent as education).

### Table `concepts.concept_explainers`

`slug` (PK) · `title` · `summary` · `body_md` (Markdown) · `category` · `sort_order` ·
`updated_at`. Ships EMPTY from the migration; content loads via the seed command.
Categories: "Risk & return", "Portfolio basics", "Costs", "Investing habits".

## Frontend

```text
frontend/src/features/learn/concepts-api.ts        # server-only fetch (INTERNAL_API_URL)
frontend/src/components/concepts/ConceptsIndex.tsx  # presentational index (category groups)
frontend/src/components/concepts/ConceptArticle.tsx # presentational detail (react-markdown)
frontend/src/app/learn/concepts/page.tsx            # SSR index — force-dynamic
frontend/src/app/learn/concepts/[slug]/page.tsx     # SSR detail — force-dynamic
```

Both pages live OUTSIDE the `(app)` route group (no AuthGuard; MaybeShell chrome) and set
`export const dynamic = 'force-dynamic'` per the 2026-06-10 SSR build-time ECONNREFUSED
RCA; server fetches resolve an absolute base from `INTERNAL_API_URL`. Nav: "Investing
Basics" entry in `AppShell.tsx`; the index cross-links the sibling `/learn/tax` area.
Live Geist/warm tokens only; `DisclosureBundle` renders on every page (index footer,
detail above the body); the standing `<Disclaimer/>` comes from MaybeShell.

## Compliance posture (SEBI educational boundary)

- Copy is descriptive/definitional only — no advisory verbs, no second-person
  imperatives, no action nudges; `scripts/ci_guards.py` Guard #4 scans `content.py`.
- Every rupee figure carries the standing "hypothetical illustration (authored June
  2026)" label (unit-test enforced); no projection/guarantee framing anywhere.
- Asset-allocation copy explicitly defers personal suitability to SEBI-registered
  advisers; SIP copy carries the no-assured-profit caveat.
- No numeric DhanRadar score surface; no auth change (public-read); DPDP-irrelevant
  (no user data).

## Tests

- `backend/tests/integration/test_concepts.py` — canonical `async_client`/`db_session`
  fixtures: list happy (anonymous), category filter, unknown category → 200 `[]`,
  slug happy, bad slug → RFC7807 404; disclosure asserted throughout.
- `backend/tests/unit/test_concepts.py` — advisory-framing phrase screen, labelled-
  illustration rule for ₹ figures, well-formedness/unique slugs, 8 launch slugs,
  schema disclosure-bundle fields.
- `frontend/.../ConceptsIndex.test.tsx`, `ConceptArticle.test.tsx`,
  `concepts-api.test.ts` — index/detail render incl. not-advice disclosure presence;
  404 → null; category param pass-through (13 tests).

## Deploy notes

1. `alembic upgrade head` (0017) — verify `alembic current`.
2. `python -m dhanradar.concepts.seed` on the box (idempotent; re-run on content edits).
3. `INTERNAL_API_URL` must be set on the nextjs container (shared prerequisite with G8).

## Future (not built)

Contextual surfacing of concepts by holdings (the dynamic half of C1) waits for real
portfolio data. Glossary/static sibling routes, if added, must be declared BEFORE the
`{slug}` route (see router docstring).
