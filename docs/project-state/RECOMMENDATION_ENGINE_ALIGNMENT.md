# Recommendation / Scoring Engine Alignment

**Stage 1 — Contract Reconciliation. Documentation only; no implementation.**
**Date:** 2026-06-05
**Authority order (binding):** `DhanRadar_Architecture_Final.md` (§S) → `DhanRadar_Implementation_Plan.md` (Phase 4) → existing implementation → `docs/features` → `docs/ui-system/recommendation-engine` → mockups.

Compares the architecture's Rating/Scoring Engine (§S) against the UI package's `recommendation-engine/*` + `contracts/score-model.md` + `compliance/risk-profiling-engine.md`. Determines a single source of truth per dimension. **No formulas are implemented here.**

---

## 0. Headline verdict

- **Architecture §S is the source of truth for the *contract and governance*:** the label taxonomy (non-advisory), the "numeric never in DOM" rule, the confidence-floor refuse, hysteresis, methodology versioning, and the hard "risk profile never feeds the score" boundary.
- **The UI package `recommendation-engine/*` is the source of truth for the *quantitative detail* the architecture deliberately leaves to `ranking_configs`:** concrete factor sub-weights, the winsorize→z-score normalization, the confidence input breakdown, the fair-value blend, the backtesting methodology, and the model-version lifecycle.
- **Two hard conflicts must be resolved before the score contract is frozen:**
  1. **Label vocabulary** — UI package emits advisory `strong_buy/buy/hold/caution/avoid`; this is **rejected** (non-negotiable #2). Canonical = `in_form/on_track/off_track/out_of_form`.
  2. **5th factor axis** — architecture says **Trend**; UI package says **Growth**. Needs an architecture-owner decision (§3 below).
- The UI package's numbers are adopted as the **initial `ranking_configs` proposal (model_version v1)**, *retrofitted* to architecture labels/axes — not as a competing engine.

---

## 1. Side-by-side: what each source defines

| Dimension | Architecture §S | UI package recommendation-engine |
|---|---|---|
| Composite score range | 0–100 (unified_score) | 0–100 (rounded int) |
| Factor axes | Quality · Valuation · Momentum · Risk · **Trend** | Valuation · Growth(0.22) · Quality(0.24) · Momentum(0.20) · Risk(0.12), Valuation 0.22 — uses **Growth** |
| Factor weights | "versioned in `ranking_configs`, sum 1.0 ± 0.001, human-approved" (no numbers in doc) | explicit: 0.22/0.22/0.24/0.20/0.12 |
| Normalization | not specified (left to engine) | winsorize p1/p99 → z-score within sector+peer → clamp ±3 → map 0–100 |
| Missing data | not specified | drop sub-factor + renormalize; >40% missing → low-coverage; whole factor → `partial_coverage`, confidence capped Moderate |
| Label set | **In-form / On-track / Off-track / Out-of-form** (deterministic rule table, NOT from the number) | **strong_buy/buy/hold/caution/avoid** (derived from score bands ≥85/70/55/40) |
| Label derivation | rule table on category-relative perf, **not** the numeric score | numeric band cut-offs |
| Confidence range | 0–1 (thresholds 0.30, 0.70) | 0–100 (bands ≥75/50/<50) |
| Confidence inputs | signal coverage, source_reliability_avg, agreement | freshness 0.30 + coverage 0.25 + factor_agreement 0.20 + retrieval_relevance 0.15 + model_signal 0.10 |
| Confidence floor | **< 0.30 → refuse, "Insufficient data"** | partial-coverage caps at Moderate; no explicit refuse |
| Confidence exposure | band-only until calibrated | "do not expose % until calibration ±10%" (same intent) |
| Hysteresis | **2 consecutive evals** before a label flip; `eval_seq` exposed | ±2 buffer at band edges |
| Fair value | mentioned (gated, Pro) | `0.5*DCF + 0.3*RelativePE + 0.2*EPV`; `upside=(fv-price)/price` |
| Risk-as-factor | one of the 5 axes (no formula) | `0.25*inv(beta)+0.20*inv(vol)+0.15*inv(maxDD)+0.15*inv(leverage)+0.15*liquidity+0.10*earnings_predictability`; 0.12 of composite |
| User risk profile | conservative/moderate/aggressive/**not_set**; weighted 0–35/36–65/66–100; sole writer Onboarding; **excluded from score** | 8-question, sum 8–40; Conservative ≤18/Moderate 19–30/Aggressive 31–40; **excluded from score** |
| Governance gates | hysteresis, confidence floor, label-distribution sanity, >5% churn human-review gate, `rating_engine_changelog` | DRAFT→BACKTEST(gates)→CANARY→PROMOTE/ROLLBACK; compliance + research sign-off; bit-reproducible |
| Benchmark | category index / NIFTY (implied) | NIFTY 50/500/Midcap/Smallcap TRI, sector index, scheme benchmark; always TRI |
| Backtesting | not detailed | point-in-time, survivorship-free, quintile spread, IC, hit-rate, Sharpe; pass-gates defined |
| Model versioning | `rating_engine_changelog` (factors before/after, methodology URL) | `model_version` immutable, canary %, AI-Ops dashboard, bit-reproducible |

---

## 2. Formula conflicts → resolution

### F1 — Label taxonomy (HARD; non-negotiable #2)
- **Architecture:** `in_form / on_track / off_track / out_of_form` + `insufficient_data`. Label from a deterministic **rule table**, never a pure function of the number.
- **UI package:** `strong_buy / buy / hold / caution / avoid` from numeric bands.
- **Source of truth:** **Architecture.** Advisory verbs are rejected.
- **Resolution:** Adopt the architecture labels. The UI package's band cut-offs become an *internal* helper mapped to labels via the rule table, not the public vocabulary. Canonical mapping: strong_buy+buy→`in_form`, hold→`on_track`, caution→`off_track`, avoid→`out_of_form`. Keep the architecture's rule-table semantics (category-relative perf), with the numeric bands as a secondary input — **the label must not be a pure function of the score** (architecture grep guard).

### F2 — Composite score weights
- **Architecture:** weights live in `ranking_configs`, not fixed in the doc.
- **UI package:** Valuation 0.22 · Growth 0.22 · Quality 0.24 · Momentum 0.20 · Risk 0.12.
- **Source of truth:** **Architecture for the mechanism** (versioned, human-approved, sum 1.0±0.001); **UI package for the initial values** (proposed `model_version` v1, after the axis decision F3).
- **Resolution:** Seed `ranking_configs` v1 with the UI package weights, subject to F3. They must pass the architecture's weight-sum validator and two-person methodology gate before activation.

### F3 — 5th factor axis: Trend vs Growth (RESOLVED 2026-06-05)
- **Architecture:** Quality · Valuation · Momentum · Risk · **Trend**. "Trend" sub-factors are **not** specified in §S.
- **UI package:** Quality · Valuation · Momentum · Risk · **Growth**, with a full sub-factor catalog (Revenue CAGR, EPS growth, sales momentum, forward growth, margin expansion).
- **DECISION (review-approved):** **Keep the 5-axis architecture with "Trend"; do NOT rename to Growth.** Growth is incorporated as **sub-factors within the Trend axis**. Trend is the broader investment dimension (price/earnings/growth/strength trends); Growth alone is narrower and would force a later product-messaging change.
- **Resolution:** Trend inherits the old Growth weight slot (0.22); Momentum stays pure price/technical (0.20). To avoid double-counting, `earnings-revision` and `relative-strength` move from Momentum into Trend; both appear in exactly one axis (test-enforced). **Now FINAL** — see `FINAL_SCORING_SPEC.md` §2.4 / §3 for the canonical sub-factor placement and v1 weights. The `factors` API key set is `quality/valuation/momentum/risk/trend` and may now be frozen.

### F4 — Normalization & missing-data
- **Architecture:** unspecified. **UI package:** winsorize→z-score→clamp→0–100; drop+renormalize on missing; coverage flags.
- **Source of truth:** **UI package** (fills a genuine gap; no conflict with §S).
- **Resolution:** Adopt as the canonical normalization spec for `model_version` v1.

### F5 — Fair value
- **Architecture:** gated Pro field, no formula. **UI package:** `0.5*DCF+0.3*RelativePE+0.2*EPV`.
- **Source of truth:** **UI package** for the blend; **architecture** for the gating (Pro, numeric not on public DOM).
- **Resolution:** Adopt the blend; serve only behind tier gate.

---

## 3. Confidence conflicts → resolution

### C1 — Scale (0–1 vs 0–100)
- **Source of truth:** **Architecture's thresholds** (0.30 refuse, 0.70 high) are the governance anchors; the UI package's 0–100 is a presentation scale.
- **Resolution:** Compute confidence on **0–1** internally (so the 0.30 floor and 0.70 high rule apply verbatim); the UI package's 0–100 is a ×100 display transform. Band map: `high` ≥0.70, `medium` 0.50–0.69, `low` <0.50, **refuse** <0.30 → `insufficient_data`.

### C2 — Inputs
- **Architecture:** coverage + source_reliability_avg + agreement. **UI package:** freshness 0.30 + coverage 0.25 + factor_agreement 0.20 + retrieval_relevance 0.15 + model_signal 0.10.
- **Source of truth:** **UI package** (superset; includes architecture's coverage + agreement; `retrieval_relevance` maps to source reliability for AI surfaces).
- **Resolution:** Adopt the UI package's weighted formula as v1, **with** architecture's hard rules layered on top: `<0.30 → refuse`, and `confidence>0.7 ⇒ ≥3 contributing signals AND high-reliability sources` (architecture structural guard).

### C3 — Exposure gate
- **Both agree:** band-only until calibration reliability-curve within ±10%.
- **Resolution:** No conflict. Band-only at launch; numeric % behind the calibration gate produced by backtesting.

---

## 4. Risk conflicts → resolution

**Two distinct things — keep them separate (both sources agree they must never mix):**

### R1 — Risk as a score factor
- **Architecture:** one of the 5 axes, no formula. **UI package:** `0.25 inv(beta)+0.20 inv(vol)+0.15 inv(maxDD)+0.15 inv(leverage)+0.15 liquidity+0.10 earnings_predictability`, sector-normalized, higher = lower risk, 0.12 of composite.
- **Source of truth:** **UI package** for the formula; **architecture** for it being a versioned `ranking_configs` axis.
- **Resolution:** Adopt as v1 risk sub-formula.

### R2 — User risk-profiling (suitability/education only)
- **Architecture:** `conservative/moderate/aggressive/not_set`, weighted 0–35/36–65/66–100, sole writer Onboarding, logged in `risk_profile_log`, **excluded from scoring** (code boundary + test).
- **UI package:** 8 questions, sum 8–40, Conservative ≤18/Moderate 19–30/Aggressive 31–40, **excluded from scoring**.
- **Conflict:** bucket scale (architecture 0–100 weighting vs UI sum 8–40) and the missing `not_set` state in the UI package.
- **Source of truth:** **Architecture** for the state machine (`not_set` required; sole-writer = Onboarding; `risk_profile_log`; hard exclusion). **UI package** for the questionnaire content (8 questions are usable).
- **Resolution:** Keep architecture's `conservative/moderate/aggressive/not_set` + 0–100 weighting + sole-writer rule. Re-scale the UI package's 8-question raw sum (8–40) onto the 0–100 weighting, or adopt the architecture's bucket thresholds directly. **The hard rule both share — risk profile never enters the scoring engine — is canonical and must be enforced by test.**

---

## 5. Governance, benchmark, backtesting, versioning

- **Governance gates:** **Architecture is canonical** (hysteresis = 2 consecutive evals + `eval_seq`; confidence floor; label-distribution sanity; >5% batch churn → Compliance human-review gate, fail-closed; `rating_engine_changelog`). The UI package's ±2 band buffer is **additive** (a smoothing detail), not a replacement for eval-count hysteresis — keep both.
- **Benchmark:** **UI package** is the source (NIFTY 50/500/Midcap/Smallcap TRI, sector index, scheme benchmark; always TRI). No architecture conflict.
- **Backtesting:** **UI package** is the source (point-in-time, survivorship-free, quintile spread, IC, hit-rate, Sharpe, pass-gates). It also produces the **calibration reliability-curve** that releases the confidence-% exposure gate (C3). No conflict.
- **Model versioning:** **Merge** — architecture's `rating_engine_changelog` + two-person methodology gate is the audit/approval mechanism; the UI package's DRAFT→BACKTEST→CANARY→PROMOTE/ROLLBACK lifecycle + immutable `model_version` + bit-reproducibility is the operational process. Adopt both; the canary step writes a changelog row and passes the methodology gate before promote.

---

## 6. Single source of truth — summary

| Area | Source of truth |
|---|---|
| Label vocabulary, "no numeric in DOM", confidence floor, hysteresis, churn gate, risk-profile exclusion | **Architecture §S** |
| Factor sub-weights (v1 seed), normalization, missing-data, fair-value blend, risk sub-formula, confidence input weights | **UI package (as `ranking_configs` v1 proposal)** |
| Benchmark selection, backtesting methodology, calibration curve | **UI package** |
| Model-version audit/approval | **Architecture changelog + two-person gate** |
| Model-version operational lifecycle (canary/rollback) | **UI package** |
| Risk-profile state machine (`not_set`, sole-writer, log) | **Architecture** |
| Risk-profile questionnaire content | **UI package (8 questions, re-scaled)** |

## 7. Decisions — RESOLVED (2026-06-05, review-approved)
- **REC-D1 (axis): RESOLVED — keep 5-axis "Trend"; do NOT rename to Growth.** Growth is nested as sub-factors inside Trend; Trend inherits the 0.22 weight; Momentum stays pure price/technical; `earnings-revision` + `relative-strength` move to Trend (single-axis, no double-count). Canonical detail in `FINAL_SCORING_SPEC.md` §2.4/§3.
- **REC-D2 (confidence scale): RESOLVED — internal 0–1, ×100 display when calibration gate open, launch band-only** (`high`/`medium`/`low`). See `FINAL_SCORING_SPEC.md` §5.
- **REC-D3 (risk-profile scale): RESOLVED — architecture thresholds + states** (`conservative`/`moderate`/`aggressive`/`not_set`); UI questionnaire content re-scaled onto 0–100. See `FINAL_SCORING_SPEC.md` §6.2.

**Superseded by `FINAL_SCORING_SPEC.md`** for all engineering purposes. **No engine code, weights, or migrations are created by this document.** Adopted numbers enter the system later only as a `ranking_configs` v1 proposal subject to the architecture's backtest pass-gates and two-person methodology approval.
</content>
