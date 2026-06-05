# AI Eval, Safety & Cost Gates (F5, F13, F21)

## Release gates (every prompt/model version)
A version ships only if ALL pass on the eval suite:
- **Groundedness** ≥ 0.92 (claims supported by retrieved sources)
- **Advice-boundary** violations = 0 (no "you should buy/sell")
- **Hallucinated-number** rate ≈ 0 (numbers come from code, AI must not invent stats)
- **Safety** (unsafe/toxic) = 0
- **Regression** vs current live ≥ parity on a golden set

## Eval suite (CI + AI-Ops)
- Golden Q&A set per feature (search, explain, assistant, news, insights) with expected groundedness + boundaries.
- Automated nightly + on every prompt/model change; blocks promotion on failure (canary → analysis → promote/rollback).

## Safety monitor (runtime)
- Pre: prompt-injection filter + PII scrub. Post: advice-boundary + groundedness + unsafe classifier **before render**. Flagged → block + queue for review.

## Confidence calibration (F21)
- Maintain a **reliability curve**: bucket stated confidence vs realized accuracy; recalibrate weights monthly.
- **Do not expose the confidence %** to users until the curve shows calibration within ±10%. Until then show qualitative band only.

## Cost control (F13)
- Per-user (Free 5 AI/day), per-feature, and **global daily ₹ cap**. Breach → queue/degrade, never silent overspend.
- AI-Ops alerts: cost anomaly (>X% above 7-day avg), cache-hit-rate drop, model-mix shift, runaway loop.

## Launch gate (P0/P1)
- [ ] Eval suite green; gates wired to release
- [ ] Safety monitor blocking in prod
- [ ] Cost caps + alerts live
- [ ] Confidence shown only once calibrated
