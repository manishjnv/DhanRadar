# Backtesting Framework

## Purpose
Validate that the Score has **predictive merit** and is **stable** before any model_version ships.

## Method
- **Point-in-time data** (no look-ahead): reconstruct factors as known on each historical as_of (CA-adjusted, restatement-aware).
- **Universe:** liquid instruments per period; survivorship-bias-free (include delisted).
- **Portfolios:** rank by Score into quintiles/deciles; form Strong-Buy/Buy/Hold/Avoid baskets; rebalance at recompute cadence (e.g., monthly).
- **Horizons:** forward 1m/3m/6m/12m returns per bucket.

## Metrics
- **Spread:** top-bucket minus bottom-bucket forward return (should be positive, monotonic).
- **Information Coefficient (IC):** rank-correlation(score, forward return); IC > 0 stable.
- **Hit rate:** % of Strong-Buy outperforming benchmark.
- **Risk-adjusted:** Sharpe/Sortino of score-sorted baskets; max drawdown.
- **Factor attribution:** contribution of each factor to spread.
- **Turnover/stability:** band-change frequency (avoid churn).

## Gates (a version must pass)
- Monotonic bucket spread over ≥3 historical windows.
- IC positive + stable; Strong-Buy hit-rate > benchmark.
- No single factor driving all alpha (diversified).
- Turnover within bounds (hysteresis effective).

## Tooling
- Runs on S3 Parquet history via batch engine; results stored + shown in AI-Ops (model versioning). Calibration reliability-curve produced here (feeds confidence exposure gate).
