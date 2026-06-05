# Alerting Framework

## Principles
- **Alert on symptoms (SLO burn), not causes.** Every alert is actionable + has a runbook link.
- Severity: SEV1 (outage/payment/data-integrity), SEV2 (degraded/SLO at risk), SEV3 (warning).
- Routing: SEV1/2 → PagerDuty (on-call); SEV3 → Slack. De-dup + grouping in Alertmanager. Maintenance windows mute.

## SLO burn-rate alerts (multi-window)
- Fast burn (1h window, high rate) + slow burn (6h) → page only on real budget threat (cuts noise).

## Alert catalog (examples)
| Alert | Condition | Sev | Runbook |
|---|---|---|---|
| API availability burn | error-budget fast+slow burn | SEV1 | incident-runbook |
| API p99 high | p99 > 250ms 10m | SEV2 | capacity-and-scaling |
| 5xx spike | 5xx rate > 2% 5m | SEV1 | incident-runbook |
| DLQ growth | any {topic}.dlq depth > N | SEV2 | event-architecture |
| Consumer lag | lag > threshold 10m | SEV2 | capacity |
| EOD data missing | bhavcopy absent by 20:30 IST | SEV2 | market-data-sla |
| Reconciliation variance | variance > tolerance | SEV2 | data-reconciliation |
| Score recompute overrun | not done by 19:00 IST | SEV2 | recommendation-engine |
| Payment failure spike | fail-rate > X% | SEV1 | incident-runbook |
| **Audit-write failure** | any failed audit persist (sensitive) | SEV1 | secrets/runbook |
| AI safety flag spike | advice-boundary/hallucination > 0 trend | SEV1 | hallucination-controls |
| AI cost anomaly | ₹ > X% over 7-day avg | SEV2 | llm-observability |
| Cache hit-rate drop | < target 15m | SEV3 | llm-observability |
| Cert/secret expiry | < 7 days | SEV2 | secrets-runbook |

## Anti-noise
- Tune thresholds from baselines; require sustained breach; group related; auto-resolve. Post-incident: every page reviewed (was it actionable?).
