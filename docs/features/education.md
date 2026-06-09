# Feature — Tax-Education Engine (G8)

**Status:** Built, Tier-A reviewed (Compliance+Architect ACCEPT-WITH-CONDITIONS, inline); merge-eligible;
NOT deployed (seed + INTERNAL\_API\_URL + CA sign-off required before public launch)
**Branch:** `feat/g8-tax-education` · **Phase:** G8 · **Last updated:** 2026-06-09

## Purpose & scope

FY-aware educational content on Indian MF taxation. Purely educational — never advisory. Content is
static and calendar-driven: no AI inference, no live market data, no scoring, no user profile.
Endpoints are public-read and server-rendered — anonymous access, no auth required — so pages are
crawlable and indexable (SEO). Every response carries the disclosure bundle and a `NOT_ADVICE`
marker; the education module supplies its own human `EDUCATION_NOT_ADVICE` line (distinct from the
platform `NOT_ADVICE` sentinel used by the scoring/AI surfaces).

## Non-goals

- No AI generation (static authored content only — no OpenRouter calls, no prompt registry, no
  audit rows in `ai_recommendation_audit`).
- No live pricing, NAV, or fund signals.
- No personalisation or user-specific output (no `user_id`, no consent gate, no `RequireTier`).
- No buy/sell/hold framing; no advisory verbs (`avoid`, `buy`, `strong_buy`, `caution`) anywhere in
  copy or enum values.
- Does not own scoring labels, risk profiles, or the compliance audit trail — those modules are out
  of scope for G8.

## Schema & migration

New `education` schema. Migration `0015` chains from `0014` (audit-ledger).

Table: `education.tax_education_articles`

| Column | Type | Notes |
|---|---|---|
| `slug` | `TEXT PRIMARY KEY` | URL-safe identifier, e.g. `equity-fund-tax-fy2526` |
| `category` | `TEXT NOT NULL` | e.g. `capital_gains`, `elss`, `idcw`, `debt`, `exit_load` |
| `fy` | `TEXT NOT NULL` | e.g. `2025-26`; all current content targets FY 2025-26 |
| `title` | `TEXT NOT NULL` | Human-readable heading |
| `summary` | `TEXT NOT NULL` | One-sentence description for list views |
| `body_md` | `TEXT NOT NULL` | Markdown body; rendered server-side |
| `source_note` | `TEXT NOT NULL` | Citation / effective-date note (e.g. "Finance Act 2024, FY 2025-26") |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |

The table ships **empty** from the migration. Content is authored in
`backend/dhanradar/education/content.py` (6 articles, FY 2025-26) and loaded by the seed command
below. This separation keeps editorial content out of the migration chain.

## Content coverage (FY 2025-26)

All figures are dated to FY 2025-26; each article carries a `source_note` citing the governing
statute or Finance Act amendment.

| Article slug | Category | Key figures |
|---|---|---|
| `capital-gains-basics` | `capital_gains` | STCG/LTCG definitions; holding-period thresholds (equity ≥12 m, debt ≥24 m post 1-Apr-2023) |
| `equity-fund-tax` | `capital_gains` | STCG 20 % (§111A); LTCG 12.5 % over ₹1.25 L exemption (§112A, Finance Act 2024) |
| `debt-fund-tax` | `debt` | Taxed at slab post 1-Apr-2023 (§50AA indexation removal); 24-month LTCG period retained but rate = slab |
| `elss-tax` | `elss` | 3-year statutory lock-in; §80C deduction up to ₹1.5 L (old regime only; new regime ineligible) |
| `idcw-tax` | `idcw` | Dividend taxed at investor's slab; §194K TDS at 10 % when aggregate IDCW > ₹5,000 per FY |
| `exit-loads` | `exit_load` | Exit loads reduce redemption proceeds (not a tax but reduces effective return); common 1 %/1-year structures |

`ci_guards` scans article content for advisory verbs at CI time — any introduction of
`avoid`/`buy`/`hold`/`caution`/`strong_buy` in the body text fails the guard.

## Public interface (all under `/api/v1`)

All endpoints: public-read (no auth, no tier gate, no consent check); RFC7807 errors; every
successful response includes `disclosure`, `not_advice`, and `disclaimer_version` from the in-force
disclaimer record.

### `GET /learn/tax`

List all published articles. Optional query params:

- `?category=<value>` — filter by `category` column
- `?fy=<value>` — filter by `fy` column (e.g. `?fy=2025-26`)

Returns `{"articles": [...], "disclosure": "...", "not_advice": "...", "disclaimer_version": "..."}`.
An empty list `[]` is a valid response (e.g. before seeding — see deploy steps). Never 404.

### `GET /learn/tax/{slug}`

Single article by slug. Returns the full `body_md`, `source_note`, and the disclosure bundle.

Error: `404 article_not_found` (RFC7807) on an unrecognised slug.

### `GET /learn/tax/calendar`

FY-aware statutory key dates, computed from IST today at request time. No DB read for the dates
themselves — computed deterministically. Includes:

- Advance-tax instalments (15 Jun / 15 Sep / 15 Dec / 15 Mar)
- FY end (31 Mar)
- ITR due date (31 Jul, non-audit)
- ELSS lock-in note (purchases before 31 Mar unlock 3 years later)

Response carries the disclosure bundle identically to the other endpoints.

## Seeding

The table ships empty from the migration. Run the seed command after `alembic upgrade head`:

```bash
python -m dhanradar.education.seed
```

This inserts the 6 articles from `backend/dhanradar/education/content.py`. The command is
idempotent (upsert by slug). Until the seed runs, `GET /learn/tax` returns `[]`.

## Frontend

Server-rendered Next.js pages under `app/learn/tax/`:

| Route | Page file | Notes |
|---|---|---|
| `/learn/tax` | `app/learn/tax/page.tsx` | Article list; SSR fetch; per-page SEO metadata |
| `/learn/tax/[slug]` | `app/learn/tax/[slug]/page.tsx` | Article detail; `notFound()` on 404 |
| `/learn/tax/calendar` | `app/learn/tax/calendar/page.tsx` | Key-dates view; SSR |

Server-component fetches use an absolute base URL resolved in
`frontend/src/features/learn/api.ts` — required because a relative `/api/v1` path cannot be fetched
server-side (no browser origin). The absolute base is read from `process.env.INTERNAL_API_URL` on
the Next.js container (see deploy steps).

Article bodies are rendered with `react-markdown` (server-side). Each page renders:

- `<DisclosureBundle>` populated from the API response payload
- A standing `<Disclaimer/>` footer (same component used platform-wide)

Per-page SEO: `<title>` and `<meta name="description">` set from `title` and `summary` fields;
`<link rel="canonical">` set to the production URL. Pages are fully server-rendered and do not
require JavaScript for content — crawlable by default.

## Compliance

Non-negotiable compliance checklist (inline, not deferred):

- **Education only (non-neg #1):** no advisory verbs or framing anywhere in copy, API responses, or
  frontend components. `ci_guards` scans article content.
- **No numeric score surface (non-neg #2):** G8 has no connection to the scoring engine; no
  `unified_score`, factor weight, or confidence numeric reaches the client.
- **Not-advice disclosure on every surface (non-neg #9):** every API endpoint injects the disclosure
  bundle; every page renders `<DisclosureBundle>` from the payload plus the standing `<Disclaimer/>`.
  The education module supplies its own `EDUCATION_NOT_ADVICE` line — not the `NOT_ADVICE` platform
  sentinel (which is reserved for scoring/AI surfaces) — so the two disclosures remain independently
  auditable.
- **Anonymous access:** no user data is collected or processed by G8 endpoints; DPDP consent gate
  does not apply.
- **Tier-A governance:** Builder + Architect reviews required; Compliance (Opus) inline because the
  not-advice token structure touches a load-bearing compliance invariant. Review ledger:
  `reviews/g8-tax-education.md`.

Inline Compliance (Opus) verdict: **ACCEPT-WITH-CONDITIONS** — the not\_advice-token ambiguity
(education module was emitting the platform `NOT_ADVICE` sentinel) was identified as a condition.
Fixed inline before merge: the education router now supplies `EDUCATION_NOT_ADVICE` from a module
constant, distinct from the platform token. Inline Architect (Sonnet) verdict: **ACCEPT**.

## ⚠ Deploy steps (REQUIRED before public launch)

These steps are **mandatory** — the feature is broken without them. Do not declare G8 live until
all three are complete.

1. **Run migrations then seed:**

   ```bash
   alembic upgrade head
   python -m dhanradar.education.seed
   ```

   The table is empty after migration alone — `GET /learn/tax` will return `[]` until the seed
   runs. The seed is idempotent; safe to re-run.

2. **Set `INTERNAL_API_URL` on the Next.js container:**

   ```bash
   INTERNAL_API_URL=http://dhanradar-fastapi:8000/api/v1
   ```

   Add this to the `nextjs` service environment in `docker-compose.yml` (or via the KVM4 `.env`
   override). Without it, Server-Component fetches in `app/learn/tax/` have no absolute base URL
   and will fail at render time.

3. **Human CA sign-off on tax figures:**

   A qualified tax professional must verify the FY 2025-26 figures in
   `backend/dhanradar/education/content.py` (rates, thresholds, statutory citations) before the
   pages go live. The human-CA verify list is in `reviews/g8-tax-education.md`. **Do not open
   `/learn/tax` to real users without this sign-off.**

## Known follow-ups

- **G8-f1 (security):** add `rehype-sanitize` + reject non-`http(s)` hrefs in the markdown renderer
  before any admin content-write path is introduced. Currently the seed is the only write path and
  content is under version control, so this is low-risk but must be addressed before an admin UI
  allows arbitrary markdown input.
- **G8-f2 (deploy):** the seed + `INTERNAL_API_URL` steps above are the tracked deploy blockers.
  Filed in `BLOCKERS.md`.

## Verification

`backend/tests/integration/test_education_endpoints.py` — covers: list (empty, seeded, category
filter, fy filter); single article (200 + body, 404 article\_not\_found RFC7807); calendar (key
dates present, disclosure bundle injected); every endpoint carries `not_advice` and
`disclaimer_version`. `ci_guards` article content scan. Frontend: `tsc` + `eslint` clean; SSR
render verified in CI (no `window`/`document` references in server components).

## Changelog

- 2026-06-09 — G8 built (branch `feat/g8-tax-education`): `education` schema + migration 0015;
  6-article content module (FY 2025-26) + seed command; 3 public RFC7807 endpoints
  (`/learn/tax`, `/learn/tax/{slug}`, `/learn/tax/calendar`) with disclosure injection; SSR Next.js
  pages + per-page SEO metadata + `react-markdown` rendering + `<DisclosureBundle>`; `INTERNAL_API_URL`
  SSR base wiring; `EDUCATION_NOT_ADVICE` token distinct from platform sentinel (inline Compliance
  condition fixed). Tier-A + inline Compliance (Opus) ACCEPT-WITH-CONDITIONS (condition applied) +
  Architect (Sonnet) ACCEPT. Ledger: `reviews/g8-tax-education.md`. NOT deployed (seed +
  `INTERNAL_API_URL` + CA sign-off required).
