# AI Output Quality Scoring

## Per-output quality score (0-100, internal)
```
quality = 0.35*groundedness + 0.20*format_contract + 0.15*relevance
        + 0.15*(1 - safety_risk) + 0.15*user_feedback_signal
```
- Computed at serve-time (cheap checks) + enriched async (feedback).
- Drives: caching TTL (high quality cached longer), surfacing (low quality → regenerate/escalate model), and the eval feedback loop.

## Confidence vs quality
- **Confidence** = how sure we are of the answer (shown to users, band-only until calibrated).
- **Quality** = internal health of the generation (governance metric, not user-facing).

## Feedback loop
- 👍/👎 on every answer → routed in AI-Ops Feedback Review → triaged to: prompt fix, retrieval fix, data fix, or training label.
- Low-rated clusters → new golden-set cases (regression prevention).

## Dashboards (AI-Ops)
- Quality distribution per feature, trend, low-quality drill-down, feedback themes, helpful-rate (target ≥85%).
