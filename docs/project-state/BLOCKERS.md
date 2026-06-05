# DhanRadar — Open Blockers & Deferred Items

Single register of deferred items. Each names the gate/phase it blocks. Clear an item only when
proven resolved (link the commit/RCA). New items get the next B-number.

| ID | Item | Blocks | Source | Status |
|---|---|---|---|---|
| B1 | Auth pytest suite written but never executed locally | green CI run | `docs/features/auth.md` | ADDRESSED — CI `backend` job runs pytest (PR+push); confirm green |
| B2 | `EXACT_PLAN_TIERS` empty (substring plan→tier fallback) | billing go-live | `docs/features/auth.md` | OPEN |
| B3 | `RequireConsent` is a pass-through stub | any DPDP data-processing route | `docs/features/auth.md` | OPEN |
| B4 | `deletion_requested_at` not enforced at auth | Consent/erasure module | `docs/features/auth.md` | OPEN |
| B5 | No CI / commit hook — deterministic gates manual | enforced gates | `.github/workflows/ci.yml` | RESOLVED 2026-06-05 — CI runs `ci_guards.py` + secret scan + pytest + FE build on PR+push (local commit hook still optional) |
| B6 | Two-person scoring methodology gate not yet enforced | **production activation** of any `ranking_configs` version (NOT implementation) | `AI_GOVERNANCE_MODEL.md` §7.2 | OPEN (non-blocking until prod-readiness) |
| B7 | Razorpay `plan_id` conflation: catalog `plan.id` passed as the Razorpay plan id; `billing.plans.id` is TEXT PK (UUID-rule deviation — ADR owed) | billing go-live | `reviews/stage2-steps5-7-backend.md` | OPEN (pre-billing) |
| B8 | `_TOTAL_COUNT=12` hardcoded regardless of plan interval (annual ⇒ 12 years); needs `Plan.total_count` | non-monthly plans go-live | `backend/dhanradar/billing/service.py` | OPEN (pre-billing) |
| B9 | Billing test/UX gaps: no 502-gateway-down test (no-double-charge unproven); `/billing/webhook` valid-event untested; plans-seed copy needs a Compliance pass; add `Retry-After:60` on the lock-held 409 | "done" on billing; billing go-live | `reviews/stage2-steps5-7-backend.md` | OPEN |
| B10 | Frontend hardening: ESLint import-isolation is a fail-open N×N matrix; `NEXT_PUBLIC_API_URL` can strip `/api/v1`; ScoreRing aria split-model | before new feature slices | `reviews/stage2-steps2-4-frontend.md` | OPEN |
| B11 | `concentration` risk sub-factor unweighted in `ranking_configs_v1` + `FINAL_SCORING_SPEC` §2.5/§6.1 internal inconsistency | scoring v1 activation | `reviews/stage2-step8-ranking-configs.md` | OPEN (architecture-owner decision) |
| B12 | `ci_guards.py` advisory-verb regex too narrow (`strong_buy\|caution`, snake_case) — missed `strongBuy`/`Strong Buy`/`Hold`/`Avoid` in tokens.json | reliable enforcement of non-neg #1 | `docs/rca/README.md` (2026-06-05) | OPEN |

## Notes

- **B6 is intentionally non-blocking for implementation.** Scoring-engine code and `ranking_configs`
  *staging* may proceed; the `approved_by ≠ created_by` methodology gate is enforced only before a
  version is **activated** in production. Track here until then.
- **B5 is RESOLVED** — `.github/workflows/ci.yml` now enforces the deterministic plane on PR + push
  to `main` (`ci_guards.py` non-negotiable guards + secret scan, pytest, frontend build). **But B12**
  shows the guard has coverage gaps (it missed advisory verbs in `tokens.json`) — CI exists, but its
  guards still need broadening. An optional local `PreToolUse` commit hook is not yet wired.
- **B7/B8 are pre-billing** — billing code is merged and sound, but the Razorpay plan-id mapping and
  per-plan `total_count` must be corrected before real charges are enabled.
- **B11** is an architecture-owner decision (a `FINAL_SCORING_SPEC` §2.5/§6.1 reconciliation), gated
  to scoring v1 activation alongside B6.
