# DhanRadar Recommendation Engine — Production Spec

*Quant Architect · Investment Research Lead · AI Architect. Deterministic quant core; AI explains, never scores. Extends doc 03 (Part I), doc 04 (Part 5), contracts/score-model.md.*

## 1. Architecture
```
Inputs (market-data layer)
  prices · fundamentals · NAV · corporate-actions(adjusted) · technicals · news-sentiment
        ▼
FACTOR COMPUTE (per instrument)  → raw factor metrics
        ▼
NORMALIZE (within sector+peer set, z→0-100, winsorized)
        ▼
SECTOR & LIQUIDITY ADJUSTMENTS
        ▼
WEIGHTED COMPOSITE (model_version weights) → score 0-100
        ▼
SIGNAL BAND  +  FAIR VALUE  +  CONFIDENCE
        ▼
WRITE scores(instrument, as_of, model_version)  [immutable]
        ▼
DIFF vs prior → events (alerts, cache invalidation) → AI pre-generates explanations
```
- **Determinism:** reproducible from inputs + version weights. No LLM in the number.
- **Cadence:** nightly 18:30 IST (trading days), reading authoritative EOD; intraday Score is carried-forward (clearly dated).

## 2. Five-factor frame
Valuation · Growth · Quality · Momentum · Risk. Each = weighted blend of sub-factors (see factor-catalog.md). Funds/ETFs map the same frame to fund-specific metrics.

## 3. Missing-data logic
Priority order per factor:
1. Use reported value if fresh + valid.
2. If a sub-factor missing → **drop it and renormalize remaining sub-factor weights** within the factor (never impute 0).
3. If > 40% of a factor's sub-factors missing → factor marked **low-coverage**; factor still computed on available, but **confidence penalized**.
4. If a whole factor uncomputable → composite reweights remaining factors proportionally; instrument flagged `partial_coverage`; confidence capped at Moderate.
5. Stale data (past SLA) → used but **confidence reduced** (freshness term); surfaced in Source Attribution.
- Never fabricate; never silently zero. Coverage feeds confidence.

## 4. Sector adjustments
- Normalization is **sector-relative** (z-score within sector+peer set) so a 90 in Banking ≈ a 90 in IT.
- Sector-specific sub-factor weights (e.g., Banks weight asset-quality/NIM; IT weight margins/deal-wins; Energy weight cyclic-adjusted earnings). Stored per sector in model config.
- Cyclicals: use cycle-adjusted (normalized) earnings to avoid peak/trough distortion.

## 5. Liquidity adjustments
- Liquidity sub-factor in Risk (ADV, spread, impact cost, free-float).
- **Score reliability gate:** very illiquid names (ADV < threshold) get a confidence penalty + "low liquidity" flag; micro-caps may be excluded from public recommendation surfaces.

## 6. News-sentiment factor
- Optional **momentum/risk modifier** (small weight), not a standalone score driver.
- From the news pipeline: per-instrument sentiment (entity-linked, deduped) over a trailing window; clamped; decays with age.
- Guardrail: sentiment can nudge Momentum/Risk within ±a few points; cannot dominate fundamentals (prevents headline-chasing).

## 7. Signal lifecycle (recommendation lifecycle)
```
NEW (first score) → ACTIVE (daily refresh) → CHANGED (band shift → event/alert)
  → STALE (data gap → confidence down, flagged) → SUSPENDED (insufficient data / corp event)
  → RETIRED (delisting/merger; history preserved)
```
- Band changes emit events → alerts + cache invalidation + AI re-explain.
- Every state transition audited (recommendation_audit, compliance).
- Hysteresis: small band-edge oscillation damped (require sustained move or buffer) to avoid alert spam.

## 8. Outputs
`{ score, signal, factors{...}, fair_value, confidence, coverage, model_version, as_of }` → API + audit + AI explanation inputs.
