# DhanRadar — Open Blockers & Deferred Items

Single register of deferred items. Each names the gate/phase it blocks. Clear an item only when
proven resolved (link the commit/RCA). New items get the next B-number.

| ID | Item | Blocks | Source | Status |
|---|---|---|---|---|
| B1 | Auth pytest suite written but never executed locally | green CI run | `docs/features/auth.md` | ADDRESSED — CI `backend` job runs pytest (PR+push); confirm green |
| B2 | `EXACT_PLAN_TIERS` empty (substring plan→tier fallback) | billing go-live | `reviews/prebilling-hardening.md` | ADDRESSED (code, merged) — substring foot-gun removed; unmapped plan → free + error (fail-safe). Real plan_id→tier values = data-only seeding at launch |
| B3 | `RequireConsent` is a pass-through stub | any DPDP data-processing route | `docs/features/auth.md` | ADDRESSED (gate primitive) 2026-06-05 (branch `hardening/b13-b10-ci-fe`) — `RequireConsent` now fail-closed: purpose validated against the canonical taxonomy at construction; grant read FRESH from `users.dpdp_consents` (no cache → revoke honoured immediately); missing/false/anonymous → 403 `consent_required` (`deps.py`). Unit-tested. **Remaining (later Consent module):** append-only `consent_audit_log`, grant/revoke endpoints, CMP banner, erasure, the 30-min cache **with** its flush-on-revoke writer |
| B4 | `deletion_requested_at` not enforced at auth | Consent/erasure module | `docs/features/auth.md` | ADDRESSED (login denial) 2026-06-05 (branch `hardening/b13-b10-ci-fe`) — `authenticate_user` denies a new session for an account with `deletion_requested_at` set (403 `account_deletion_pending`, after password verify so it is not an enumeration oracle; `auth/service.py`). Unit-tested. **Remaining (erasure module):** at the point it SETS `deletion_requested_at`, revoke the user's refresh jtis + flush `auth:tier:{uid}` so existing sessions die |
| B5 | No CI / commit hook — deterministic gates manual | enforced gates | `.github/workflows/ci.yml` | RESOLVED 2026-06-05 — CI runs `ci_guards.py` + secret scan + pytest + FE build on PR+push (local commit hook still optional) |
| B6 | Two-person scoring methodology gate not yet enforced | **production activation** of any `ranking_configs` version (NOT implementation) | `AI_GOVERNANCE_MODEL.md` §7.2 | OPEN (non-blocking until prod-readiness) |
| B7 | Razorpay `plan_id` conflation (catalog id passed as Razorpay plan id) | billing go-live | `reviews/prebilling-hardening.md` | ADDRESSED (code, merged) — `billing.plans.razorpay_plan_id` added (mig 0003); checkout fail-safes (503) until set. Real plan_ids = data-only seeding at launch |
| B8 | `_TOTAL_COUNT=12` hardcoded regardless of plan interval (annual ⇒ 12 years) | non-monthly plans go-live | `reviews/prebilling-hardening.md` | ADDRESSED (code, merged) — `billing.plans.total_count` added + used; checkout fail-safes if unset. Per-plan value = data-only at launch |
| B9 | Billing test/UX gaps: no 502-gateway-down test (no-double-charge unproven); `/billing/webhook` valid-event untested; plans-seed copy needs a Compliance pass; add `Retry-After:60` on the lock-held 409 | "done" on billing; billing go-live | `reviews/stage2-steps5-7-backend.md` | ADDRESSED (code/tests) 2026-06-05 (branch `hardening/b13-b10-ci-fe`) — `Retry-After: 60` added to the lock-held 409 (`billing/service.py`; RFC7807 handler forwards `exc.headers`); 502-gateway no-double-charge test (first attempt 502 + 1 gateway call, retry 409 + Retry-After + still 1 call) and valid-event test through the re-mounted `/billing/webhook` added (`tests/integration/test_billing.py`). **Remaining (data-only):** plans-seed copy Compliance pass — no seed exists yet; gate at billing go-live like B7/B8. Tests compile+collect locally; execute in CI (no local PG, per B1) |
| B10 | Frontend hardening: ESLint import-isolation is a fail-open N×N matrix; `NEXT_PUBLIC_API_URL` can strip `/api/v1`; ScoreRing aria split-model | before new feature slices | `reviews/stage2-steps2-4-frontend.md` | RESOLVED 2026-06-05 (branch `hardening/b13-b10-ci-fe`) — matrix replaced by generic `eslint-plugin-boundaries` rule (auto-covers all features incl. previously-uncovered `dashboard`/`mf`; clean-pass + planted-violation both verified); `apiClient` fails closed if `NEXT_PUBLIC_API_URL` ≠ `…/api/v1`; `ScoreRing` single accessible name via sr-only `<figcaption>` + decorative SVG. RCA logged |
| B11 | `concentration` risk sub-factor unweighted in `ranking_configs_v1` + `FINAL_SCORING_SPEC` §2.5/§6.1 internal inconsistency | scoring v1 activation | `reviews/stage2-step8-ranking-configs.md` | OPEN (architecture-owner decision) |
| B12 | `ci_guards.py` advisory detection too narrow (snake_case only) AND never scanned the token files | reliable enforcement of non-neg #1 | `reviews/prebilling-hardening.md` | ADDRESSED (merged) — broadened to camelCase/Title/spaced/quoted/key + now scans `tokens.json` + generated token files. Residual coverage gaps → B13 |
| B13 | `ci_guards.py` advisory coverage residuals: scans only 3 hardcoded non-code files (other `.json/.yaml/.html` label assets unscanned); `_ADV_SKIP` (`not`/`guard`) can mask a true positive; `"scoring" in p.parts` skips the whole scoring dir | reliable enforcement of non-neg #1 | `reviews/prebilling-hardening.md` | RESOLVED 2026-06-05 (branch `hardening/b13-b10-ci-fe`) — advisory scan now walks all `.json/.yaml/.yml/.css/.html`+config under `frontend/`+`backend/dhanradar/` (minus `node_modules/.next/__pycache__`); `_ADV_SKIP` tightened (anchored phrases, dropped bare `not`/`guard`); scoring skip narrowed to `ranking_configs*` files; `backend/tests/unit/test_ci_guards.py` self-test added. RCA logged |
| B14 | Cross-account webhook `plan_id` provenance (low; signature-gated): once `EXACT_PLAN_TIERS` is populated, optionally validate plan_id against a known-good set | billing go-live (residual) | `reviews/prebilling-hardening.md` | OPEN (low residual) |

## Notes

- **B6 is intentionally non-blocking for implementation.** Scoring-engine code and `ranking_configs`
  *staging* may proceed; the `approved_by ≠ created_by` methodology gate is enforced only before a
  version is **activated** in production. Track here until then.
- **B5 is RESOLVED** — `.github/workflows/ci.yml` enforces the deterministic plane on PR + push to
  `main` (`ci_guards.py` guards + secret scan, pytest, frontend build). **B12 ADDRESSED** (guard
  broadened + now scans token files); residual coverage gaps tracked as **B13**. Optional local
  `PreToolUse` commit hook still not wired.
- **B7/B8/B2 are code-ADDRESSED (merged) with fail-safes** — checkout refuses (503) and tier
  derivation grants nothing until the catalog is seeded with the REAL Razorpay plan ids +
  `total_count` + `EXACT_PLAN_TIERS`. What remains before charges is **data-only seeding** (await
  the Razorpay dashboard), not code. A charge/tier cannot be created from wrong config.
- **B11** is an architecture-owner decision (a `FINAL_SCORING_SPEC` §2.5/§6.1 reconciliation), gated
  to scoring v1 activation alongside B6.
