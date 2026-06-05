# DhanRadar — Observability Architecture

*SRE Architect · Platform Reliability Engineer. Extends doc 06 (DevOps/Security). Three pillars + KPIs, one correlation id everywhere.*

## 1. Pillars
| Pillar | Tooling | Purpose |
|---|---|---|
| **Metrics** | Prometheus (+ remote-write to long-term store) | RED/USE, KPIs, SLOs |
| **Logs** | structured JSON → Loki (or ELK) | debugging, audit-adjacent |
| **Traces** | OpenTelemetry → Tempo/Jaeger | end-to-end latency, dependency map |
| **Errors/RUM** | Sentry | exceptions, releases, web vitals, session replay (PII-scrubbed) |
| **Dashboards** | Grafana (as code) | per-audience views |
| **Alerting** | Alertmanager → PagerDuty/Slack | actionable, SLO-driven |

## 2. Correlation
- Every request carries `request_id` (gateway → service → DB/model → event bus). Logs, traces, metrics exemplars, and events all tagged with it. One id pivots across all pillars.
- Events carry `trace_id` (event-architecture) so async flows are traceable end-to-end.

## 3. Instrumentation standards
- **Metrics:** RED per endpoint (Rate, Errors, Duration histograms), USE per resource (Util, Saturation, Errors), business counters/gauges. Naming: `dr_<domain>_<metric>_<unit>`.
- **Logs:** JSON {ts, level, request_id, user_id?, service, msg, ctx}. No PII/secrets (scrubbers + gitleaks). Sampled at high volume; errors always.
- **Traces:** span per hop; key attributes (symbol, model_version, cache_hit, plan). Tail-based sampling (keep slow/error traces).
- **Cardinality discipline:** bounded label sets (no user_id as a metric label — use exemplars/logs).

## 4. Pipeline
```
app → OTel SDK → OTel Collector ─┬─> Prometheus (metrics)
                                 ├─> Loki (logs)
                                 ├─> Tempo (traces)
                                 └─> Sentry (errors)
Collector: batching, scrubbing, sampling, routing. Dashboards/alerts provisioned via IaC BEFORE prod traffic.
```

## 5. KPI taxonomy (detail in dashboard-specs)
Business · Product · AI · Recommendation · Notification · Subscription · Cost — each with owner, definition, target, source.
