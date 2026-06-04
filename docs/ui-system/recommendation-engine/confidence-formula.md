# Confidence & Risk Score Formulas

## Confidence (0-100, separate from Score)
```
confidence = round(
  0.30 * freshness        +   # all sources within SLA? stale → down (per-source decay)
  0.25 * coverage         +   # % of sub-factors available (missing-data logic)
  0.20 * factor_agreement +   # do factors point the same direction? dispersion → down
  0.15 * retrieval_relevance + # (AI surfaces) grounding quality
  0.10 * model_signal         # backtest stability / cross-sample consistency for this instrument
)
```
Bands: **High ≥75 · Moderate 50-74 · Low <50.**

### Inputs
- freshness = min over sources of e^(-age/half_life).
- coverage = available_subfactors / total_subfactors (weighted).
- factor_agreement = 1 - normalized_dispersion(factor scores).
- model_signal = historical hit-stability for similar instruments (from backtest).

### Rules
- Partial coverage caps confidence at Moderate. Illiquid caps lower.
- **Do not expose the % to users until the calibration reliability-curve is within ±10%** (launch gate). Show band-only until then.

## Risk Score (0-100, higher = LOWER risk)
```
risk = normalize_within_sector(
  0.25*inv(beta) + 0.20*inv(volatility) + 0.15*inv(max_drawdown) +
  0.15*inv(leverage) + 0.15*liquidity + 0.10*earnings_predictability
)
```
- Each term sector-normalized; `inv` = inverse-direction (more debt/vol → lower risk score).
- Risk contributes 0.12 to the composite; also surfaced standalone in the Risk Analysis UX.
