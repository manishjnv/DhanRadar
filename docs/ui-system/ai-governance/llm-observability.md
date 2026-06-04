# LLM Observability — Cost, Token, Latency, Routing

## Metrics (per request, tagged feature/model/prompt_version/user-tier)
- tokens_in / tokens_out / total; cost_inr; latency p50/p95/p99; cache (exact/semantic) hit; model used; fallback fired; safety_result; groundedness.

## Cost & token monitoring
- **Budgets:** per-user (Free 5 AI/day), per-feature, **global daily ₹ cap**. Breach → queue/degrade (never silent overspend).
- **Alerts:** cost anomaly (>X% over 7-day avg), token spike, cache-hit-rate drop, model-mix shift toward expensive tier, runaway-loop detector.
- **Attribution:** ₹/feature, ₹/user, ₹/1k-tokens; weekly cost review in AI-Ops.

## Model routing observability
- Routing decisions logged (task, complexity, chosen tier, reason); fallback rate; escalation rate (small→large).
- Latency/error per model; circuit-breaker state.

## Tracing
- OpenTelemetry span: gateway → cache → retrieval → model → safety → attribution, one request_id; correlated with backend logs/metrics.

## Dashboards (AI-Ops)
- Cost (daily ₹, feature/user mix), latency, cache hit-rate, token volume, model mix, fallback/escalation, quality/groundedness, safety flags, feedback. SLO: AI p95 < 4s; cache hit-rate target.
