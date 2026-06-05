# Incident Runbook & SLO Policy (F6, F14, F20)

## SLOs + error budget
| Service | SLO | Error budget |
|---|---|---|
| API availability | 99.9% | 43m/month |
| Read p99 (cached) | <80ms | — |
| Alert latency | <60s | — |
| AI p95 | <4s | — |
Burn-rate alerts (fast 1h + slow 6h windows). Budget exhausted → freeze feature launches, focus on reliability.

## On-call
- PagerDuty rota (primary + secondary), 24×7 for P1/P2. Escalation: on-call → eng lead → CTO.
- Sev levels: SEV1 (outage/payment/data-integrity), SEV2 (degraded), SEV3 (minor).

## Runbooks (one per scenario)
1. **DB failover** — promote replica, repoint, verify, post-mortem.
2. **Region failover** — Cloudflare DNS cutover to warm standby; validate.
3. **Data-feed outage** — serve last-good + lower confidence + banner.
4. **Payment-gateway outage** — queue + retry (idempotent); status page.
5. **AI/model outage** — serve quant scores + cached explanations; assistant degraded message.
6. **Key compromise** — rotate keys, revoke session families, force re-auth, audit.
7. **Score-model regression** — rollback to prior model_version (repoint).

## DR drills (F14)
- **Quarterly** restore drill from PITR into isolated env; measure actual RTO; chaos test on staging.

## Observability as code (F20)
- Grafana dashboards + Prometheus rules + Sentry projects provisioned via IaC **before** prod traffic. Status page (public) for incident comms.

## Launch gate (P0)
- [ ] On-call rota live; runbooks tested
- [ ] Dashboards + alerts provisioned
- [ ] Status page up
