# Dashboard Specifications (per audience)

## 1. Executive
**Audience:** CTO/CEO/Founders. **Cadence:** daily glance.
- MRR, ARR, MoM growth; paying users; **Free→Pro conversion %**; churn; ARPU; LTV:CAC.
- DAU/MAU + stickiness; signups; **activation rate**.
- Platform availability (30d); major incidents.
- AI cost as % revenue; gross margin.
- **KPIs:** business + product + cost (summary tiles + trend).

## 2. Product
**Audience:** PM/UX. 
- Funnel: visit → signup → activation → paid (drop-offs).
- Activation rate, time-to-first-value, D1/D7/D30 retention, cohort curves.
- Feature engagement: research depth, screener runs, watchlist adds, AI usage, alert adoption.
- Paywall hit-rate → upgrade; onboarding completion.
- **Recommendation KPIs:** signal CTR, add-to-watchlist rate, "why?" open rate.

## 3. Engineering
**Audience:** SRE/backend/frontend.
- **RED** per service/endpoint (rate, error %, p50/p95/p99); 4xx/5xx.
- **USE**: CPU/mem/saturation per pod; DB pool, slow queries, replica lag; Redis hit-rate; ES query latency.
- Event bus: throughput, consumer lag, **DLQ depth**, retry rate.
- Celery: queue depth/latency per queue; Beat job success.
- Web vitals (LCP/INP/CLS), bundle size; deploy markers; error budget burn.
- **Data Source Monitor:** feed freshness/lag, reconciliation variance, ingest DLQ.

## 4. AI Operations
**Audience:** ML Ops/AI Gov.
- Model version live + canary %; backtest spread/IC; **drift**; calibration reliability-curve.
- Quality: groundedness, helpful-rate (👍), low-quality drill; **safety flags** (advice-boundary, hallucinated-number, unsafe).
- Performance: AI p50/p95/p99, fallback rate, escalation rate, **cache hit-rate** (exact+semantic).
- **Cost KPIs:** ₹/day, ₹/feature, ₹/user, ₹/1k-tokens, token volume, model mix; budget burn + anomalies.

## 5. Support
**Audience:** Support/Success.
- Ticket volume/category, SLA timers, resolution time, backlog.
- Top user-facing errors (payment failures, sync errors, login issues) with affected counts.
- Notification health (delivery/bounce), status-page incidents.
- Per-user lookup (audited): plan, recent errors, subscription state.

## Provisioning
- All dashboards as code (Grafana provisioning + Sentry config), versioned in git, deployed via IaC. No click-ops.
