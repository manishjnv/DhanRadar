# Review — stage2-step8-ranking-configs (post-merge)

## Gate ledger

**Tier:** C (scoring / recommendation logic) · **Class:** major · **Artifact:**
`backend/dhanradar/scoring/ranking_configs_v1.json` + `RATING_ENGINE_CHANGELOG.md` ·
**Diff:** merged in `9368628` (PR #3) — reviewed post-merge · **Date:** 2026-06-05.

| Gate | Required by tier | Verdict | Reviewer/tier |
|---|---|---|---|
| Deterministic (weight-sum check; CI guards) | always | PASS | machine + orchestrator |
| Architect | always | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |
| Compliance | tier C | ACCEPT-WITH-CONDITIONS | Opus (independent) |
| Product | tier C | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |

**Final status:** ACCEPT-WITH-CONDITIONS. The config faithfully encodes `FINAL_SCORING_SPEC` and is
correctly **staged-not-activated** (`activated:false`, `approved_by:null`) — the two-person
methodology gate (B6) and backtest pass-gates remain pending before any production activation.

## Findings

- **Compliance (Opus): CLEAN on every non-negotiable.** Labels exact
  (`in_form/on_track/off_track/out_of_form/insufficient_data`); advisory verbs only in
  `advisory_verbs_rejected`; composite weights 0.24+0.22+0.20+0.22+0.12 = 1.00 (±0.001);
  `no_numeric_in_dom:true`; `risk_profile_excluded_from_score:true`; label `primary` = deterministic
  rule table (not a pure score function); confidence floor 0.30 → `insufficient_data` + band-only
  exposure gate; `activated:false` + `approved_by:null`. Changelog records the v1 entry + the
  pending two-person/backtest gates.
- [MAJOR→fixed-as-note] Risk sub-factor coverage mismatch: `axes.risk` lists 7 sub-factors
  (incl. `concentration`) per `FINAL_SCORING_SPEC` §2.5, but `risk_factor_formula.weights` weights
  only 6 (§6.1 omits `concentration`). This is a **latent inconsistency in the spec itself**
  (§2.5 vs §6.1), faithfully reproduced in the config. **Action:** added a `_concentration_note` to
  the config documenting that `concentration` is unweighted in v1 pending a weight at the backtest
  gate; flagged the §2.5/§6.1 inconsistency to the architecture owner. → BLOCKERS B11.
- [PASS] Product: edge-cases (insufficient data, partial coverage, stale, reweight), benchmarks,
  recompute cadence all specified; no engine logic leaked into the config.

## Orchestrator note

`concentration`'s weight is a scoring-methodology decision (PROPOSED v1, governed by the backtest +
two-person gate) — deliberately NOT assigned here. The spec §2.5/§6.1 reconciliation is owed to the
architecture owner before v1 activation.
