# Review — B20 AI gateway cross-border consent gate (defense-in-depth)

## Gate ledger

**Tier:** B (DPDP cross-border; AI gateway → OpenRouter, non-Indian) · **Class:** major
(load-bearing AI/consent path) · **Artifacts:** `backend/dhanradar/ai_gateway/gateway.py`
(`complete()` default-deny guard + params), `backend/dhanradar/ai_gateway/errors.py`
(`ConsentNotVerifiedError`), `backend/dhanradar/ai_gateway/__init__.py` (export),
`backend/tests/unit/test_ai_gateway.py` (3 new tests) · **Branch:**
`hardening/launch-gate-blockers` · **Date:** 2026-06-07.

| Gate | Required | Verdict | Reviewer/tier |
|---|---|---|---|
| Deterministic (pytest + ci_guards) | always | PASS (47 unit tests; ci_guards exit 0) | machine |
| Architect | always | self-note (right-sized) | orchestrator (Opus) |
| Security | tier B | **ACCEPT** (independent, adversarial) | Sonnet takeover |
| Compliance | tier B | folded into Security pass (DPDP purpose model already set in ADR-0024) | Sonnet/Opus |

**Right-sizing:** a ~12-line default-deny guard + a standalone error class, reusing the
already-reviewed `cross_border_ai` purpose (ADR-0024). The gateway is module-isolated (non-neg #7)
and cannot read consent itself, so the real enforcement is `assert_consent(user_id,
"cross_border_ai", db)` at the future consuming call site; this change is the gateway's
fail-closed backstop so a forgetful consumer cannot transfer PII cross-border by omission.

**Final status:** ACCEPT. No consumer exists yet, so B20 is **ADDRESSED (defense-in-depth)** — the
call-site `assert_consent` is owed (and Compliance-verified) in the first AI-consuming module PR.

## Codex availability

`codex:rescue` (the normal Tier-B adversarial gate) is **unavailable** — the linked ChatGPT account
lacks Codex model entitlement (hard HTTP 400 on every model). Per the approved fallback ladder
(global playbook), an **independent Sonnet** ran the adversarial pass.

## Security (independent, adversarial — Sonnet takeover) — ACCEPT

7-vector adversarial review (guard-first placement, default-deny, error-not-swallowed, module
isolation, wrong-default, message leak, test quality). **No real vectors.** Confirmed:

- The guard is the literal first statement in `complete()` (`gateway.py:138`), before
  `QualityValidator`, model selection, `budget_guard`, client construction, and any `_call` /
  `_spillover_to_sonnet` path. No alternate entry reaches OpenRouter.
- Default-deny: a bare `complete(...)` (both flags omitted) raises `ConsentNotVerifiedError`.
- `ConsentNotVerifiedError` subclasses `Exception`, **not** `GatewayError` — so no `except` in the
  free-pool loop or spillover can catch/convert it into a strike/spillover/credit path; it is also
  raised entirely outside every `try` block.
- No consent/db/auth import added (module isolation intact).
- Error `str()` carries only the purpose literal `cross_border_ai` — no user id / payload / PII.
- All 3 deny-path tests FAIL if the guard is removed or misplaced (positive controls).

**One trivial completeness note applied:** the no-consent test now also asserts the **premium**
budget counter is untouched (not just free), making the "no payload reached OpenRouter" proof
airtight.

## Tracked

- **B20 call-site enforcement** (`assert_consent` + `cross_border_consent_verified=True`) is owed in
  the first AI-consuming module PR (Mood AI commentary / MF AI pick), Compliance-verified there.
- **B31** (notification deliver seam) is RESOLVED separately — `tasks/misc.py` step-1b gate +
  `test_drain_skips_without_cross_border_consent`.
- The **Consent-module grant/revoke WRITER** is still a stub (non-neg #10): until it lands, every
  user fails closed and these seams are inert for real users (safe).
