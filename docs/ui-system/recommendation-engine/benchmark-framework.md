# Benchmark Framework

## Benchmarks
| Universe | Benchmark |
|---|---|
| Large-cap equity | NIFTY 50 / SENSEX (TRI) |
| Broad equity | NIFTY 500 TRI |
| Sectoral | respective sector index (Bank/IT/Auto/FMCG…) |
| Mid/Small | NIFTY Midcap 150 / Smallcap 250 TRI |
| Mutual funds | scheme's stated benchmark (category index TRI) |
| ETFs | underlying index (tracking error vs benchmark) |

## Usage
- **Relative performance:** instrument & portfolio returns vs benchmark (alpha) over standard windows.
- **Score validation:** Strong-Buy basket vs benchmark (backtest hit-rate).
- **Normalization context:** sector-relative scoring uses sector index + peer set.
- **Portfolio:** XIRR vs NIFTY 50, sector exposure vs benchmark weights.
- **TRI (Total Return Index):** always use TRI (dividends reinvested) for fair comparison.

## Display (compliant)
- Show benchmark comparison as factual performance, with PAST_PERF disclaimer; never as a promise.
