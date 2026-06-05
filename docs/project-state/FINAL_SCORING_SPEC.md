# FINAL_SCORING_SPEC — Canonical Scoring-Engine Specification

**Status:** Canonical single source of truth for DhanRadar scoring. Supersedes the scoring content of `RECOMMENDATION_ENGINE_ALIGNMENT.md`, `docs/ui-system/recommendation-engine/*`, and `contracts/score-model.md` for engineering purposes.
**Date:** 2026-06-05
**Authority order (binding):** `DhanRadar_Architecture_Final.md` §S → `DhanRadar_Implementation_Plan.md` Phase 4 → existing code → docs/features → docs/ui-system → mockups.
**Scope:** specification only. No engine code, no `ranking_configs` records, no migration is created by this document.

**Finality convention (important):**

- **FINAL & binding now:** factor definitions, sub-factor placement, label taxonomy, thresholds, confidence formula shape, risk model, governance rules, exposure rules. These do not change without an architecture-owner amendment.
- **PROPOSED (v1), pending validation:** the concrete **numeric weights**. Per architecture §S/§S4, weights live in versioned `ranking_configs`, must sum to 1.0 ± 0.001, and require backtest pass-gates + two-person methodology approval before activation. The numbers below are the **v1 proposal**; they are canonical as a starting point but are not "frozen" until they clear the backtest gate.

---

## 0. Authority & scope — this is the sole source of truth for scoring

This document is the **single, canonical specification** for DhanRadar's **rating/scoring engine**:
the factor model, weight model, confidence model, risk model, labels, thresholds, and governance
rules. For any scoring question, read this — not the docs below.

**Supersedes (for ALL purposes, not just engineering):**

- `docs/project-state/RECOMMENDATION_ENGINE_ALIGNMENT.md` — the reconciliation that produced this
  spec; retained as provenance only.
- `docs/ui-system/recommendation-engine/*` and `docs/ui-system/contracts/score-model.md` — the
  UI-package engine docs; their quantitative detail is absorbed here as the `ranking_configs` v1
  proposal.

**Relationship to the architecture (authority order respected):** `DhanRadar_Architecture_Final.md`
§S remains the **originating governance authority** — its hard rules (no-numeric-in-DOM,
non-advisory labels, confidence floor, hysteresis, churn gate, risk-profile exclusion, methodology
versioning) are reproduced verbatim in §7 and are not weakened here. This document **elaborates and
freezes the spec detail** §S delegates to `ranking_configs`. On any scoring conflict between sibling
docs, **this document wins**; on a conflict with architecture §S's hard rules, §S wins and this
document is corrected.

**Terminology (compliance-relevant):** the canonical name is the **rating/scoring engine**. The
legacy term "recommendation engine" appears only in the superseded ui-system docs and is **retired**
— DhanRadar **issues no recommendations**. The engine emits **educational signals/labels + a
confidence band**; no buy/sell/hold output exists at any layer (non-negotiable #2).

**Change rule:** any change to a **FINAL** element here requires an ADR entry
(`ARCHITECTURE_DECISIONS.md`) and a Tier-C review (Architect + Compliance + Product). Numeric
weights remain **PROPOSED v1** until they clear the backtest pass-gates (§8) and the two-person
methodology gate (`BLOCKERS.md` B6 — non-blocking for implementation, enforced before production
activation).

---

## 1. Approved decisions encoded here

- **REC-D1 (RESOLVED — per review):** Keep the **5-axis architecture**: Quality · Valuation · Momentum · Risk · **Trend**. **Do NOT rename Trend to Growth.** Growth is incorporated as **sub-factors within Trend**. Rationale: Trend is the broader investment dimension (price, earnings, growth, strength trends); Growth alone is narrower and would force a product-messaging change later.
- **REC-D2 (APPROVED):** Confidence computed internally on **0–1**; displayed as a percentage only when the calibration gate permits; **launch UI shows band only** (`high`/`medium`/`low`).
- **REC-D3 (APPROVED):** User risk profile uses **architecture thresholds + states** (`conservative`/`moderate`/`aggressive`/`not_set`). The UI-package 8-question questionnaire content is reused, re-scaled onto the architecture range.
- **Non-negotiable #2:** labels are **non-advisory**: `in_form`/`on_track`/`off_track`/`out_of_form` (+ `insufficient_data`). Advisory verbs (`strong_buy/buy/hold/caution/avoid`) are rejected.

---

## 2. Final factor definitions & sub-factor placement

Five axes. Each sub-factor lives in **exactly one** axis (no double-counting). `dir` = direction (↑ higher raw value improves the axis score; ↓ lower is better; inverted internally).

### 2.1 QUALITY — business durability

| Sub-factor | dir |
|---|---|
| ROE / ROCE | ↑ |
| Operating + net margin | ↑ |
| FCF margin / cash conversion | ↑ |
| Debt / Equity | ↓ |
| Interest coverage | ↑ |
| Earnings stability (low variance) | ↑ |
| Accruals (lower = better) | ↓ |
| Promoter pledge | ↓ |

### 2.2 VALUATION — cheap vs sector

| Sub-factor | dir |
|---|---|
| P/E (trailing + forward, vs sector median) | ↓ |
| P/B | ↓ |
| EV/EBITDA | ↓ |
| P/FCF | ↓ |
| Dividend yield | ↑ |
| PEG | ↓ |

### 2.3 MOMENTUM — pure price/technical (no fundamental signals here)

| Sub-factor | dir |
|---|---|
| Price return 3m / 6m / 12m (composite) | ↑ |
| 50-DMA vs 200-DMA (golden/death cross) | ↑ |
| RSI (regime-aware) | ↑ |
| News-sentiment (small modifier) | ↑ |

### 2.4 TREND — fundamental-growth + directional strength *(Growth nested here, per REC-D1)*

| Sub-factor | dir | Origin |
|---|---|---|
| Revenue CAGR (3y/5y) | ↑ | Growth |
| EPS growth (YoY, 3y) | ↑ | Growth |
| Sales momentum (QoQ acceleration) | ↑ | Growth |
| Forward growth estimate | ↑ | Growth |
| Margin expansion trend | ↑ | Growth |
| Earnings-revision trend | ↑ | moved from Momentum |
| Relative strength vs sector/index | ↑ | moved from Momentum |

**Double-counting guard (test-enforced):** earnings-revision and relative-strength appear **only** in Trend, never in Momentum. Momentum is strictly price/technical. Any config that lists a sub-factor in two axes fails the weight validator.

### 2.5 RISK — higher axis score = LOWER risk

| Sub-factor | dir |
|---|---|
| Beta | ↓ |
| Volatility (30/90d) | ↓ |
| Max drawdown (1y) | ↓ |
| Leverage (Debt/Equity) | ↓ |
| Liquidity (ADV, spread, free-float) | ↑ |
| Earnings predictability | ↑ |
| Concentration (segment/customer) | ↓ |

### 2.6 Fund / ETF mapping (same five axes)

- Quality → manager tenure, consistency, downside capture.
- Valuation → portfolio valuation / expense ratio.
- Momentum → relative category rank.
- Trend → rolling-return trend, category-relative return trajectory.
- Risk → Sharpe / Sortino, std-dev, tracking error (ETF), premium/discount stability (ETF).

---

## 3. Final composite score formula

```
unified_score (0–100, integer) = round(
    w_quality   * Quality   +
    w_valuation * Valuation +
    w_momentum  * Momentum  +
    w_trend     * Trend     +
    w_risk      * Risk
)
```

**v1 PROPOSED weights (sum = 1.000; pending backtest gate):**

| Axis | v1 weight | Note |
|---|---|---|
| Quality | **0.24** | unchanged from UI-package proposal |
| Valuation | **0.22** | unchanged |
| Momentum | **0.20** | now pure price/technical |
| **Trend** | **0.22** | inherits the old "Growth" weight slot; now holds Growth + strength sub-factors |
| Risk | **0.12** | unchanged |
| **Total** | **1.00** | validator: sum 1.0 ± 0.001 |

Sub-factor weights within each axis are stored per sector in versioned config (banks weight asset-quality/NIM; IT weight margins/deal-wins; energy cycle-adjusted; etc.), defaults provided, all human-approved.

### 3.1 Normalization (FINAL)

1. **Winsorize** each raw sub-factor at p1 / p99 within the sector + peer set.
2. **Z-score** standardize: `z = (x_w − mean(S)) / std(S)`.
3. **Clamp** z to [−3, +3].
4. **Map to 0–100:** `n = 50 + (z * 50/3) * dir` (50 = sector median; `dir` = +1 or −1).
5. Axis score = sector-sub-weighted mean of its normalized sub-factors.

### 3.2 Missing-data handling (FINAL)

1. Use a reported value if fresh + valid.
2. Sub-factor missing → **drop it and renormalize the remaining sub-factor weights within that axis** (no imputation).
3. > 40% of an axis's sub-factors missing → axis flagged **low-coverage**; confidence penalized.
4. Whole axis uncomputable → composite **reweights the remaining axes proportionally**; instrument flagged `partial_coverage`; confidence capped at `medium`.
5. Stale data (past SLA) → used but confidence reduced.

### 3.3 Sector & liquidity adjustments (FINAL)

- Normalization is sector-relative (within sector + peer set); cyclicals use cycle-adjusted earnings.
- Very illiquid names (ADV < threshold) → confidence penalty + "low liquidity" flag, **not** a score distortion.

### 3.4 Fair value (FINAL blend; Pro-gated, numeric off public DOM)

```
fair_value = 0.5*DCF + 0.3*RelativePE + 0.2*EPV
upside     = (fair_value − price) / price
```

---

## 4. Final label taxonomy & thresholds (non-advisory)

**Labels are derived from a deterministic rule table on category-relative performance — NOT a pure function of the numeric score** (architecture grep-guard). The score band is a **secondary** input/tiebreaker only.

### 4.1 Primary rule table (FINAL)

| Label | enum | Rule |
|---|---|---|
| 🟢 In-form | `in_form` | outperforming category **1Y AND 3Y**, controlled drawdown |
| 🟡 On-track | `on_track` | matching category, no red flags |
| 🟠 Off-track | `off_track` | underperforming category **12m+** OR fund-manager change / emerging structural concern |
| 🔴 Out-of-form | `out_of_form` | **sustained** underperformance + structural concern |
| ⚪ Insufficient data | `insufficient_data` | confidence < 0.30 → refuse to label |

### 4.2 Secondary score-band cross-check (tiebreaker only, NOT the public vocabulary)

Internal band cut-offs used to corroborate the rule table (never surfaced as buy/sell): `≥70 ⇒ in_form-leaning`, `55–69 ⇒ on_track-leaning`, `40–54 ⇒ off_track-leaning`, `<40 ⇒ out_of_form-leaning`. If the rule table and band disagree materially, the rule table wins and the disagreement is logged.

### 4.3 Hysteresis (FINAL — both mechanisms)

- **Eval-count hysteresis (governance):** a label flip publishes only after **2 consecutive evaluations** at the new label; `eval_seq` is exposed for downstream alert gating.
- **Band-edge buffer (smoothing):** ±2 score-point buffer at band edges to damp oscillation.

---

## 5. Final confidence formula (REC-D2)

**Computed on 0–1.** Display = ×100 percentage only when the calibration gate is open; **launch = band only.**

```
confidence (0–1) =
    0.30 * freshness          +
    0.25 * coverage           +
    0.20 * factor_agreement   +
    0.15 * retrieval_relevance +
    0.10 * model_signal
```

| Input | Definition |
|---|---|
| `freshness` | min over sources of `e^(−age/half_life)` (per-source decay) |
| `coverage` | available_subfactors / total_subfactors (weighted) |
| `factor_agreement` | `1 − normalized_dispersion(axis_scores)` |
| `retrieval_relevance` | grounding quality of sources (AI surfaces); maps to `source_reliability_avg` |
| `model_signal` | historical hit-stability for similar instruments (from backtest) |

### 5.1 Bands (FINAL)

| Band | enum | Range |
|---|---|---|
| High | `high` | ≥ 0.70 |
| Medium | `medium` | 0.50 – 0.69 |
| Low | `low` | 0.30 – 0.49 |
| (refuse) | `insufficient_data` | < 0.30 → no label |

### 5.2 Hard structural rules (FINAL)

- **Floor:** confidence < 0.30 ⇒ refuse, emit `insufficient_data` (no label).
- **Coverage cap:** `partial_coverage` ⇒ confidence capped at `medium`; illiquid ⇒ capped lower.
- **High-confidence guard:** `confidence > 0.70 ⇒ ≥3 contributing signals AND high-reliability sources` (structurally prevents high-confidence low-coverage outputs).
- **Exposure gate:** numeric % suppressed until the backtest calibration reliability-curve is within ±10%; band-only until then.

---

## 6. Final risk model

Two **separate** constructs that must never mix (test-enforced).

### 6.1 Risk as a score factor (REC-D1/REC engine; 0–100, higher = lower risk)

```
risk = normalize_within_sector(
    0.25*inv(beta) + 0.20*inv(volatility) + 0.15*inv(max_drawdown) +
    0.15*inv(leverage) + 0.15*liquidity + 0.10*earnings_predictability
)
```

Contributes **0.12** to the composite (§3). Each term sector-normalized; `inv` = inverse-direction. Also surfaced standalone in the Risk Analysis UX.

### 6.2 User risk-profiling (REC-D3 — suitability/education ONLY)

- **States (architecture, FINAL):** `conservative` / `moderate` / `aggressive` / `not_set`.
- **Questionnaire:** reuse the UI-package 8-question instrument (age band, horizon, income stability, %-of-savings, reaction to 20% drop, experience, goal, prior-loss experience), each scored 1–5 → raw sum 8–40.
- **Re-scaling onto architecture range (FINAL):** `profile_score (0–100) = round((raw_sum − 8) / (40 − 8) * 100)`, then bucket by **architecture thresholds**:
  - `conservative` = 0–35
  - `moderate` = 36–65
  - `aggressive` = 66–100
  - `not_set` = quiz not taken.
- **Ownership:** sole writer is the Onboarding module; logged in `risk_profile_log`; stored in `users.risk_profile`. Domains read-only.
- **HARD RULE (test-enforced, compliance):** the user risk profile is **excluded from all scoring-engine inputs**. It only drives content-suitability warnings and educational surfacing — never personalizes the score.

---

## 7. Final governance rules (architecture §S4 — canonical)

- **Hysteresis:** 2 consecutive evals before a label flip (§4.3); `eval_seq` exposed.
- **Confidence floor:** < 0.30 → `insufficient_data` (§5.2).
- **Label-distribution sanity:** per-batch share of each label must stay within bounds (prevents all-🔴 collapse in a crash).
- **Human-review gate:** > 5% of the universe changing label in one batch → batch held in `pending_publish` (Compliance module, fail-closed) until admin approval.
- **Methodology versioning:** every weight/band/normalization change writes `rating_engine_changelog` (factors before/after + published methodology URL); requires **two-person gate** (`approved_by ≠ created_by`).
- **Disagreement disclosure:** contributing AND contradicting signals always shown; uncertainty never hidden.
- **No numeric in DOM:** numeric score + factor weights never reach the client; public surface = label + confidence band only.
- **Risk-profile exclusion:** §6.2 hard rule.

---

## 8. Final model-versioning & validation

- **`model_version`** (e.g. `v1`) encodes factor weights, sub-factor weights (per sector), normalization params, label rules/bands, fair-value blend. **Immutable once published.** Every `scores` row carries its `model_version` → bit-reproducible given (input snapshot + version) — required for regulatory defensibility.
- **Lifecycle:** `DRAFT → BACKTEST (pass-gates) → CANARY (% read traffic) → ANALYSIS → PROMOTE | ROLLBACK → RETIRED`.
- **Backtest pass-gates (must clear before a version is active):**
  1. Monotonic bucket spread (top minus bottom forward return) over ≥3 historical windows.
  2. Positive, stable Information Coefficient; In-form basket out-tracks benchmark.
  3. No single axis drives all the spread (diversified attribution).
  4. Turnover within bounds (hysteresis effective).
  - Methodology: point-in-time (no look-ahead), survivorship-bias-free, CA-adjusted; forward 1m/3m/6m/12m horizons; rebalance at recompute cadence. Produces the **calibration reliability-curve** that releases the confidence-% exposure gate (§5.2).
- **Benchmarks (FINAL):** large-cap NIFTY 50 / SENSEX TRI; broad NIFTY 500 TRI; mid/small NIFTY Midcap 150 / Smallcap 250 TRI; sectoral → sector index; MF → scheme's stated benchmark TRI; ETF → underlying index (tracking error). Always TRI. Portfolio: XIRR vs NIFTY 50.
- **Recompute cadence:** nightly 18:30 IST (trading days), authoritative EOD; intraday score carried-forward and clearly dated.

---

## 9. What is FINAL vs PROPOSED (summary)

| Element | Status |
|---|---|
| 5 axes + sub-factor placement (Trend holds Growth) | **FINAL** |
| Label taxonomy + rule table + thresholds | **FINAL** |
| Confidence formula shape, bands, hard rules, exposure gate | **FINAL** |
| Risk model (factor formula shape + user-profile states/exclusion) | **FINAL** |
| Normalization + missing-data + sector/liquidity rules | **FINAL** |
| Governance rules + versioning lifecycle + backtest gates + benchmarks | **FINAL** |
| **Numeric axis weights (0.24/0.22/0.20/0.22/0.12)** | **PROPOSED v1** — pending backtest pass-gates + two-person approval |
| Sub-factor weights per sector | **PROPOSED v1** — same gating |

This document is the single reference for any future scoring implementation. The engine itself is built in Implementation-Plan Phase 4; no code is produced here.
</content>
