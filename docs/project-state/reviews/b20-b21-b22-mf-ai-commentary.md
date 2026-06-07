# Review Ledger — AI MF Commentary (first AI-gateway consumer; B20/B21/B22 call sites)

- **Change-id:** `b20-b21-b22-mf-ai-commentary`
- **Branch:** `hardening/launch-gate-blockers`
- **Date:** 2026-06-08
- **Tier:** B (load-bearing: AI gateway + DPDP consent + compliance audit) — full inline review this session.
- **Build sequence:** item 5 (AI MF commentary). Tiering (PHASE 5M / DhanRadar Plus) is the NEXT item, deliberately NOT built here.

## What changed

The first real consumer of `OpenRouterGateway.complete()`. CAS→report pipeline now produces
governed, educational portfolio commentary, wiring the three call-site gates left for the first
consumer.

- `ai_gateway/gateway.py` (B21): `complete()` now returns `CompletionResult(output, model_used)`
  instead of a bare `AIOutputBase`; `_LLMResult` gained a `model` field; free-pool returns the
  loop model, spillover returns `res.model` (== `self._sonnet_model`). `CompletionResult` exported.
- `ai_gateway/__init__.py`: export `CompletionResult`.
- `mf/commentary.py` (NEW): `MFCommentary(AIOutputBase)` schema (+ `commentary` free-text field);
  `build_messages()` (PII-free prompt — no folio/user_id/raw rupee amounts, XIRR banded);
  `generate_commentary()` four-gate orchestration.
- `tasks/mf.py`: best-effort `ai_commentary` block in `_run_pipeline` (a failure never breaks the
  report — mirrors the fire-and-forget audit pattern).
- `tests/unit/test_mf_commentary.py` (NEW) + `tests/unit/test_ai_gateway.py` (return-type update).

## Infra that already existed vs. what was wired

- **Existed:** `assert_consent(user_id,"cross_border_ai",db)` (deps.py); gateway default-deny
  (`ConsentNotVerifiedError`); `record_served_label(...)`; `log_low_confidence(...)` +
  `ai_low_confidence_log` table (migration 0008); `budget_guard` (atomic incr-then-rollback, B18).
- **Wired (call site):** the consent assertion before any payload; `cross_border_consent_verified=True`
  on the gateway call; the `<0.30 → insufficient_data + log_low_confidence` floor; the served-label
  audit with `model=model_used`.
- **One gateway change:** surfacing `model_used` (B21) — the only piece not already built.

## Gate order (generate_commentary)

1. **B20 consent** — `assert_consent(...,"cross_border_ai",...)`; on refusal return `unavailable`
   WITHOUT building a payload or calling the gateway (gateway default-deny is the second line).
2. **Gateway call** — `task_type="mf_pick"`, `contains_personal_data=True`,
   `cross_border_consent_verified=True`. Gateway errors → `unavailable` (no audit).
3. **B22 floor** — `confidence < 0.30` → `log_low_confidence(...)` + return `insufficient_data`
   (no served-label audit on this path).
4. **B21 audit + serve** — `record_served_label(surface="mf_commentary", model=model_used,
   recommendation_type="educational_label", disclaimer_version=in-force, ...)`; return the public
   payload (band only — the raw confidence float is NEVER returned; non-neg #2).

## Deterministic gates

- `ruff` (E/F/I/UP): clean on all touched files.
- `anti_pattern_sweep.py`: passed. `ci_guards.py` (non-neg + secrets): passed.
- Secrets grep on diff: clean.
- Unit suite: 412 passed; the 2 `test_market_data` failures are the known pre-existing network
  (DNS) failures, unrelated. Touched-module tests: 34 passed.

## Acceptance proof

| # | Item | Proof |
|---|------|-------|
| 1 | Gateway call → educational commentary, QualityValidator (>=2 signals, no advisory) | `test_happy_path_returns_ok_payload` + `test_mf_commentary_advisory_text_rejected_by_quality_validator` |
| 2 | B20 deny path — refused BEFORE any payload reaches `complete()` | `test_consent_deny_never_calls_gateway` (asserts `gateway.calls == 0`) |
| 3 | B21 audit (label, model_used, in-force disclaimer_version) | `test_happy_path_*` asserts `record_served_label(model="glm-4.6-flash", recommendation_type="educational_label", surface="mf_commentary")` |
| 4 | B22 floor — `<0.30 → insufficient_data` + `log_low_confidence` | `test_confidence_floor_returns_insufficient_data` (log called, audit NOT) |
| 5 | Budget metered; over-budget skips, never overspends | `test_budget_exhausted_returns_unavailable` (consumer skips; no audit). Gateway-level atomic budget enforcement pre-tested in `test_ai_gateway.py` |
| + | never-raises contract (consent ValueError fails closed) | `test_consent_gate_value_error_fails_closed` |

## Security review (adversarial — Sonnet takeover)

`codex:rescue` **n/a** — codex companion unhealthy (latest job log: `400 'gpt-5' model not
supported on a ChatGPT account`, fail-fast). Independent Sonnet adversarial review per the
approved fallback ladder. **Verdict: ACCEPT-WITH-CONDITIONS.** Adjudication:

- **F1 (claimed blocker — `ValueError` from `assert_consent` falls through):** real severity lower —
  purpose is a hardcoded valid constant so `ValueError` is unreachable today, and even if raised the
  gateway is never reached (gate 1 precedes the call). Fixed anyway to honor the never-raises
  contract: gate 1 now catches `ValueError` → `consent_gate_error`, fail-closed. **Applied + tested.**
- **F4 (claimed blocker — `CreditExhaustedError` uncaught):** **not a bug** —
  `CreditExhaustedError(GatewayError)` is already caught by `except (GatewayError, ...)`. Added a
  clarifying comment listing the GatewayError subclasses.
- **F5 (should-fix — spillover audits `self._sonnet_model`):** switched to `res.model` (identical
  value, symmetric with the free-pool path, uses the threaded field). **Applied.**
- **F2 (nit):** documented the "advisory screen covers every string field" invariant on the schema.
- **F3 (numeric leak):** ACCEPT — float never returned on any path; prompt is PII-free.
- **F6 (nit — observability parity for `log_low_confidence`):** **deferred** — fixing it meant
  editing a load-bearing compliance file carrying 24 pre-existing `UP` lint findings for a nit;
  out of scope for this call-site slice. Tracked as a follow-up.

## Compliance review (Opus)

**Verdict: ACCEPT.** Non-neg #1 (advisory net screens commentary + signals; `educational_label`
allowlisted — no buy/sell/hold path), #2 (band-only; float never in the payload — all three return
paths verified), #4 (0.30 floor → refuse), #9 (disclaimer + in-force disclaimer_version on every
return path AND the audit row; same version both places), #10 (consent + gateway backstop), module
isolation (only ai_gateway + compliance + deps interfaces; no billing/scoring) all hold.

**Forward condition:** the FE must render the disclosure bundle + `NOT_ADVICE` from the carried
`disclaimer`/`disclaimer_version` — that is the later UI/tiering slice (item 6), not this backend
slice.

## Status

Merge-eligible (Tier-B inline ACCEPT / ACCEPT-WITH-CONDITIONS, conditions applied). NOT
deploy-eligible until the Phase-7 §5 pre-deploy gate + B48 consent re-enable + separate human
approval.
