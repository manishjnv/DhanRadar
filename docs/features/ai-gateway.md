# Feature — AI / LLM Gateway

**Status:** core built (gateway orchestration + QualityValidator + AIOutputBase + budget governor); live model-id verification + Admin prompt-template sourcing deferred     **Phase:** Phase 3 (architecture §B3)
**Last updated:** 2026-06-06

## Purpose & scope

The single seam through which any module obtains LLM output. Domain modules call `OpenRouterGateway.complete(...)` and never touch a model, a budget counter, or a prompt directly. Every output is validated (structure + SEBI compliance) before it can reach a caller.

## Non-goals

- Hardcoding prompts or model ids — prompts/messages are passed IN (sourced from the Admin module's versioned `prompt_templates`); the free-model pool is operator-set (`AI_FREE_MODELS`) and verified live before use. No unverified `:free` literal lives in code.
- Computing scores — AI output is descriptive/explanatory only; the Rating Engine owns scores.
- Owning the Admin prompt-template store (later module) or the live model-verification job.

## Public interface

- `await OpenRouterGateway.complete(task_type, messages, schema, ticker=None) -> AIOutputBase`.
- `AIOutputBase` (extend per task): `confidence` (0–1), `confidence_band` (high/medium/low), `contributing_signals` (≥2; ≥3 if confidence>0.7), `contradicting_signals` (always carried), forced `disclaimer = "AI-generated insight, not investment advice"`.
- `QualityValidator(schema).validate(raw) -> AIOutputBase`.
- Errors: `CreditExhaustedError` (402), `ThreeStrikeSkipError`, `QualityValidationError`, `AllFreeModelsFailedError`, `BudgetExhaustedError`.

## Pipeline / behaviour

1. **Free pool, round-robin** within the free budget. `429` (RateLimitError) → rotate to next model immediately, **no sleep**. `402` → `CreditExhaustedError` (alert; **never** retried as a 429).
2. Each response → `QualityValidator`: schema (signal floor, band, forced disclaimer) **and** advisory-language screen (word-boundary; rejects `buy/sell/hold/switch/avoid/caution/strong buy/strong sell` as recommendations; `holding`/`buyer`/`household` are not false positives). The runtime twin of the static ci_guards advisory net (non-neg #1).
3. **Escalation** when the free pool yields no valid output: high-stakes task types (`mood_commentary`, `earnings_summary`, `stock_pick`, `mf_pick`) → **Sonnet spillover** within the premium budget; otherwise **3-strike-per-(ticker, day) skip**.
4. **Budget** enforced inside the gateway (`budget_guard`): free = call-count (cap 1000/day), premium = USD (soft $0.50, hard $9.50); daily UTC reset. A `BudgetMeter` records spend only on success — a 429/402/failed attempt consumes nothing.

## Config & flags

`OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `AI_FREE_MODELS` (csv, operator-set/verified), `AI_SONNET_MODEL` (default `anthropic/claude-sonnet-4.6`). `TASK_MODEL_PREFERENCES` injected per task (from Admin prompt templates).

## Dependencies

`openai` (OpenAI-compatible client → OpenRouter), Redis (budget + strike counters). No imports from auth/billing/scoring (module isolation). Consumes prompts from the Admin module (later); routed market data from the Market Data Adapter where relevant.

## Verification

`backend/tests/unit/test_ai_gateway.py` (7) + `test_budget.py` (14): 429→rotation (no sleep); 402→CreditExhaustedError (no retry); schema-fail on `stock_pick`→Sonnet spillover (+premium debit); schema-fail on `news_summary`→3-strike skip; advisory output rejected; `holding`/`buyer` not flagged; free success debits free budget by 1; premium debit by cost; no debit on exception. `ci_guards` green (the reject-list carries per-line `banned` markers).

## Known limitations / deferred

- `verify_models()` (live model-id check at openrouter.ai/models) and the Admin `prompt_templates` source are not wired — the gateway takes models/prompts as injected input today.
- Premium cost is a rough `tokens × blended $/1M` estimate for budgeting only, not a billing source of truth.
- A non-JSON response from the Sonnet spillover propagates a raw `JSONDecodeError` (free-pool path wraps it as a quality failure) — tighten when wiring real prompts.
- Cross-border check before routing user-specific data to non-Indian LLMs (DPDP) is a domain-module responsibility at call sites, not enforced here yet.

## Changelog

- 2026-06-06 — Module built (Phase 3 §B3): OpenRouterGateway (round-robin, 429-rotate, 402-alert, Sonnet spillover, 3-strike skip), AIOutputBase + QualityValidator (schema + advisory screen), budget governor increment (BudgetMeter). 21 unit tests. Built on Opus (Tier-B). Governance fan-out pending.
