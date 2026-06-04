# DhanRadar — AI Governance Framework

*AI Platform Architect · AI Governance Lead. Extends doc 04 (Data/AI) and the AI-layer UX. Governs every model-touching path through the single AI Gateway.*

## 1. Principles
1. **One door:** no service calls an LLM directly — all via the AI Gateway (authz → cost → cache → prompt → RAG → route → safety → attribution).
2. **Grounded only:** RAG over internal DhanRadar data; no open-web inference.
3. **Explain, never advise:** AI describes/explains; the deterministic engine scores. AI cannot generate the number, advise, or promise returns.
4. **Numbers from code, words from AI.** AI must not invent stats.
5. **Every output:** answer → reasoning → confidence → sources, + "not advice" disclaimer.
6. **Auditable & reversible:** prompts/models versioned; outputs logged; rollback instant.

## 2. Governance bodies & roles
| Role | Responsibility |
|---|---|
| AI Governance Lead | owns policy, approves prompt/model releases, chairs review |
| AI Platform Architect | gateway, routing, eval infra |
| Compliance Officer | advice-boundary + disclosure sign-off |
| ML Ops | runs evals, monitors safety/cost, canary/rollback |
| Research Lead | factual correctness of explanations |

## 3. Control planes
- **Prompt management & versioning** → prompt-management.md
- **Evaluation (test/A-B/regression)** → evaluation-framework.md
- **Quality scoring** → quality-scoring.md
- **Observability (cost/token/latency)** → llm-observability.md
- **Hallucination/grounding/safety** → hallucination-controls.md

## 4. Release gate (any prompt or model change)
```
DRAFT → automated evals (groundedness, advice-boundary, hallucination, safety, regression)
      → human review (governance + compliance + research approval)
      → CANARY % → live analysis → PROMOTE | ROLLBACK
```
All transitions audited. A change cannot reach prod without passing gates + approvals.

## 5. Model routing & fallback (governed)
- Route by task→complexity→cost/latency tier (small→mid→large); plan-aware (Premium may unlock larger).
- Circuit breaker → fallback model on error/timeout; persistent failure → graceful degraded answer ("I can explain the factors but can't run a full comparison right now").
- Determinism where it matters: explainability uses low temperature + templated scaffolds.

## 6. Compliance coupling
- Prohibited-language classifier blocks advisory phrasing pre-render (compliance/recommendation-disclosure-framework).
- Disclaimers injected by the gateway (disclaimer-framework). Every AI output logged to recommendation_audit.
