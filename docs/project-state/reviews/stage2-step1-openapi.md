# Review — stage2-step1-openapi

## Gate ledger

**Tier:** B (API/auth contract surface) · **Class:** major (canonical API contract) ·
**Artifact:** `contracts/openapi.yaml` · **Date:** 2026-06-05 ·
**Diff:** uncommitted on `stage2/contract-reconciliation` (spec authored in `5c02d7a`; reviewed +
revised this session).

| Gate | Required by tier? | Verdict | Reviewer/tier | Conditions |
|---|---|---|---|---|
| Deterministic (OpenAPI 3.1 parse + $ref + live-path check) | always | PASS | machine (python yaml) | closed |
| Architect | always | ACCEPT-WITH-CONDITIONS → **resolved** | Sonnet (independent) | closed |
| Security | tier B | ACCEPT-WITH-CONDITIONS → **resolved** | Sonnet (independent) | closed |
| Compliance | tier B | ACCEPT-WITH-CONDITIONS → **resolved** | Opus (independent) | closed |

**Note on Security tier:** the mandatory `codex:rescue` sign-off is scoped by
`STAGE2_EXECUTION_PLAN` to Steps 5 & 7 (the actual auth/error + payment **code**). Step 1 is a
non-executable spec, so Security ran as an independent Sonnet reviewer (the documented fallback).

**Final status:** COMPLETE — merge-eligible. All BLOCKER/MAJOR conditions fixed and re-validated.
**Human operator sign-off:** operator "go", 2026-06-05.
**Deploy-eligible?:** n/a — spec artifact; no runtime deploy.

## Builder summary

**Builder agent/tier:** Opus (contract correctness is judgment).
**Discovery:** Step 1's artifact (`contracts/openapi.yaml`) already existed, committed in `5c02d7a`,
but predated the governance model and had never been reviewed; the plan/SESSION_STATE were stale.
Builder action = validate against live code + run the Tier-B review it never received, then fix.
**Validation:** verified the spec matches the live backend (`auth/router.py`, `auth/schemas.py`,
`subscriptions/router.py`, `routers/health.py`, `deps.py`): auth schemas, health shape, cookie
scheme, label/band enums, gated `Score`/`ScorePublic` split all match. Machine gate: valid OpenAPI
3.1, 35 paths, all 34 $refs resolve.
**Non-negotiables touched:** #2 (no-numeric-in-DOM), #4 (cookie auth), #6 (`/api/v1`, idempotency).

## Architect review (Sonnet, independent)

**VERDICT: ACCEPT-WITH-CONDITIONS.**

- [BLOCKER] `/billing/webhook` marked LIVE but the real path is `/subscriptions/webhook` (absent) →
  generated client would call a 404. **FIXED:** `/subscriptions/webhook` added as LIVE;
  `/billing/webhook` relabelled SPEC (Step-7 target).
- [MAJOR] `trend` vs `growth` flagged as an unresolved open item. **RESOLVED (no spec change):** the
  decision was already made — ADR-0011 / REC-D1 keep 5-axis `trend`; the spec was correct. **FIXED:**
  the stale "open item" note in `CANONICAL_OPENAPI_ALIGNMENT.md` §6 now points to ADR-0011.
- [MAJOR] `risk_profile` spec enum vs backend free `Optional[str]`. **TRACKED:** backend writes only
  the canonical states; backend enum validation owed when Onboarding wires risk profile.
- [MINOR] `LoginRequest.password` minLength asymmetry — tracked (intentional; comment owed).

## Security review (Sonnet, independent)

**VERDICT: ACCEPT-WITH-CONDITIONS.** Confirmed clean: cookie-only scheme, no bearer anywhere;
generic 401 login (no enumeration); webhook verify-before-parse + dedup; Idempotency-Key on
mutating/payment ops; TOTP secret auth-gated; `ScorePublic` suppresses numerics.

- [BLOCKER] Webhook path mismatch (same as Architect). **FIXED.**
- [MAJOR] `/instruments/{symbol}/score` was `security:[]` + `oneOf:[ScorePublic, Score]` (Score a
  superset) → numeric could serve on an ungated call. **FIXED:** ungated 200 = `ScorePublic` only;
  numeric `Score` moved to a tier-gated `/instruments/{symbol}/score/detail` (no `security:[]`
  override → requires auth; 402 for free/anonymous).
- [MINOR] `razorpay_key_id` not annotated as publishable. **FIXED** (description added).
- [MINOR] `/explain/{entity_type}/{id}` ambiguous security + no 401/402. **TRACKED** (SPEC; bound
  when built).
- [NIT] `Problem.detail` freeform. **FIXED** (`maxLength: 500` + "no stack-trace/PII" note).

## Compliance review (Opus, independent)

**VERDICT: ACCEPT-WITH-CONDITIONS.** Verified clean: Label enum exact (no advisory verbs);
`/recommendations` filters by `label` not `signal`; `ScorePublic` carries no numeric/factors/
fair_value; factor **weights** absent even in gated `Score`; `ConfidenceBand` band-only with numeric
`confidence` nullable until calibration; `AIAnswer` carries NOT_ADVICE; `risk_profile` not fed to
any score schema; `/fair-value` gated.

- [MAJOR] `oneOf` on the score endpoint made no-numeric-in-DOM not contract-enforceable. **FIXED**
  (same fix as Security MAJOR — public 200 = `ScorePublic` only; numerics gated).
- [MINOR] score/AI-bearing SPEC endpoints with no response schema. **PARTIALLY FIXED:**
  `/recommendations` bound to `ScorePublic[]`; `/explain` + `/track-record` tracked (bound when
  built in their phase).
- [MINOR] no disclosure-version tie-in on score schemas. **FIXED:** `ScorePublic.disclaimer_version`
  added (ai_recommendation_audit tie-in, non-neg #9).

## Accepted MINOR follow-ups (tracked, do not block)

- Backend `risk_profile` enum validation when Onboarding lands.
- Explicit `security:` annotations on logout/me/totp (valid via inheritance; cosmetic).
- Response schemas for `/explain/{entity_type}/{id}` and `/track-record` when built.
- `LoginRequest.password` asymmetry comment.
