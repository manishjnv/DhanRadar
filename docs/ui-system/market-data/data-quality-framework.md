# Data Quality Framework

## Dimensions + checks
| Dimension | Check |
|---|---|
| **Validity** | schema conformance; types/ranges (price>0, volume≥0, NAV>0); enum (series, CA type) |
| **Completeness** | all expected symbols present in EOD; no missing NAV for active schemes |
| **Accuracy** | vendor vs exchange EOD variance ≤ tolerance; CA adjustment continuity |
| **Consistency** | NSE vs BSE price within band; adj vs raw series reconcile |
| **Timeliness** | freshness within SLA (see SLA doc) |
| **Uniqueness** | idempotency key per record; no dupes (direct/regular, dual-listing) |
| **Integrity** | corporate-action factors produce continuous market cap / holding value |

## Validation pipeline (every record)
```
schema validate → range/enum checks → cross-source consistency →
  pass → normalize → load
  fail → DLQ(reason) + alert; quarantine; never load bad data
```

## Anomaly detection
- Price spike > N×ATR without CA → flag for review.
- Volume 0 on a trading day → flag.
- NAV jump beyond threshold without CA → flag.
- Stale (no update past SLA) → flag + lower confidence.

## Quality monitoring (Admin "Data Source Monitor")
- Per-source: freshness, success/fail counts, DLQ depth, variance vs exchange, anomaly count.
- Scorecard per feed (green/amber/red); SLA breach + anomaly → alert (Slack/PagerDuty).
- Weekly human sample-audit (news entity-linking precision, CA correctness).

## DLQ & remediation
- Failed records → `ingest_dlq(record, source, reason, ts)`; replayable by ops after fix.
- Schema-registry drift → migrate or reject; alert.
