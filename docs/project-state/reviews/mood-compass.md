# Review — Mood Compass module (twice-daily market regime + commentary)

## Gate ledger

**Tier:** C (a regime score + AI-commentary public surface; recommendation-adjacent
educational output). · **Class:** major · **Base:** `main` (post #16, `b6fa252`) ·
**Date:** 2026-06-06.

| Gate | Required by tier | Verdict | Reviewer |
|---|---|---|---|
| Deterministic (ci_guards + anti-pattern sweep + unit pytest + F-lint + compile) | always | PASS (246 unit; 22 mood unit + 6 integ) | machine |
| Architect | always | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |
| Compliance | tier C | ACCEPT-WITH-CONDITIONS | Opus (independent of builder) |
| Product | tier C | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |

**Final status:** ACCEPT-WITH-CONDITIONS — the one compliance MAJOR + the compute
bug fixed in-branch; product launch-gaps tracked (B35). Merge-eligible; not
deploy-eligible (the public feature needs real signals + the embed widget — B35).

## MAJOR / correctness — fixed this turn (in-branch)

- **[Compliance MAJOR] sub-0.30 confidence published a confident regime** — the band
  degraded to `insufficient_data` but the REGIME stayed a directional bucket (e.g.
  `extreme_greed`) and was served + audited + broadcast. Now `compute_mood` coerces the
  served `regime` to **`insufficient_data`** when confidence < 0.30 (non-neg #4, mirroring
  the rating engine's refuse floor). The 0–100 stays server-side. Unit-tested.
- **[Product/correctness] bucket gap on non-integer scores** — the buckets used inclusive
  integer ranges `[0–19],[20–39],…`, so a score of 19.5/39.9/etc. fell through to
  `neutral`. Reimplemented with contiguous half-open bounds — no gaps. Unit-tested at the
  boundaries.
- **[Compliance MINOR] commentary advisory screen** — the free-text AI `commentary` is now
  run through a core advisory-verb screen before publish; any commentary carrying
  buy/sell/hold/switch/avoid/caution is withheld (non-neg #1; B23 owns the full taxonomy).
  Commentary is None until AI prompts are wired, so this is latent defense-in-depth.
- **[Architect] migration downgrade** — `DROP SCHEMA mood CASCADE` so a future `mood_history`
  object can't block a clean rollback.

## Confirmed-sound (no change)

- **No-numeric public surface (Compliance #1):** `MoodPublic`/`WhyToday`/`mood:latest`/the
  public card carry the `regime` bucket + `confidence_band` words only — the `mood_score`
  (0–100) and `confidence_score` float stay server-side (`market_mood` columns). Compliance
  **confirmed this is the correct call** and a Fear&Greed-style public number would be a
  BLOCKER (non-neg #2 is absolute). Test asserts no numeric keys in the JSON.
- **Disclosure on every surface (#9):** bundle + NOT_ADVICE + `disclaimer_version` are
  required (non-Optional) on every public schema + the cached payload + the card text.
- **B26 audit (mood):** the served regime persists to `ai_recommendation_audit`
  (`surface="mood"`, `recommendation_type="mood_regime"` — allowlisted at service + DB CHECK),
  fire-and-forget. Test asserts the row.
- **DPDP (#10):** the public card + mood surfaces carry only MARKET data — no user PII — so
  no consent/cross-border gate is owed (unlike the per-user notification seam B31).
- **Module isolation:** mood owns the `mood` schema; calls Compliance + Notification via
  interface (`record_served_label`, `post_public_card`); the regime is NOT a ranking input.

## Conditions carried forward (B35 — Mood go-live; product launch gaps)

- **Real signals:** the Market Data Adapter providers are stubbed → all 11 inputs missing →
  the snapshot is skipped → `GET /market/mood` 404s. The feature is inert until real signals
  wire in (B29-class).
- **Friendly empty-state:** prefer a structured 200 `data_unavailable` over a 404 for the
  anon magnet (API + the future Mood UI).
- **Factor display labels:** the evidence lists carry raw keys (`put_call_ratio`); map to
  human labels (server-side or in the Mood UI) so the disagreement disclosure is legible.
- **`/market/mood/embed` creator widget** — not built (the primary distribution surface).
- **Structured `mood.snapshot.published` event** `{snapshot_date, mood_score, regime,
  confidence_score}` for the future AI-Enrichment analogue consumer — currently emission is
  the public card + audit only (no event bus / consumer yet).
- **`mood_history` (pgvector)** + the AI commentary (real prompts via the Admin/AI-Enrichment
  module) are deferred.
- **Isolation cleanup (low):** the disclosure constants are imported from
  `scoring.engine.schemas` (a public schema module, same as the MF module does); a shared
  `compliance.constants` home is a cross-cutting cleanup, tracked not done.
