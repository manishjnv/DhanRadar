# Gate ledger — pu1-mood-portfolio-context

**Change:** New educational "Market Mood Context" surface. Backend adds
`GET /api/v1/portfolio/{id}/mood-context` in the insights module. Auth: 401 for
anonymous, 404 for IDOR (other user's portfolio). Returns a disclosure bundle per
RFC7807. Reads current mood via `mood.service` public functions (`get_latest` /
`unavailable_public`) — no raw mood SQL. Derives a descriptive concentration band
governed by ADR-0032: empty/high/moderate/low thresholds based on fund count and
top-category allocation percentage. Emits exactly 3 deterministic templated
observations (no LLM, no advisory verbs, no direction prediction) ordered
[regime, independence-disclaimer, structure] so the disclaimer interrupts the
mood-to-structure pairing (Compliance finding F2). No numeric reaches the DOM.
Cold-start and empty portfolio return a valid 200. Frontend adds
`features/insights/` (api.ts, types.ts, MoodContextSection.tsx) with a queryKeys
factory entry. Mounted second on `/portfolio/[id]/intelligence` (after WhatChanged,
before Overlap). RegimeChip component carries a safe fallback for unknown regimes.

**Branch:** `feat/pu1-mood-portfolio-context` — PR #\<pending\>

**Classification:** Tier A (new feature, portfolio intelligence page) with Compliance
review required (educational surface with mood/label content). Required reviews:
Builder + Architect + Compliance + UI.

## Deterministic gates

| Gate | Result |
|---|---|
| Backend unit tests (817) | PASS |
| Frontend vitest (20) | PASS |
| tsc | PASS — clean |
| ruff | PASS — clean |
| ci_guards / anti-pattern grep | PASS |
| Alembic migrations job | PASS (no new migrations) |

Note on ci_guards: the FE advisory-guard-list in the test was initially collapsed to
a single space-separated string, causing the deterministic scan to read it as shipped
advisory copy rather than a banned-verb list. Fixed so the banned-verb list is a
proper array, not a scan target. The gate is green against the corrected fixture.

## Verdicts (independent agents; builder not reviewer)

| Review | Agent | Verdict |
|---|---|---|
| Builder | Sonnet subagent (feat/pu1-mood-portfolio-context) | — |
| Architect + Compliance + UI (Tier A + Compliance) | Sonnet subagent (orchestrator = Fable, 2026-06-13) | ACCEPT-WITH-CONDITIONS |

## Independent review — evidence

Verification performed by the independent Sonnet subagent against the live source
(three-dot merge-base diff `origin/main...feat/pu1-mood-portfolio-context`):

1. F1 (MAJOR — applied): ADR-0032 was missing. The concentration-band taxonomy
   (empty/high/moderate/low thresholds derived from fund count and top-category
   allocation percentage) had no architectural decision record. Added as ADR-0032
   in `docs/project-state/ARCHITECTURE_DECISIONS.md` before the ledger was closed.

2. F2 (MAJOR — applied): The 3 observations were originally ordered [regime,
   structure, independence-disclaimer]. Reordered to [regime,
   independence-disclaimer, structure] so the disclaimer sits between the mood read
   and the structure read, preventing direct juxtaposition of mood regime with
   portfolio structure without an intervening "not a signal to act" line.

3. F3 (NIT — already covered): Reviewer queried whether the `unavailable_public`
   seam (mood snapshot absent) was exercised. Confirmed covered by existing test
   `test_mood_context_mood_unavailable`; no new test required.

4. F4 (NIT — non-issue): Reviewer raised whether `DisclosureBundle` carries
   `disclaimer_version` and whether the frontend renders it directly.
   `MoodContextSection.tsx` takes only `disclosure` and `notAdvice` props; the
   component does not render `disclaimer_version` directly, consistent with how
   `<Disclaimer/>` is used elsewhere. No change required.

5. F5 (NIT — accepted): RegimeChip fallback label for unknown regimes uses the
   string `"Unknown"`. Accepted as a safe defensive default. Not a compliance risk;
   the string carries no advisory implication.

## Advisory-boundary verdict

HOLDS. The disclaimer reorder (F2) closes the juxtaposition risk identified by the
Compliance dimension. All 3 observations are templated, deterministic, and contain
no direction prediction or advisory verb. The ci_guards advisory-verb scan is green
against the corrected array fixture.

Cross-reference: ADR-0032 (`docs/project-state/ARCHITECTURE_DECISIONS.md`).

## Conditions applied before merge

1. F1 — ADR-0032 added to `docs/project-state/ARCHITECTURE_DECISIONS.md` recording
   the concentration-band taxonomy and thresholds.
2. F2 — Observation order in the endpoint response changed from [regime, structure,
   independence-disclaimer] to [regime, independence-disclaimer, structure].

Both conditions applied; no open BLOCKERs or MAJORs remain.

## Accepted residuals

1. F3 — `unavailable_public` coverage confirmed by existing test; no action.
2. F4 — `disclaimer_version` not rendered by `MoodContextSection.tsx`; consistent
   with project convention; no action.
3. F5 — `"Unknown"` fallback in RegimeChip accepted as a safe defensive default.

**Merge-eligible** — all deterministic gates green; Architect + Compliance + UI
ACCEPT-WITH-CONDITIONS with both conditions applied and all residuals accepted.

## Deploy record

Pending — human-gated; not yet deployed to KVM4.
