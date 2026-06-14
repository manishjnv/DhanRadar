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

## Activation gate (B6/B28)

Runtime activation is triggered by `POST /api/v1/admin/scoring/{model_version}/activate`
(`RequireAdmin()` — surface-hiding 404 for non-admins). The gate (`scoring/engine/activation.py:
assert_activatable`) enforces fail-early: (1) `backtest_passed` must be true (§8 backtest
pass-gates, operator-asserted) else 422 `backtest_not_passed`; (2) `approved_by ≠ created_by`
two-person gate (reuses `governance.two_person_gate_ok`) else 409 `two_person_gate_failed`.
`created_by` is the authoring ROLE from `ranking_configs_v1.json` (`"architecture-review"`);
`approved_by` is the activating admin's UUID. `EngineConfig.validate()` rejects a UUID-shaped
`created_by` to prevent deceptive gate satisfaction.

On success, one row is written to `compliance.rating_engine_changelog` (`activated=true`) via
`compliance.service.record_engine_changelog` (interface-only coupling; scoring never imports the
compliance ORM model). The registry row is the **authoritative activation state**; a
`uq_engine_changelog_activated_per_version` partial-unique index (migration 0009) is the
multi-worker race-safe backstop against double-activation.

The engine's synchronous `score()` path is unchanged — it reads the JSON `cfg.activated` file flag
as a "no DB session" fallback. Surfaces with a DB session call `activation.is_activated(db,
model_version)` (positive-memoized; activation is monotonic). `GET /api/v1/admin/scoring/{version}/
status` reports `file_activated`, `registry_activated`, `effective_activated` (file OR registry),
and `provisional` (`NOT registry_activated` — the registry gate governs provisional determination).

**v1 stays provisional.** No backtest has been run; v1 is not activated. Actual v1 activation
requires real §8 backtest pass-gates (human/data) and a human approver admin (approved_by ≠
authoring role). The mechanism is built and ready.

Ledger: `docs/project-state/reviews/b6-b28-scoring-activation.md`.

## Known limitations / deferred (tracked in BLOCKERS)

- **B28/B6** — weights are **PROPOSED v1** (`activated:false`); every result is tagged
  `provisional_model`. Full activation (backtest pass-gates + calibration + two-person gate) before
  any numeric is treated as authoritative. The activation **mechanism** is built (2026-06-07) — see
  Activation gate section above. What remains is the data/human gate: real §8 backtest pass + human
  approver admin action.
- **B24** — label precedence: `manager_change`/`structural_concern` veto `in_form` even over
  1Y+3Y outperformance (fail-safe caution veto, documented); a recency window is a spec/architecture-
  owner decision.
- **B25** — `/internal/v1/score` numeric endpoint: fail-closed `X-Internal-Token` guard + network
  topology; full network/mTLS policy is a deploy gate.
- **B26** — `disclaimer_version` carried on results; persisting `ai_recommendation_audit`
  `(label, model_used, disclaimer_version)` at serve time is the caller's job.
- **B27** — RESOLVED 2026-06-13. Canonical signal-name registry shipped; see section below.
- Band-edge ±2 buffer (smoothing) is documented but the eval-count hysteresis is the active
  flip gate; the score-band-edge dead-zone remains an open refinement. (Distinct from the
  COHORT margin band, which became category-class-aware in model v1.1 — B58-f4, ADR-0030.)
- Upstream normalization (winsorize/z-score against the sector peer set) helpers are provided, but the peer-set data pipeline lands with the consuming modules (Phase 5+).
- The internal read endpoint returns the cached published result; persistence to a `scores`/`user_fund_scores` table is the caller's job (Phase 5).

## Canonical signal-name registry (B27)

All contributing and contradicting signal phrases are now centralised in
`backend/dhanradar/scoring/engine/signal_names.py`. The module defines `SignalName`
(a `StrEnum` with 9 keys), `SIGNAL_DISPLAY` (a dict mapping each key to its
compliance-approved display phrase), `CANONICAL_SIGNAL_PHRASES` (a `frozenset` of
the 9 approved phrases used as a compliance reference), and a
`display(name: SignalName) -> str` helper.

All 9 signal producers have been rewired to call `display(SignalName.X)` — 7 in
`mf/cohort.py` and 2 in `mf/signals.py`. Phrases are byte-identical to the prior
inline literals. The public API (`list[str]` on `ScoringResult`), labels, numeric
scores, and confidence bands are unchanged. No migration is required.

Rules governing this registry:

- All contributing/contradicting string values must be produced via
  `display(SignalName.X)`. Inline string literals for signal phrases are prohibited.
- Adding a new phrase requires a new `SignalName` key and `SIGNAL_DISPLAY` entry.
  This is a Tier-C change because it touches the scoring engine module.
- `CANONICAL_SIGNAL_PHRASES` is the compliance-approved reference set. Runtime
  enforcement at call sites is a planned follow-on item.
- LLM commentary signals live in a separate field on `ScoringResult` and are never
  governed by this registry.

Ledger: `docs/project-state/reviews/b27-canonical-signal-names.md`.

## Cohort-relative label sensitivity & uncohorted funds (B58-f5 / B71)

The label is **category-relative**: a fund is judged against the median of its same-category
peers. A consequence is that **a fund's label can change without the fund itself changing** — when
the peer set is recalibrated (e.g. the B66 taxonomy correction that moves mis-tagged funds into
their correct cohort), the cohort median shifts and some funds cross the margin band. This is
correct behaviour (a more complete cohort is a more honest benchmark), not a fund-performance
event. Any user-facing surface reporting a label change should frame a recalibration-driven move as
"your peer group was updated", not "your fund got worse"; the durable mechanism for a one-off
recalibration (e.g. a grouping-key activation) is a **one-time pre-rescore user notice**, not
per-fund alarm copy.

**Uncohorted funds (B71).** A fund with no canonical SEBI peer category — a pre-2017 legacy umbrella
(`sebi_category` NULL) or an unclassified raw category — is **honestly uncohorted**: it is never
auto-mapped into an unrelated cohort, and it publishes `on_track` carrying the
`COHORT_NO_CANONICAL_CATEGORY` context ("category peer benchmark unavailable — fund not mapped to a
SEBI peer category; no peer comparison made"). This distinguishes "no peer comparison was made" from a genuine "matching
category" on_track, so the label reads honest-not-positive. Benchmark quality therefore depends on
AMFI category-taxonomy consistency (the B66 validation layer).

## Changelog

- 2026-06-14 — B71 + B58-f5: uncohorted funds (no canonical SEBI category) now carry the
  `COHORT_NO_CANONICAL_CATEGORY` context (honest-not-positive `on_track`); feature-doc note on
  cohort-recalibration label sensitivity. Dormant-safe under the active `category` grouping key (no
  prod fund lacks a raw category); pre-activation prerequisites for the B66-f1 pt2 `sebi_category`
  grouping activation.

- 2026-06-13 — B27: canonical signal-name registry shipped (`scoring/engine/signal_names.py`);
  9 approved phrases single-sourced + byte-pinned; all producers rewired; public API unchanged;
  Tier-C ACCEPT. Ledger: `reviews/b27-canonical-signal-names.md`.
- 2026-06-12 — B58-f4: category-class-aware cohort label band shipped as model v1.1 —
  Debt Scheme 0.5pp / Hybrid Scheme 1.0pp / default 2.0pp; AMFI class prefix before ` - `;
  unknown class → default wider band (fail-safe); manifest in `ranking_configs_v1.json`
  `labels.cohort_margin_pct` (lockstep test-enforced); ADR-0030; registry row at deploy.
- 2026-06-07 — B6/B28 activation gate built: admin endpoint `POST /api/v1/admin/scoring/{version}/activate`
  (`RequireAdmin()`); `assert_activatable` enforces backtest_passed + two-person gate fail-early;
  `compliance.rating_engine_changelog` is the authoritative registry; `uq_engine_changelog_activated_per_version`
  partial-unique index (migration 0009) is the multi-worker double-activation backstop; engine sync
  path keeps the JSON file-flag fallback; `provisional` governed by registry (not file flag); v1
  stays provisional pending real §8 backtest + human approver. Independent adversarial review (Sonnet
  takeover) ACCEPT-WITH-CONDITIONS — all 3 conditions applied. Ledger:
  `reviews/b6-b28-scoring-activation.md`.
- 2026-06-06 — Engine v1 built (Phase 4 §S): deterministic collapse, rule-table labels (not score), confidence model + floor, 2-eval hysteresis, governance (churn/distribution/two-person/changelog), internal read API. Built on Opus (Tier-C).
- 2026-06-06 — Tier-C governance fan-out (Architect/Compliance/Product, no BLOCKER): config completeness validation; `provisional_model` tag when not activated; `disclaimer_version` + `prior_label` on results; fail-closed `X-Internal-Token` on the internal endpoint; neutral factor-agreement on sparse inputs. Residuals B24–B28. 21 unit tests (133 suite). Ledger: `reviews/phase4-rating-scoring-engine.md`.
