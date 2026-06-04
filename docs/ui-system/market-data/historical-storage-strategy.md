# Historical Storage Strategy

## Stores
| Data | Store | Layout |
|---|---|---|
| Intraday + EOD OHLCV | **TimescaleDB** hypertable | monthly partitions; adj_close + raw close + volume |
| NAV history | Timescale/Postgres | per scheme, daily |
| Fundamentals history | Postgres | by report period; restatement-versioned |
| Corporate actions | Postgres | immutable, with applied factor |
| Cold history (>2y) | **S3 (Parquet)** | partitioned by year/exchange; for backtests/analytics |
| Scores history | Postgres | immutable (instrument, as_of, model_version) |

## Techniques
- **Continuous aggregates** (Timescale) for fast range queries (daily/weekly/monthly rollups).
- **Compression** on cold chunks; retention policy moves >2y to S3 Parquet, queryable via analytics engine.
- **Adjusted vs unadjusted:** store raw close always; compute adj_close from CA factors (recomputable if a CA is corrected).
- **Backfill:** historical bootstrap from vendor history API + file archives; idempotent, watermarked.

## Access patterns
- Charts (1D–5Y): Timescale continuous aggregates → Redis cache by (symbol, range).
- Rolling returns (funds): NAV history → precomputed nightly.
- Backtests (AI Ops / score model): S3 Parquet via batch engine.

## Retention
- Price/NAV history: indefinite (Parquet cold). Tick/snapshot: 90d hot then rollup. Aligns with evidence retention (compliance) for anything backing a shown recommendation.
