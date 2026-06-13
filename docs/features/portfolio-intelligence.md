# Feature — Portfolio Intelligence (Insights)

**Status:** partial (overlap + concentration built; mood-context built 2026-06-13)
**Phase:** Phase 5 follow-on (B59 overlap + concentration) and PU1 (mood-context)
**Last updated:** 2026-06-13

## Purpose & scope

Provides three read-only insight surfaces on a user's MF portfolio: pairwise fund
overlap, category concentration observation, and market-mood context. All surfaces are
educational observations only — no advice, no numeric scores in the DOM.

## Non-goals

- No buy/sell/hold/caution advisory verbs anywhere on these surfaces.
- No numeric percentages, factor weights, or scores serialized to the client
  (non-negotiable #2).
- No LLM involvement in any current surface.
- No risk-profile input to observations.
- No direction prediction from mood regime.

## Public interface (the only coupling surface)

**Overlap** (`GET /api/v1/insights/{portfolio_id}/overlap`) returns pairwise Jaccard
overlap band descriptors and a disclosure bundle for the user's funds. Auth: 401
anonymous, 404 IDOR. Raw overlap percentages drive backend logic only and are never
serialized.

**Concentration** (`GET /api/v1/insights/{portfolio_id}/concentration`) returns a single
observation text line and disclosure bundle derived from category allocation. Auth: 401
anonymous, 404 IDOR. The underlying percentage drives logic but is not serialized
(non-neg #2).

**Mood Context** (`GET /api/v1/portfolio/{id}/mood-context`) returns:

```json
{
  "mood_regime": "...",
  "concentration_band": "...",
  "observations": ["<regime>", "<independence-disclaimer>", "<structure>"],
  "disclosure": "...",
  "not_advice": true
}
```

Auth: 401 anonymous, 404 IDOR. No numeric in response. Cold-start or empty portfolio
returns a valid 200 with `concentration_band: "empty"`.

## Data

No new tables. Reads `market_mood` exclusively via `mood.service` public functions.
Reads portfolio and holdings via the existing insights service. No new Redis keys.

## Pipeline / behaviour

Mood Context endpoint (`insights/service.py`):

1. Auth gate — anonymous returns 401; IDOR returns 404.
2. Read current mood via `mood.service.get_latest()` (public function only; no direct
   SQL on `market_mood`). If no snapshot exists, `mood.service.unavailable_public()`
   returns a sentinel and observations reflect the unavailable state.
3. Derive concentration band via `_concentration_band()` using ADR-0032 thresholds:
   0 funds maps to `empty`; 1 fund or top category at or above 70% maps to `high`;
   top category 40–69% maps to `moderate`; top category below 40% with 2 or more
   funds maps to `low`. The underlying percentage is never serialized (non-neg #2).
4. Build exactly 3 deterministic templated observations via `_build_observations()` in
   fixed order: index 0 — regime observation; index 1 — independence disclaimer
   (mandatory per Compliance F2 and ADR-0032, prevents direct adjacency of mood regime
   with portfolio structure); index 2 — structure observation.
5. Attach disclosure bundle and `not_advice: true`. Return 200.

Overlap and concentration endpoints follow the same auth pattern (401/404) and apply
the same no-numeric rule; their internal pipelines derive descriptors from holdings
data already held in the insights service.

## Config & flags

No new environment variables. No feature flags.

## Failure modes & fallbacks

| Condition | Behaviour |
|---|---|
| Mood snapshot unavailable | Valid 200; observations describe unavailable state |
| Empty portfolio (0 funds) | Valid 200; `concentration_band: "empty"` |
| Anonymous request | 401 |
| IDOR (other user's portfolio) | 404 |

## Dependencies

- `mood.service` public functions (`get_latest`, `unavailable_public`) — interface-only
  coupling; no direct SQL on `market_mood` permitted from insights code (non-neg #7).
- Portfolio and holdings data via existing insights service logic.
- No AI gateway.
- No cross-border consent gate (mood data is not user-PII).

Frontend: `features/insights/` (api.ts, types.ts, MoodContextSection.tsx). queryKeys
factory entry. Mounted second on `/portfolio/[id]/intelligence` — after WhatChanged,
before Overlap. RegimeChip component includes unknown-regime fallback.

## Verification

- `pytest tests/unit/test_mood_context_service.py` — band thresholds (ADR-0032),
  observation ordering, mood-unavailable path, empty-portfolio path.
- `vitest frontend/src/features/insights/__tests__/MoodContextSection.test.tsx` —
  render, unknown-regime fallback, disclosure rendered.
- 817 backend unit tests pass, 20 vitest pass, tsc clean, ruff clean, ci_guards clean.
- Governance ledger: `docs/project-state/reviews/pu1-mood-portfolio-context.md`.

## Changelog

- 2026-06-13 — PU1: Market Mood Context endpoint and MoodContextSection frontend
  component built. ADR-0032 (concentration-band taxonomy) added. Tier-A plus Compliance
  ACCEPT-WITH-CONDITIONS (F1: ADR-0032 added; F2: observation reorder applied). Ledger:
  `docs/project-state/reviews/pu1-mood-portfolio-context.md`.
