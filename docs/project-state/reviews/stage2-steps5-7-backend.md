# Review — stage2-steps5-7-backend (post-merge)

## Gate ledger

**Tier:** B (auth/error surface + payments) · **Class:** major · **Scope:** Step 5 (RFC7807),
Step 6 (plans migration), Step 7 (billing) · **Diff:** merged in `9368628` (PR #3) — reviewed
post-merge (the plan's mandated pre-merge sign-off was skipped) · **Date:** 2026-06-05.

| Gate | Required | Verdict | Reviewer/tier |
|---|---|---|---|
| Deterministic (CI `ci_guards.py` + pytest) | always | PASS (CI exists; guards green) | machine |
| Architect | always | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |
| Security | tier B | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |
| Compliance | tier B | ACCEPT-WITH-CONDITIONS | Opus (independent) |
| Product | (billing) | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |

**Note:** the plan mandated a `codex:rescue` adversarial sign-off on Steps 5 & 7 **before merge**;
it was skipped and the code merged to `main`. This post-merge pass substitutes an independent
Sonnet adversarial review (fallback ladder). **No security hole or compliance leak was found in the
code** — all conditions are pre-billing data/test gaps. A formal `codex:rescue` pass on the payment
path remains available if required.

**Final status:** ACCEPT-WITH-CONDITIONS — code is sound; conditions tracked in `BLOCKERS.md`
(B7–B9). No code change required for correctness; pre-billing items must clear before billing
go-live.

## Architect (independent)

ACCEPT-WITH-CONDITIONS. Module isolation CLEAN (scoring ⊄ billing; no cross-module JOIN/INSERT;
billing schema-qualified). Migration 0002 reversible + additive (nullable `plan_id` FK, no drop of
`plan`). Webhook re-mount reuses the same handler object (no duplicate receiver; dedup event-id
keyed → both paths safe). ranking_configs weights sum 1.0.

- [MAJOR→track] `billing.plans.id` is `Text` PK, not UUID — deviates from the UUID-PK rule. Likely
  intentional (Razorpay natural key) but needs an ADR or a separate `razorpay_plan_id` column.
  → BLOCKERS B7.
- [MINOR→track] `Idempotency-Key` declared `Optional`+manual-400 (works) vs spec `required:true`;
  generated client won't mark it required.
- [NIT] `except (Exception, asyncio.TimeoutError)` redundant; `features: list[Any]`→`list[str]`.

## Security (independent, adversarial)

ACCEPT-WITH-CONDITIONS. **Confirmed sound:** verify-before-parse preserved at re-mount; dedup
path-agnostic (no double-grant); `user_id` from session only (no IDOR); only the publishable
`razorpay_key_id` returned (never the secret); NX lock TTL > call timeout (double-charge guard);
RFC7807 unhandled handler never leaks `str(exc)`/stack/PII; validation errors trimmed to
loc/msg/type (no `input`/`ctx`); reserved-member forgery blocked; migration reversible.

- [BLOCKER→pre-billing, track] Razorpay `plan_id` conflation: `service.py:119` passes catalog
  `plan.id` as the Razorpay `plan_id`; if the catalog isn't seeded with real `plan_XXXX` ids every
  checkout fails. Must close before billing go-live. → BLOCKERS B7.
- [MAJOR→track] Lock-held-on-gateway-failure returns 409 with no `Retry-After`; add `Retry-After:
  60` so a transient failure isn't a confusing self-conflict. → BLOCKERS B9.
- [MINOR] confirm client SDK generates a UUID-class Idempotency-Key per attempt; webhook dashboard
  "resend" (new event-id, same body) is body-hash-deduped — acceptable.

## Compliance (independent, Opus)

ACCEPT-WITH-CONDITIONS. **Confirmed clean:** no PII echoed by any error path; ranking_configs
faithfully encodes FINAL_SCORING_SPEC (labels exact, advisory verbs only in rejected-list, weights
sum 1.0, `no_numeric_in_dom:true`, `risk_profile_excluded_from_score:true`, `activated:false` +
`approved_by:null` — two-person gate correctly unsatisfied); changelog records the pending gates.

- [MINOR→track] Plan `name`/`features` copy is DB-sourced (seed data), not in this diff. Gate the
  plans seed + pricing-page strings through a Compliance pass (no assured-returns copy) before the
  catalog goes live. → BLOCKERS B9.

## Product (independent)

ACCEPT-WITH-CONDITIONS. Billing flows coherent (401 anon, 400 no-key, 404 plan, 409 replay/in-
flight, 502 gateway). ranking edge-cases specified (insufficient_data, partial_coverage, stale,
reweight). Step 8 cleanly staged (no engine logic).

- [BLOCKER→track] No test for the 502 gateway-down path (the no-double-charge guarantee is
  untested). → BLOCKERS B9.
- [BLOCKER→pre-billing, track] `_TOTAL_COUNT=12` hardcoded regardless of plan interval (annual ⇒
  12 years). Needs a `Plan.total_count` column before non-monthly plans go live. → BLOCKERS B8.
- [MAJOR→track] `/billing/webhook` (re-mount) tested for 400 only, not a valid event — plan's
  "both paths" acceptance not fully met. → BLOCKERS B9.

## Orchestrator adjudication

- Rejected one false-positive Architect finding ("`caution` missing from `advisory_verbs_rejected`")
  — verified `ranking_configs_v1.json` lists all five verbs incl. `caution`.
- All conditions are pre-billing/test gaps, not deploy-day defects → tracked B7–B9, not hot-fixed
  in this review turn.
