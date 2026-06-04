# Factor Catalog

Each factor = weighted, normalized blend of sub-factors. Direction: ↑ = higher sub-factor raises factor (↓ = inverse).

## Valuation (cheap vs sector)
| Sub-factor | Dir | Notes |
|---|---|---|
| P/E (vs sector median) | ↓ | trailing + forward |
| P/B | ↓ | banks/financials weighted |
| EV/EBITDA | ↓ | capital-structure neutral |
| P/FCF | ↓ | cash-based |
| Dividend yield | ↑ | secondary |
| PEG | ↓ | growth-adjusted |

## Growth
| Revenue CAGR (3y/5y) | ↑ |
| EPS growth (YoY, 3y) | ↑ |
| Sales momentum (QoQ accel) | ↑ |
| Forward growth estimate | ↑ |
| Margin expansion trend | ↑ |

## Quality
| ROE / ROCE | ↑ |
| Operating + net margin | ↑ |
| FCF margin / cash conversion | ↑ |
| Debt/Equity | ↓ |
| Interest coverage | ↑ |
| Earnings stability (low variance) | ↑ |
| Accruals (lower = better) | ↓ |
| Promoter pledge | ↓ |

## Momentum
| 3m / 6m / 12m price return | ↑ |
| 50-DMA vs 200-DMA (golden/death cross) | ↑ |
| RSI (regime-aware) | ↑ |
| Earnings-revision trend | ↑ |
| Relative strength vs sector/index | ↑ |
| News-sentiment (small modifier) | ↑ |

## Risk (higher score = LOWER risk)
| Beta | ↓ |
| Volatility (30/90d) | ↓ |
| Max drawdown (1y) | ↓ |
| Debt/Equity, leverage | ↓ |
| Liquidity (ADV, spread, free-float) | ↑ |
| Earnings predictability | ↑ |
| Concentration (segment/customer) | ↓ |

## Fund/ETF mapping
- Valuation→portfolio valuation/expense; Growth→rolling-return trend; Quality→manager tenure, consistency, downside capture; Momentum→relative category rank; Risk→Sharpe/Sortino, std-dev, tracking error (ETF).

## Sub-factor weights
- Stored per **sector** in model config (versioned). Defaults provided; sector overrides for banks/IT/energy/FMCG/auto/pharma.
