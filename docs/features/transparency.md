# Data Transparency & Explainability — as-built

**Plan Group 9 / PU2 · Branch:** `feat/data-transparency-layer` · **Date:** 2026-06-11  
**Status:** Merge-eligible — pending Opus compliance gate (B60)

---

## What this is

The "Why / How / Based-on-what" layer for the user's own MF portfolio.
Answers four questions about every fund in a portfolio:

1. **How confident is this read?** — confidence BAND (high / medium / low / insufficient_data) + qualitative drivers.
2. **What data is it based on?** — source names + types (AMFI NAV Feed, CAMS/KARVY CAS, etc.).
3. **How fresh is that data?** — NAV as-of date + days since last update; stale flag when > 5 days old.
4. **When we won't score, we say so explicitly (PU2).** — `insufficient_data` surfaces as a deliberate honesty signal ("Not enough data to assess this fund yet — we won't guess."), never as an error or blank.

---

## Endpoint

```
GET /api/v1/portfolio/{portfolio_id}/transparency
```

- **Auth:** required (`__Host-` RS256 cookie; anonymous → 401)
- **IDOR:** ownership check via `mf_portfolios.user_id = caller`; other user's portfolio → 404
- **No migration required** — reads existing persisted tables only

### Response shape (abridged)

```json
{
  "portfolio_id": "...",
  "generated_at": "2026-06-11T...",
  "funds": [
    {
      "isin": "INF123...",
      "scheme_name": "Axis Bluechip Fund",
      "category": "Equity",
      "label": "on_track",
      "confidence_band": "medium",
      "drivers": ["Based on available history; category benchmark may be partially available"],
      "refusal": null,
      "sources": [
        { "name": "AMFI NAV Feed", "type": "nav_data" },
        { "name": "CAMS/KARVY CAS", "type": "holdings" }
      ],
      "freshness": {
        "nav_as_of": "2026-06-10",
        "nav_days_ago": 1,
        "is_stale": false,
        "holdings_as_of": "2026-06-01"
      },
      "scored_at": "2026-06-10T10:00:00+00:00",
      "model_version": "v1"
    },
    {
      "isin": "INF456...",
      "scheme_name": "New Fund XYZ",
      "confidence_band": "insufficient_data",
      "label": "insufficient_data",
      "drivers": [],
      "refusal": {
        "reason": "Not enough data to assess this fund yet \u2014 we won\u2019t guess.",
        "detail": "A minimum of 14 months of NAV history and category peer data are needed for a reliable assessment. This label will update automatically as more data becomes available."
      },
      ...
    }
  ],
  "disclosure": "Educational analysis only \u2014 not investment advice. Labels describe category-relative form, not a recommendation to buy, sell, hold, or switch.",
  "not_advice": "NOT_ADVICE",
  "disclaimer_version": "2026-06-06.v1"
}
```

---

## Data sources read (read-only)

| Table | Columns used | Purpose |
|---|---|---|
| `mf.user_fund_scores` | `isin`, `confidence_band`, `verb_label`, `scored_at`, `model_version` | Label + band + scored-at. `unified_score` never touched. |
| `mf.mf_nav_history` | `MAX(nav_date)` per isin | Freshness: "NAV data as of…" |
| `mf.mf_user_holdings` | `source`, `as_of_date` per (portfolio_id, isin) | Provenance: holdings source name |
| `mf.mf_funds` | `scheme_name`, `category` | Fund name + category |
| `mf.mf_portfolios` | `user_id` | IDOR ownership check |

---

## Driver derivation

The engine's `flags` list (`partial_coverage`/`stale`/`low_liquidity`/`provisional_model`) is **not persisted** to `user_fund_scores`. We derive equivalent qualitative drivers from what IS persisted:

| Condition | Driver text |
|---|---|
| `confidence_band = high` | "Based on 24+ months of NAV history across all signal axes" |
| `confidence_band = medium` | "Based on available history; category benchmark may be partially available" |
| `confidence_band = low` | "Limited data coverage — label may update as more history accumulates" |
| `nav_days_ago > 5` | "NAV data is N day(s) old — this label uses older price data" |

All drivers are factual data-quality statements. No directive verb, no advisory language.

---

## Frontend component

`frontend/src/components/transparency/TransparencyPanel.tsx`

Renders: confidence band badge · educational drivers · source chips · freshness row · PU2 refusal block · disclosure bundle.

Design tokens only (`--dr-*`, `--surface`, `--border`, `--text-*`). No ad-hoc colours.

**Mounted 2026-06-12** (`feat/b60-transparency-mount`) on `/portfolio/[portfolioId]/intelligence`,
last in the section stack (meta-information after the analysis sections):

- `frontend/src/features/transparency/api.ts` — `usePortfolioTransparency(portfolioId)`
  (TanStack Query; key from `queryKeys.portfolio.transparency`; same retry/staleTime contract as
  the changes hook).
- `frontend/src/features/transparency/TransparencySection.tsx` — fetch wrapper mirroring
  `WhatChangedSection`: shell renders in ALL non-data states with the panel's surface tokens +
  the same h2, so geometry and heading level never jump across fetch states. Shell heading
  margin is 16px (not the panel's subtitle-tight 4px — UI review condition). The wrapper adds
  no disclosure copy of its own; the panel owns the compliance surface.

---

## Compliance invariants enforced

| # | Invariant | How enforced |
|---|---|---|
| non-neg #2 | No numeric score in DOM | `unified_score` absent from schema; never SELECTed; Pydantic allowlist model; integration test assertion |
| non-neg #1 | No advisory verbs | All driver/refusal copy reviewed; advisory verb test lists cover full SEBI set (buy/sell/hold/switch/invest/redeem/avoid/consider/suggest); ci_guards clean |
| non-neg #9 | Disclosure bundle on every response | Required fields on `PortfolioTransparencyResponse`; populated unconditionally; FE test asserts presence |
| PU2 | insufficient_data as honesty signal | `refusal` field non-null for insufficient_data; `role="note"` (not alert); neutral tokens; 200 status; integration test |
| IDOR | User sees only own portfolios | `mf_portfolios.user_id == requesting_user_id` check before any score read; test_wrong_user_404 |

---

## Tests

| Test | What it covers |
|---|---|
| `test_transparency_happy_path` | 200, all fields present, disclosure bundle, no unified_score |
| `test_transparency_insufficient_data_refusal` | refusal block non-null, educational framing, full SEBI advisory verb check |
| `test_transparency_wrong_user_404` | IDOR guard |
| `test_transparency_no_numeric_leak` | unified_score, raw float, integer forms absent |
| `test_transparency_freshness_stale` | 7-day-old NAV → is_stale=True, nav_days_ago=7 |
| `test_transparency_anonymous_401` | auth guard |
| `TransparencyPanel.test.tsx` (14 vitest) | confidence band, sources, freshness, refusal, no numeric, stale, multi-fund, advisory verb ban |

---

## Lane isolation

Locked lanes (not edited): `scoring/engine/*`, `mf/signals.py`, `mf/scoring_bridge.py`,
`mf/service.py`, `tasks/*`, `news/*`, `insights/*`.

Disclosure constants imported read-only from `scoring/engine/schemas.py` (B56-f1: no third copy;
defer move to shared module, coordinate with scoring-engine lane).

---

## Independent reviewer findings (2026-06-11)

All actioned before final commit:

- **B2** (highest): "freshness check recommended" — "recommended" is a passive form of a SEBI advisory verb. Fixed to "this label uses older price data" (purely factual, no directive).
- **B1**: frontend advisory verb test comment mismatch — fixed with explanation of why compound phrases are tested (disclosure text negation context).
- **B3**: advisory verb test lists expanded to full SEBI set.
- **A1/A2**: no-numeric-leak assertions strengthened.
- **D**: late-import rationale comment added in service.py.

Remaining for Opus review: none blocking; one coverage gap (empty-portfolio test case) filed as B60 follow-up.

---

## Governance

**Tier:** A (read-only, non-scoring logic) + **inline Compliance** (confidence band + explainability copy is advice-adjacent).  
**Independent reviewer:** PASS (post-fixes).  
**Opus compliance gate:** REQUIRED before merge. Do NOT self-merge.  
**Deploy:** human-gated; no migration required.

---

## Open follow-ups (B60)

- Add integration test: portfolio-with-no-scores → 200 empty funds list.
- B56-f1 coordination: when disclosure constants move to shared module, transparency will be an additional consumer (update imports).
- B56-f3: composite index `(user_id, isin, scored_at DESC)` on `user_fund_scores` — latent perf; benefits transparency queries when load grows.
