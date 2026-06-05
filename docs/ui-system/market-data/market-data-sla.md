# Market Data SLA

## Freshness SLA
| Feed | SLA | Authoritative | Breach action |
|---|---|---|---|
| Intraday price | ≤15s | vendor | failover; banner "delayed"; lower confidence |
| EOD OHLC | by 20:00 IST | exchange | alert; block score recompute until present |
| AMFI NAV | by 23:30 IST | AMFI | alert; serve prior NAV with "as of" |
| Corp actions | by 19:00 IST | exchange/registrar | alert; hold dependent recompute |
| Fundamentals | ≤24h of filing | vendor | alert; mark stale |

## Availability SLA
- Ingestion pipeline 99.9%; recompute completion 99.5% by 19:00 IST.
- Vendor failover RTO < 5 min; gap backfill < 30 min after recovery.

## Accuracy SLA
- Vendor EOD vs exchange variance ≤ 0.01% (price), 0 for CA-adjusted continuity. Breach → reconciliation incident.

## Confidence coupling
- Any SLA breach automatically lowers downstream **confidence** and surfaces in Source Attribution + status banner — honesty over silent staleness.

## Escalation
- SLA breach → Data Source Monitor red → on-call (incident runbook). EOD-missing by 20:30 → SEV2 (scores may be stale).
