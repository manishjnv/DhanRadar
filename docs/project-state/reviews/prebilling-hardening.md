# Review — prebilling-hardening (B12 + B7/B8/B2), post-merge

## Gate ledger

**Tier:** B (billing/payments + auth tier derivation) + CI tooling · **Class:** major ·
**Scope:** B12 (`ci_guards.py` advisory broadening + token-file scan), B7/B8 (migration 0003 +
`billing.plans.razorpay_plan_id`/`total_count` + checkout fail-safe), B2 (`_derive_tier`
fail-safe) · **Date:** 2026-06-05.

**Landing note:** these changes were authored (commit `f466a74`) and reached `origin/main` by
riding in under the concurrent session's MF-screens PR (#6) — i.e. merged **without** the Tier-B
review the model requires. This is that post-merge review. A small follow-up fix (below) is on the
`hardening/prebilling-fail-safes` branch for PR.

| Gate | Required | Verdict | Reviewer/tier |
|---|---|---|---|
| Deterministic (ci_guards + py_compile) | always | PASS (guard green; compiles) | machine |
| Architect | always | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |
| Security | tier B | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |
| Compliance | tier B | ACCEPT-WITH-CONDITIONS | Opus (independent) |

**Final status:** ACCEPT-WITH-CONDITIONS — code is sound; 2 real MINORs fixed this turn, residuals
tracked (B13/B14). The fail-safes do what they claim: a charge cannot be created, and a paid tier
cannot be granted, with missing/unmapped config.

## Orchestrator adjudications (reviewer findings overridden with reasons)

- **Security [BLOCKER] "null-duplicate on `uq_plans_razorpay_plan_id`" → REJECTED (non-issue).**
  Postgres `UNIQUE` on a nullable column already permits multiple NULLs **and** enforces uniqueness
  on non-null values — exactly the intended semantics (many unconfigured plans; no duplicate real
  Razorpay ids). A partial index `WHERE … IS NOT NULL` would be functionally identical. No change.
- **Security [MAJOR] "cross-account plan_id collision" → DOWNGRADED to low residual (B14).** The
  Razorpay webhook secret is per-account and signature verification (verify-before-parse, upstream)
  already authenticates the source account; a foreign plan_id cannot arrive on a validly-signed
  event without the secret being compromised. Tracked as a documented residual, not a blocker.

## Fixed this turn (on the PR branch)

- **[MINOR, Architect/Security]** `not plan.total_count` → `plan.total_count is None` (and
  `razorpay_plan_id is None`): only an UNSET field means "unconfigured"; don't second-guess a real
  value (Razorpay rejects `total_count < 1` itself). `billing/service.py`.
- **[MINOR, Architect]** removed the stale `"Assumes billing.plans.id == the Razorpay plan id"`
  comment that contradicted the B7 fix (a maintainer could have "corrected" the code back).
  `billing/service.py`.

## Confirmed sound (all three reviewers)

- B7/B8 fail-safe is placed **before** the lock + the Razorpay call; passes the real
  `plan.razorpay_plan_id` and `plan.total_count` (not `plan.id` / a constant). Idempotency intact
  (lock TTL 60s > call timeout 25s; result cache plan-bound). Only the publishable key id returned.
- B2: substring heuristic removed; unmapped plan → `free` + `logger.error` (no privilege
  escalation, no silent under-grant). Module isolation preserved (subscriptions ⊄ billing).
- Migration 0003 additive + reversible; model matches.
- B12 broadened guard catches the slipped class (camelCase/Title/spaced/quoted/key) and now scans
  the token files; no PII in new logs; no advisory/guarantee copy added.

## Tracked follow-ups (BLOCKERS)

- **B13** — ci_guards coverage hardening: scan all non-code assets (`.json/.yaml/.css/.html` under
  `frontend/` + `backend/dhanradar/`, minus `node_modules`/`.next`) instead of 3 hardcoded token
  files; tighten `_ADV_SKIP` so a line containing `not`/`guard` can't mask a real advisory; narrow
  the `"scoring" in p.parts` skip to the `ranking_configs` files only.
- **B14** — cross-account webhook `plan_id` provenance residual (low; signature-gated): once
  `EXACT_PLAN_TIERS` is populated, optionally validate plan_id against a known-good set.
