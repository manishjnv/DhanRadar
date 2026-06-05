"""
DhanRadar — Scoring package.

This package currently holds ONLY declarative scoring configuration
(`ranking_configs_v1.json`) and its changelog. The rating/scoring ENGINE that
consumes this config is an Implementation-Plan Phase-4 deliverable and is NOT
built here (Stage 2 Step 8 stages the config only).

The v1 config is the `FINAL_SCORING_SPEC.md` §3 proposal. It is **unactivated**:
numeric weights remain PROPOSED until they clear the backtest pass-gates (§8)
and the two-person methodology gate (approved_by ≠ created_by, BLOCKERS B6).
Nothing in this package executes scoring or mutates data.
"""
