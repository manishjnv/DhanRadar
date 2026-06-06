# Review — consent-cross-border-primitive (B20/B31 foundation)

## Gate ledger

**Tier:** B (DPDP consent primitive) · **Class:** major (load-bearing compliance gate) ·
**Artifacts:** `backend/dhanradar/deps.py` (`cross_border_ai`/`cross_border_notify` purposes +
`consent_granted`/`assert_consent`/`ConsentRequiredError`), `tests/integration/test_consent_helper.py`,
ADR-0024 · **Branch:** `consent/cross-border-primitive` (off current `origin/main`) ·
**Date:** 2026-06-05.

| Gate | Required | Verdict | Reviewer/tier |
|---|---|---|---|
| Deterministic (py_compile + ci_guards; tests in CI) | always | PASS | machine |
| Architect | always | **self-note** (right-sized) | orchestrator (Opus) |
| Security | tier B | ACCEPT-WITH-CONDITIONS → conditions applied | Sonnet (independent) |
| Compliance | tier B | ACCEPT-WITH-CONDITIONS → MAJOR fixed | Opus (independent) |

**Right-sizing note:** a ~60-line additive primitive that reuses the already-reviewed fail-closed
reader (`_consent_granted`, landed in B3) with no schema/module-boundary change. The Architect
dimension is a documented self-assessment (additive helper, same DB-read pattern as
`RequireConsent`, no new tables, no cross-module import); the risk-bearing dimensions
(Security = does it fail open? Compliance = is the DPDP purpose model correct?) got independent
reviewers.

**Final status:** ACCEPT — the MAJOR is fixed; Security MINORs applied. Foundation only; the B20/B31
call-site wiring + the Consent-module grant/revoke writer are tracked follow-ups.

## Security (independent, adversarial)

**VERDICT: ACCEPT-WITH-CONDITIONS — "cannot make it fail open."** Every variant tried (`None`,
`False`, `"yes"`, `{}`, `{"granted": false}`, list, number, missing key, non-UUID, injection
string, unknown user) returns `False` or raises; unknown purpose raises `ValueError` before any DB
access; no cache (revoke honoured immediately); `ConsentRequiredError` is a plain non-HTTP
exception (worker-safe). Conditions (all **applied** this turn):

- [MINOR] `_UUID(str(user_id))` accepted odd inputs → **added an `isinstance(user_id, str)` guard**
  (fails closed on `None`/`True`/objects, mirrors `RequireConsent`).
- [MINOR] no `{"granted": False}` test → **added** `test_granted_false_dict_fails_closed`.
- [MINOR] unknown-user only tested via `consent_granted` → **added** an `assert_consent` raise case.
- [MINOR] revoke-format invariant unstated → **documented** in `_consent_granted` (writer must set
  `granted:false`/remove key, never add a `revoked` key that this reader would ignore = fail-open).

## Compliance (independent, Opus)

**VERDICT: ACCEPT-WITH-CONDITIONS → MAJOR fixed.** Confirmed: cross-border is correctly a concern
**distinct** from the processing purposes (folding into `ai_insights` would conflate a
processing grant with a transfer grant); fail-closed = no consent → no transfer; fresh read honours
revoke; `assert_consent` (refuse) vs `consent_granted` (skip) correctly maps to B20 vs B31.

- [MAJOR → **FIXED**] one bundled `cross_border_transfer` grant violated DPDP's specific-consent /
  no-bundling principle. **Split into per-processor `cross_border_ai` (B20) + `cross_border_notify`
  (B31).** Recorded in **ADR-0024**.
- [MINOR] architecture-doc purpose taxonomy lists only the 5 feature purposes (taxonomy drift) →
  ADR-0024 records the cross-border additions; single-sourcing the architecture prose is a tracked
  doc follow-up.

## Tracked follow-ups (for the B20/B31 wiring PRs)

- **B20 wiring:** call `assert_consent(user_id, "cross_border_ai", db)` (or skip) at the AI
  consuming call site; defense-in-depth guard in `complete()`; test "no grant → OpenRouter client
  never invoked."
- **B31 wiring:** gate the notification deliver seam on `cross_border_notify` fail-closed (skip
  channel + audit); test "no grant → Telegram/Resend client never invoked."
- **Consent-module WRITER** (grant/revoke + `consent_audit_log` + CMP) is still a stub (non-neg
  #10): until it lands, every user fails closed and the cross-border seams are inert for real users
  (safe). Sequence the writer before B20/B31 can function for real users.
- ADR index reconciliation (0021–0024).
