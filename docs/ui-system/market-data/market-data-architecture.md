# DhanRadar — Market Data Architecture

*Prepared by: Market Data Architect · Data Engineering Lead. Extends doc 04 (Data/AI). All feeds flow through one ingestion contract; vendor-abstracted.*

## 0. Map
```
Sources                 Ingestion (Celery 'ingest')              Storage
NSE (stream+EOD) ─┐                                          ┌─ Timescale (prices/NAV ticks+EOD)
BSE (stream+EOD) ─┤   Connector → Validate → Normalize →     ├─ Postgres (instruments, CA, fundamentals)
AMFI (EOD NAV)   ─┼─▶ Dedupe → Adjust(CA) → Load → Emit      ├─ Elasticsearch (screener/search fields)
Corp Actions     ─┤        (DataProvider abstraction)        ├─ Redis (hot px/nav/score)
Fundamentals     ─┤                                          └─ S3 (raw payloads, audit)
News             ─┘   watermark · idempotency · DLQ · lineage
```

## 1. DataProvider abstraction
```
interface DataProvider {
  prices(symbols, range): OHLCV[]        // intraday stream + EOD
  nav(scheme, range): NAV[]
  reference(symbol): InstrumentMeta
  corporateActions(since): CorporateAction[]
  fundamentals(symbol): Fundamentals
}
Impl: VendorA (primary), VendorB (failover), MockProvider (dev → seed-data.json)
```
Swapping vendors = new adapter; domain code unchanged. (See launch/data-licensing.)

## 2. Sources
### NSE / BSE
- **Intraday:** licensed vendor WebSocket → throttled snapshots (5–15s persisted) → Redis `px:{sym}` + Timescale.
- **EOD:** bhavcopy file → authoritative OHLC overwrites intraday close; drives nightly score recompute.
- Dual-listing (NSE+BSE): reconcile to one **canonical instrument** with venue tags; primary venue = higher liquidity.
- Circuit limits, trading status, series (EQ/BE) captured in meta.

### AMFI
- Daily NAV text file (~23:00 IST) + scheme master. ETag/checksum to skip reprocessing.
- Scheme code ↔ ISIN map; **direct vs regular** dedupe; track mergers/closures. Backfill historical NAV for rolling returns.

### Fundamental data
- Quarterly/annual financials (revenue, EBITDA, PAT, EPS, balance sheet, cash flow), ratios (PE, PB, ROE, D/E), shareholding pattern.
- Source: licensed fundamentals vendor + filings. Versioned by report period; restatements tracked.

### Technical data
- Derived from price series: moving averages (50/200-DMA), RSI, MACD, volatility(30d), beta, drawdown. Computed in the scoring/technical pipeline, cached.

## 3. Corporate actions (correctness-critical)
| Type | Effect |
|---|---|
| **Dividend** | event/alert; (optional) total-return series; no price split-adjust |
| **Split** | adjust historical prices by factor; adjust holdings qty/avg |
| **Bonus** | adjust prices + holdings (e.g., 1:1 → qty×2, avg÷2) |
| **Rights** | event; entitlement calc; price reference adjustment |
| **Name/symbol change, merger** | remap canonical instrument; preserve history |
- Pipeline: ingest CA → classify → compute **adjustment factor** → apply to `instrument_prices` (store adj_close alongside raw close) → adjust user `holdings` → schedule ex/record-date alerts → **audit** every adjustment.
- Adjustments are reproducible (store factor + as-of); reversible if CA corrected.

## 4. Historical data
- Full OHLCV history (Timescale hypertable, monthly partitions); adjusted + unadjusted series.
- NAV history per scheme (for rolling/CAGR). Fundamentals history by period.
- Cold partitions → S3 (Parquet) for analytics/backtests; Timescale continuous aggregates for fast range queries.

## 5. Data freshness (drives confidence)
| Feed | Target |
|---|---|
| Intraday price | <15s |
| EOD OHLC | by 20:00 IST |
| AMFI NAV | by 23:30 IST |
| Corp actions | by 19:00 IST (T-1 to ex-date) |
| Fundamentals | within 24h of filing |
Stale feed → lowers AI **confidence** + shows in Source Attribution + Admin Data Source Monitor.

## 6. Failover & recovery (summary; detail in SLA + reconciliation docs)
- Vendor failover (VendorA→VendorB) on health-check breach; circuit breaker.
- Gap detection via watermark; auto-backfill on recovery; DLQ replay.
- Exchange/EOD as authoritative source of truth — intraday is best-effort, reconciled at EOD.
