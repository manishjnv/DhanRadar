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
2. Each response → `QualityValidator`: schema (signal floor, band, forced disclaimer) **and** advisory-language screen (word-boundary; rejects the **core** recommendation set — `buy/sell/hold/switch/avoid/caution/strong buy/strong sell` plus `accumulate/book profit(s)/take profit(s)/square off/go long/overweight/underweight/top pick/buy the dip`; `holding`/`buyer`/`household` are not false positives). Complements (does not duplicate) the static ci_guards source-asset net (non-neg #1). The list is the core set, not exhaustive — a versioned, domain-expert-signed taxonomy is tracked (B23).
3. **Escalation** when the free pool yields no valid output: high-stakes task types (`mood_commentary`, `earnings_summary`, `stock_pick`, `mf_pick`) → **Sonnet spillover** within the premium budget; otherwise **3-strike-per-(ticker, day) skip**.
4. **Budget** enforced inside the gateway (`budget_guard`): free = call-count (cap 1000/day), premium = USD (soft $0.50, hard $9.50); daily UTC reset. A `BudgetMeter` records spend only on success — a 429/402/failed attempt consumes nothing.

## Config & flags

`OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `AI_FREE_MODELS` (csv, operator-set/verified), `AI_SONNET_MODEL` (default `anthropic/claude-sonnet-4.6`). `TASK_MODEL_PREFERENCES` injected per task (from Admin prompt templates).

## Dependencies

`openai` (OpenAI-compatible client → OpenRouter), Redis (budget + strike counters). No imports from auth/billing/scoring (module isolation). Consumes prompts from the Admin module (later); routed market data from the Market Data Adapter where relevant.

## Verification

`backend/tests/unit/test_ai_gateway.py` (7) + `test_budget.py` (21): 429→rotation (no sleep); 402→CreditExhaustedError (no retry); schema-fail on `stock_pick`→Sonnet spillover (+premium debit); schema-fail on `news_summary`→3-strike skip; advisory output rejected; `holding`/`buyer` not flagged; free success debits free budget by 1; premium debit by cost; no debit on exception. **B18 atomicity:** a real `asyncio.gather` race from one reservation of headroom admits **exactly one** caller (fails against the old check-then-act); a rejected call releases its reservation (counter never left inflated); a Redis failure on rollback does not mask the guarded block's own exception. `ci_guards` green (the reject-list carries per-line `banned` markers).

## Known limitations / deferred (tracked in BLOCKERS)

- `verify_models()` (live model-id check at openrouter.ai/models) and the Admin `prompt_templates` source are not wired — the gateway takes models/prompts as injected input today.
- Premium cost is a rough `tokens × blended $/1M` estimate for budgeting only, not a billing source of truth.
- **B20** — **ADDRESSED (defense-in-depth) 2026-06-07.** `complete()` now has a fail-closed default-deny contract: keyword-only `contains_personal_data=True` + `cross_border_consent_verified=False`; if a call carries personal data without verified consent it raises `ConsentNotVerifiedError` as its **first statement**, before any payload reaches OpenRouter. The gateway stays module-isolated (it cannot read consent), so the **call-site `assert_consent(user_id, "cross_border_ai", db)` is still owed** in the first AI-consuming module PR (Compliance-verified there) — but a forgetful consumer can no longer transfer PII by omission. Independent adversarial review ACCEPT. Ledger `reviews/b20-ai-callsite-gate.md`. **Call site WIRED 2026-06-07** by the MF commentary consumer (see Consumers; `reviews/ai-consumer-mf-commentary.md`).
- ~~**B18** — premium hard-cap is check-then-act (concurrent overshoot by ≤1 call); needs atomic Redis before scale.~~ **RESOLVED 2026-06-06** — `budget_guard` is now atomic **incr-then-rollback**: the per-call reserve is added with an atomic `INCRBYFLOAT` and admission keys off the pre-reservation value, so concurrent callers observe each other's reservations and at most one is admitted past the cap (the irreducible single-call cost). Reservation released on reject, rolled back on a failed call (best-effort so the real outcome is never masked), reconciled to actual spend on clean exit; a warning fires if a premium call's actual cost exceeds the reserve (`_PREMIUM_RESERVE_USD = $0.20`). **B19** — circuit breaker is in-process, not distributed.
- **B21** — **RESOLVED 2026-06-07.** `complete()` returns `CompletionResult(output, model_used)`; the MF commentary consumer writes `model_used` to `ai_recommendation_audit` via `record_served_label`. **B22** — **WIRED 2026-06-07** at the MF caller (pre- and post-call floor, NaN/inf-safe); still owed at any future consumer. **B23** — advisory list is the core set, full taxonomy + sign-off pending (the MF consumer adds a second defense-in-depth net over its published summary).

## Consumers

### MF report portfolio commentary

`dhanradar/mf/commentary.py` — `maybe_generate_commentary(...)` — is called from
`tasks/mf.py::_run_pipeline` after scoring and before report assembly. It uses the
`MfPortfolioCommentary(AIOutputBase)` schema (`summary` field); `PortfolioReport.commentary`
(optional) carries it through to the cached and served report.

`complete()` returns `CompletionResult(output, model_used)` (frozen dataclass); the consumer reads
`model_used` and writes it via `record_served_label(surface="mf_report_ai", ...)` into
`ai_recommendation_audit` — on the served path only (B21/B26). The audit write is wrapped so an
audit-layer failure never drops a clean, already-screened commentary.

Four gates wired:

- **B20** — `assert_consent(user_id, "cross_border_ai", db)` is the first statement; any
  `ConsentRequiredError` or DB error returns `None` (fail-closed). Data is minimized to
  `verb_label` / `confidence_band` / signals — ISIN, scheme name, folio, units, and amounts
  never leave.
- **B22** — confidence floor enforced twice: pre-call (no usable labels → `log_low_confidence`
  and omit) and post-call (model confidence < 0.30, `math.isfinite`-safe → omit).
- **B23** — two independent advisory nets: `quality.py` inside `complete()` plus a
  defense-in-depth regex over the published `summary` in the consumer.
- **B21/B26** — `model_used` recorded via `record_served_label` on the served path only; audit
  wrapped (serve + alert-on-failure posture).

Commentary is **non-blocking** — any refusal or failure omits it and the report still serves
(architecture §MF line 257). The served string is SEBI-disclaimer-postfixed
(`AI-generated insight, not investment advice`). In prod, commentary refuses until
`cross_border_ai` consent capture lands — the correct fail-closed behaviour. Mood Compass is the
trivial fast-follow (`contains_personal_data=False`).

## Changelog

- 2026-06-06 — Module built (Phase 3 §B3): OpenRouterGateway (round-robin, 429-rotate, 402-alert, Sonnet spillover, 3-strike skip), AIOutputBase + QualityValidator (schema + advisory screen), budget governor increment (BudgetMeter). Built on Opus (Tier-B).
- 2026-06-06 — Governance fan-out (Architect/Security/Compliance): 2 BLOCKERs + cheap MAJORs fixed — advisory list expanded (core set), high-stakes premium loop bounded by 3-strike, free counter debits every served call, atomic budget init, soft-cap warning, `model_copy` disclaimer guard, empty-choices guard, adapter `skipped` diagnostics. Residuals B18–B23 tracked. Ledger: `reviews/phase3-market-data-ai-gateway.md`. Now 30 tests across gateway/budget/market-data.
- 2026-06-07 — **B20 ADDRESSED (defense-in-depth)** — `complete()` gained a fail-closed default-deny cross-border contract (`contains_personal_data`/`cross_border_consent_verified` + `ConsentNotVerifiedError` raised first, before any OpenRouter payload); gateway stays module-isolated; call-site `assert_consent` owed in the first consuming PR. Independent adversarial review ACCEPT; 3 deny-path tests. Ledger `reviews/b20-ai-callsite-gate.md`.
- 2026-06-06 — **B18 RESOLVED** — `budget_guard` reworked from check-then-act to atomic **incr-then-rollback** (reserve → admit-on-pre-value → release/rollback/reconcile), closing the concurrent premium-hard-cap overshoot. Best-effort release/reconcile (`_adjust_quietly`) so a Redis blip never masks the caller's real outcome; warning when actual cost > reserve. Independent adversarial review (Sonnet takeover — Codex unavailable) ACCEPT-WITH-CONDITIONS; all 4 conditions applied (Redis-failure resilience, over-reserve warning, real `asyncio.gather` race test, Redis-rollback-failure test). 7 budget tests added (now 21). RCA 2026-06-06.
