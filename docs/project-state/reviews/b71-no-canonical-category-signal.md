# Review ledger — B71: uncohorted-fund context signal (+ B58-f5 feature-doc note)

Change-id: `b71-no-canonical-category-signal` · Branch: `feat/b66f1-pt2-activation-prereqs`
Tier: **C** (scoring-engine signal vocabulary) · Date: 2026-06-14

## What changed

Pre-activation prerequisites for the (separately-gated) B66-f1 pt2 `sebi_category` cohort
grouping. **No behavioural change under the active `category` grouping key** (verified: 0 of
14,041 prod funds have a NULL/blank/`uncategorized` raw category) — the new path only fires for
the ~4,876 legacy-umbrella funds once `sebi_category` grouping is activated.

- **B71 — `COHORT_NO_CANONICAL_CATEGORY` signal.** New `SignalName` + compliance-approved phrase in
  `scoring/engine/signal_names.py`. A fund with no canonical SEBI peer category (pre-2017 legacy
  umbrella → `sebi_category` NULL, or unclassified raw category) is now KNOWN-uncohorted: instead of
  a silent `on_track` with an empty context pane, it publishes `on_track` carrying the new context
  string. Cures the prior Compliance C1 / Product P1 finding (uncohorted funds over-reassured).
  - Emission seam: `_CohortContext.uncategorized_isins` (new field); `_build_cohort_context`
    computes it (and surfaces it even in the all-uncategorized empty-cohort early return);
    `_relative_from_context` emits the signal for those targets. Funds are NEVER auto-mapped into an
    unrelated cohort; `nav_points < _MIN_POINTS` funds still resolve to `insufficient_data` first.
- **B58-f5 — feature-doc note** in `docs/features/rating-scoring-engine.md`: cohort-relative label
  sensitivity (a label can change when the peer set is recalibrated, not only when the fund moves;
  the durable mechanism for a one-off recalibration is a one-time pre-rescore user notice, not
  per-fund alarm copy) + the uncohorted-funds explainer.

## Approved phrase (byte-pinned in `test_signal_names.py`)

> category peer benchmark unavailable — fund not mapped to a SEBI peer category; no peer comparison
> made

## Deterministic gates (all green)

- pytest: 944 unit passed + 1 xfailed; `test_mf_cohort.py` + `test_signal_names.py` 61 passed
  (2 new cohort tests: NULL-target context + all-uncategorized; 1 new byte-pin).
- ruff clean on changed files; ci_guards exit 0 (no non-negotiable violations; secrets clean).

## Review — Compliance (independent Sonnet agent) — VERDICT: ACCEPT-WITH-CONDITIONS

- Phrase within the SEBI educational boundary: factual, non-advisory, no numeric, no advisory verb,
  parallel-in-voice to `COHORT_THIN_BENCHMARK`. PASS.
- Emission correctness: no auto-mapping (SQL `IN` excludes NULL + `if c` filter); `insufficient_data`
  correctly takes precedence for thin-history funds; no numeric leak (`contributing` is `list[str]`).
  PASS.
- Disclosure-neutral: adds explanatory context, does not change any label's meaning → no
  `DISCLAIMER_VERSION` bump warranted. PASS.
- **C1 (recommended):** make the absence of assessment explicit. **APPLIED** — phrase now ends
  "; no peer comparison made" (phrase + byte-pin + feature-doc quote updated in lockstep).
- **C2 (blocking gate):** byte-pin test must be green. **DONE** — `test_cohort_no_canonical_category`
  added and matches the final bytes.

## Eligibility

**MERGE-ELIGIBLE.** Dormant under the active grouping key; deterministic gates green; the new
user-facing copy passed its Tier-C compliance review with both conditions resolved. This is a
prerequisite for — not itself — the B66-f1 pt2 `sebi_category` activation (which remains gated on the
two-person methodology gate + founder approval; see `reviews/b66f1-pt2-cohort-sebi-rewire.md`).
