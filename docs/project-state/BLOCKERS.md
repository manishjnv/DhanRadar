# DhanRadar — Open Blockers & Deferred Items

Single register of deferred items. Each names the gate/phase it blocks. Clear an item only when
proven resolved (link the commit/RCA). New items get the next B-number.

| ID | Item | Blocks | Source | Status |
|---|---|---|---|---|
| B1 | Auth pytest suite written but never executed | "done" on Auth; any deploy | `docs/features/auth.md` | OPEN |
| B2 | `EXACT_PLAN_TIERS` empty (substring plan→tier fallback) | billing go-live | `docs/features/auth.md` | OPEN |
| B3 | `RequireConsent` is a pass-through stub | any DPDP data-processing route | `docs/features/auth.md` | OPEN |
| B4 | `deletion_requested_at` not enforced at auth | Consent/erasure module | `docs/features/auth.md` | OPEN |
| B5 | No CI / commit hook — deterministic gates are manual | enforced gates (tests/secrets/anti-pattern + IGNORE grep) | governance deterministic plane | OPEN |
| B6 | Two-person scoring methodology gate not yet enforced | **production activation** of any `ranking_configs` version (NOT implementation) | `AI_GOVERNANCE_MODEL.md` §7.2 | OPEN (non-blocking until prod-readiness) |

## Notes

- **B6 is intentionally non-blocking for implementation.** Scoring-engine code and `ranking_configs`
  *staging* may proceed; the `approved_by ≠ created_by` methodology gate is enforced only before a
  version is **activated** in production. Track here until then.
- **B5** is the dependency the governance model's "machine gates first" principle assumes; until it
  lands, deterministic gates are run manually and reported in the Builder summary.
