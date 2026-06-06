# Review — B31 notification cross-border consent gate

## Gate ledger

**Tier:** B (DPDP cross-border deploy-gate; notification PII → non-Indian processors) ·
**Class:** major · **Artifacts:** `backend/dhanradar/tasks/misc.py` (`_handle_job` step 1b),
`backend/tests/integration/test_notifications.py` · **Branch:** `consent/b31-notify-gate`
(off current `origin/main`, which has the consent primitive #18) · **Date:** 2026-06-06.

| Gate | Required | Verdict | Reviewer/tier |
|---|---|---|---|
| Deterministic (py_compile + ci_guards; tests in CI) | always | PASS | machine |
| Architect | always | self-note (right-sized) | orchestrator (Opus) |
| Security | tier B | ACCEPT-WITH-CONDITIONS → condition applied | Sonnet (independent) |
| Compliance | tier B | ACCEPT-WITH-CONDITIONS → condition applied | Opus (independent) |

**Right-sizing:** a ~15-line gate inserted into the existing drain flow, reusing the
already-reviewed `consent_granted` primitive (#18). Architect dimension is a self-note (no schema /
module-boundary change; the placement-before-transport is the only structural concern, verified).

**Final status:** ACCEPT — production gate sound; the one shared finding (a defective new test) is
fixed.

## Compliance (independent, Opus) — production PASS

**VERDICT: ACCEPT-WITH-CONDITIONS.** All compliance checks PASS on the production code:

- Gate (`misc.py:120`, step 1b) precedes BOTH `deliver_telegram` (154) and `deliver_email` (160) —
  no transport path bypasses it. `post_public_card` is anonymous broadcast (no per-user PII) —
  correctly out of scope.
- Fail-closed: no grant ⇒ `log_delivery(..., "cross_border_consent_required")` + drop (no retry —
  a retry would re-attempt the blocked transfer). Correct.
- Correct per-processor purpose `cross_border_notify` (ADR-0024, no-bundling); fresh read → revoke
  honoured immediately.
- Audit records an opaque code only — no chat_id/email/body leak.
- **Residual:** B31 closed for current transports (Telegram + email). WhatsApp is Y2; share-cards
  are generated, not transmitted here. Any future per-user channel MUST reuse this step-1b gate
  (tracked note).

## Security (independent, adversarial) — no bypass

**VERDICT: ACCEPT-WITH-CONDITIONS.** No delivery path reaches a transport without the consent
check (HIGH priority bypasses only quiet-hours, not the gate). On a DB error inside
`consent_granted`, `_drain`'s outer `except` drops the (already-popped) job — fail-closed
preserved, never re-delivered. Blocked job is dropped, not re-queued. No caching → revoke applies
next tick.

## Shared finding — FIXED this turn

- [MAJOR/MINOR] the new `test_drain_skips_without_cross_border_consent` referenced `misc` /
  `DeliveryResult` without the in-body imports the other drain tests have → it would `NameError`
  before asserting, leaving the negative proof unverified. **FIXED:** added
  `import dhanradar.tasks.misc as misc` + `from dhanradar.notifications.channels import DeliveryResult`
  to the test body. The two delivery-path tests were also updated to grant `cross_border_notify`
  (otherwise the gate would skip/break them — the quiet-hours test's re-queue assertion in
  particular).

## Tracked

- B20 (AI call-site) + the Consent-module grant/revoke WRITER remain (until the writer lands, every
  user fails closed → channels inert for real users, which is safe).
- `BLOCKERS.md` B31 status update + the "future channels reuse step-1b" note: deferred to the
  merger / a follow-up (BLOCKERS is edited by the concurrent session — left untouched here).
