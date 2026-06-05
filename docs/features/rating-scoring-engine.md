# Feature — Rating / Scoring Engine v1

**Status:** engine built (deterministic collapse, label rule-table, confidence, hysteresis, governance, internal read API); numeric weights remain PROPOSED v1 (not activated) pending backtest pass-gates + the two-person gate (B6)     **Phase:** Phase 4 (architecture §S)
**Last updated:** 2026-06-06

## Purpose & scope

The IP core. A standalone, deterministic engine that turns instrument factors into `{unified_score, confidence_band, verb_label, valid_until, eval_seq}` with all SEBI-boundary invariants enforced structurally. Domain modules couple ONLY via events + the internal read endpoint — never by importing engine internals.

## Non-goals

- No user input — there is deliberately **no `risk_profile` / user field** in `FactorInputs` (non-neg #3; test-enforced). The risk profile drives suitability/education elsewhere, never the score.
- No public numeric — the engine returns the numeric server-side (tier-gated); the public projection is band + label only (non-neg #2).
- No advisory output — labels describe category-relative form, never buy/sell/hold/switch (non-neg #1).
- Does not own the input pipeline (Market Data Adapter / MF module provide `FactorInputs`); does not persist `scores` rows (caller/Phase 5).

## Public interface

- `await RatingEngine.score(FactorInputs) -> ScoringResult`.
- Inputs: `FactorInputs` (per-axis `SubFactor`s + `LabelSignals` + freshness/coverage provenance). `Axis` = quality/valuation/momentum/trend/risk.
- Outputs: `ScoringResult` (internal: `unified_score` 0–100, `confidence` 0–1 — tier-gated) → `to_public()` → `PublicScore` (label + `confidence_band` + signals + disclosure, **no numeric**).
- Events: `scoring.result.published` carries the `PublicScore`. Internal read: `GET /internal/v1/score/{instrument_type}/{identifier}` (server-to-server; not reachable via the public `^/api/.*` ingress).
- Governance: `review_batch`, `make_changelog_entry`, `two_person_gate_ok`.

## Pipeline / behaviour (spec §3–§7)

1. **Axes** — per-axis weighted mean; missing sub-factors dropped + remaining weights renormalized (never imputed).
2. **Composite** — weighted over present axes (reweighted proportionally); a dropped axis sets `partial_coverage`. Weights from `ranking_configs_v1.json` (sum 1.0 ± 0.001, validated at load; no sub-factor in two axes).
3. **Confidence** — `0.30·freshness + 0.25·coverage + 0.20·factor_agreement + 0.15·retrieval_relevance + 0.10·model_signal`; structural caps: partial_coverage→medium, illiquid→low, stale→×0.9, high-confidence guard (>0.70 needs ≥3 contributing + reliable sources).
4. **Floor** — confidence < 0.30 ⇒ `insufficient_data`: REFUSE (no label, **no numeric** exposed).
5. **Label** — from the deterministic **rule table** on `LabelSignals` (category-relative facts), **not** the score. Score-band leaning is only a logged cross-check (rule wins on disagreement).
6. **Hysteresis** — a label flip publishes only after **2 consecutive evals** at the new label; `eval_seq` exposed for alert gating. Refusals publish immediately.
7. **Governance** — batch churn > 5% ⇒ held `pending_publish` for Compliance (fail-closed); label-distribution bound (no single label > 80%); methodology change writes a changelog entry + requires the two-person gate (`approved_by ≠ created_by`, enforced at activation — B6).

## Dependencies

Redis (hysteresis eval state + internal result cache). Reads `ranking_configs_v1.json`. No imports from auth/billing/market_data/ai_gateway (engine is standalone; non-neg #7). Pure-python normalization (no numpy needed).

## Verification

`backend/tests/unit/test_scoring_engine.py` — 17 tests: golden-set score+label; **label ≠ pure score function** (same 60 score → in_form vs out_of_form); confidence floor → insufficient_data + no numeric; 2-eval hysteresis flip suppression; partial-coverage→medium cap; churn>5%→hold + distribution-collapse→hold; `risk_profile`/`user` absent from inputs; PublicScore has no numeric; two-person gate; config weight-sum + double-count validators; publish emits PublicScore + caches the full internal result. Full unit suite 129 pass; ci_guards green.

## Known limitations / deferred

- Numeric axis weights are **PROPOSED v1** — not activated until backtest pass-gates + two-person gate (B6); `activated:false` in config.
- Band-edge ±2 buffer (smoothing) is documented but the eval-count hysteresis is the active flip gate; band-edge dead-zone is a v1.1 refinement.
- Upstream normalization (winsorize/z-score against the sector peer set) helpers are provided, but the peer-set data pipeline lands with the consuming modules (Phase 5+).
- The internal read endpoint returns the cached published result; persistence to a `scores`/`user_fund_scores` table is the caller's job (Phase 5).

## Changelog

- 2026-06-06 — Engine v1 built (Phase 4 §S): deterministic collapse, rule-table labels (not score), confidence model + floor, 2-eval hysteresis, governance (churn/distribution/two-person/changelog), internal read API. 17 unit tests. Built on Opus (Tier-C). Governance fan-out pending.
