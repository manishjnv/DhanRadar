# Hallucination Detection, Grounding & Source Attribution

## Grounding (prevention)
- **RAG-only:** answers must be supported by retrieved internal context (hybrid: vector ANN + ES BM25, RRF). No open web.
- **Numbers from code:** any stat/score/price is injected from structured data into the prompt; the model is instructed it may only restate provided numbers, never compute/invent.
- **Context delimiting:** retrieved/user content is fenced and never treated as instructions (injection defense).

## Detection (post-generation, pre-render)
```
1. Claim extraction → match each claim to retrieved sources (NLI / verifier)
2. groundedness score; unsupported claim → block or strip + lower confidence
3. Numeric verifier: every number in output must exist in provided data → else block
4. Advice-boundary classifier: imperative/advice phrasing → block → safe template
5. Safety classifier: unsafe/toxic → block
```
- Fail → do not render; serve a safe fallback ("I can't verify that right now") + log.

## Source attribution
- Every output lists sources used (name, type, freshness) + confidence; user can inspect. Stale source → confidence penalty + visible caveat.

## Safety monitor (runtime, AI-Ops)
- Real-time: advice-boundary breaches, low-groundedness, unsafe content, hallucinated-number catches → flagged, blocked, queued for review; trend dashboards; alerts.
- Flagged outputs feed golden set (regression) and prompt/data fixes.

## Calibration
- Confidence reliability-curve validated continuously; % exposed to users only when within ±10% (launch gate).
