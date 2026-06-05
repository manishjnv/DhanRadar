# Market Holiday Logic & Data Recovery

## Market holiday logic
- Maintain **exchange holiday calendar** (NSE/BSE) + trading sessions (incl. special/muhurat sessions).
- On holidays: no intraday expectation; EOD jobs skip; "markets closed" state in UI; no false stale-alerts.
- Half-days / special sessions handled via calendar metadata.
- AMFI NAV may publish on some exchange holidays — decouple NAV schedule from equity calendar.
- Score recompute runs on **trading days** only (or carries forward last as_of on holidays, clearly dated).

## Data recovery
- **Gap detection:** watermark per source; missing expected records → recovery job.
- **Backfill:** pull missing range from vendor history/file; idempotent (dedupe keys); reconcile after.
- **DLQ replay:** ops-triggered after fix; preserves order/idempotency.
- **Vendor outage:** failover to secondary; on primary recovery, backfill the gap + reconcile.
- **Corrupt/incorrect data:** quarantine, correct, recompute affected scores (versioned), re-emit invalidation; audit.
- **Disaster:** prices/NAV reconstructable from S3 archives + vendor history; ES/vector rebuildable from Postgres (source of truth).

## Alerts
- Holiday-aware: suppress stale-alerts on non-trading days; raise SEV on missing data during a trading session.
