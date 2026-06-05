# SLA / SLO Specification

## SLIs → SLOs (with error budgets)
| Service | SLI | SLO | Error budget (30d) |
|---|---|---|---|
| API | availability (non-5xx /total) | 99.9% | 43m |
| API read (cached) | p99 latency | < 80ms | — |
| API read (DB) | p99 latency | < 250ms | — |
| Auth/login | success latency p95 | < 400ms | — |
| Alert pipeline | trigger→notify | < 60s (p95) | — |
| AI answer | p95 latency | < 4s | — |
| Score recompute | full universe done | by 19:00 IST 99.5% | — |
| Ingestion | freshness within SLA | per market-data-sla | — |
| Notification | delivery success | ≥ 99% | — |
| Web | LCP / INP / CLS | <2.0s / <200ms / <0.1 | — |

## External SLA (user-facing, if published)
- Platform availability 99.9% monthly. Data "informational, best-effort" (not a trading guarantee — compliance).

## Error-budget policy
- Budget consumed → **freeze feature launches**, redirect to reliability until restored. Burn-rate alerts (fast 1h + slow 6h).
- Monthly SLO review; breaches → blameless post-mortem + action items.

## RPO/RTO (from DR)
- RPO 5 min (WAL archiving) · RTO 30 min (API) · 60 min full platform. Validated by quarterly restore drills.

## Reporting
- SLO dashboard (Grafana) per service + budget remaining; monthly reliability report to Exec dashboard.
