# Evaluation Framework (Test · A/B · Regression)

## Golden sets
- Per feature (search, explain, assistant, news-summary, portfolio-insights): curated Q&A with expected groundedness, allowed/forbidden content, expected sources, format.
- Versioned; grown from production failures + feedback (closed loop).

## Eval dimensions (per output)
| Dim | Method | Gate |
|---|---|---|
| Groundedness | claims↔sources (NLI / LLM-judge + checks) | ≥0.92 |
| Advice-boundary | classifier for imperative/advice phrasing | 0 violations |
| Hallucinated numbers | numeric claims must trace to provided data | ≈0 |
| Safety/toxicity | classifier | 0 |
| Format/contract | answer+confidence+sources+disclaimer present | 100% |
| Helpfulness | LLM-judge + human spot | ≥ baseline |

## A/B testing
- Prompt or model variants → split live traffic (flagged); compare groundedness, helpfulness (👍 rate), latency, cost, escalation rate. Winner promoted; loser retired. Statistical significance + min sample before decision.

## Regression testing
- Every release re-runs the full golden set; **must be ≥ parity** with current live on all gated dims. Any regression blocks promotion.
- Nightly scheduled regression on live prompts/models to catch upstream drift (model provider changes).

## CI integration
- Evals run in CI on any prompt/model/RAG-config change; block merge/promote on failure. Results surfaced in AI-Ops.
