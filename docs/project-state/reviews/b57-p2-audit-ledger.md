# Review Ledger — B57 P2 Audit Ledger

Change-id: `b57-p2-audit-ledger` · Branch: `feat/b41-banners-b57-p2-audit-ledger` ·
Date: 2026-06-09

## Scope

New append-only `audit` schema with three monthly-RANGE-partitioned tables
(`admin_actions`, `payment_events`, `security_events`), per-row SHA-256 tamper
hash, fire-and-forget emit helpers, and call-site wiring. Implements
`LOGGING_PLAN.md` §3 + P2; §9 decisions honoured (per-row hash, keep UUID4
`request_id`).

- Migration: `backend/alembic/versions/0014_audit_ledger.py` (0014 → 0013 head)
- Models: `backend/dhanradar/models/audit.py`
- Service: `backend/dhanradar/audit/{__init__,service}.py`
- Call sites: `admin/router.py` (activate_disclaimer, activate_scoring_model),
  `subscriptions/service.py` (Razorpay webhook, post-commit),
  `auth/service.py` (refresh-reuse, TOTP lockout)
- Tests: `backend/tests/integration/test_audit_ledger.py` (6)

## Tier classification

Load-bearing paths touched: Alembic migration, `auth/`, payments. → **Tier B**
(Security) + **Tier C** (Compliance) + Builder + Architect. `codex:rescue`
unavailable on this account → Sonnet adversarial takeover (per project memory).

## Deterministic gates

- ruff (new/changed files): **PASS** (`All checks passed!`)
- secrets scan (diff): **PASS** (no literals)
- anti-pattern sweep (§0.3): **PASS**
- Integration + migration tests: **deferred to CI** (no local Postgres; CI is the
  gate). Reproducibility + fire-and-forget + PII-absence assertions present.

## Tier-C Compliance review (Opus) — ACCEPT

- DPDP: `security_events` stores `hash_user_ref(user_id)` as `user_ref`, never raw.
  `payment_events` stores raw `user_id` — justified (ADR-0022, SEBI 7-yr
  identifiable financial record). `admin_id` raw = staff, not end-user PII.
- No prompts/responses/raw bodies/PII-heavy data in the ledger (§3 honoured).
- No FK on any column → records survive DPDP erasure while meeting SEBI 7-yr
  retention (the coexistence requirement). Append-only by convention (matches
  `ai_recommendation_audit`); DB-level UPDATE/DELETE trigger logged as deferred
  hardening.
- Module isolation (non-neg #7): `audit` is standalone (imports only
  `core.logging`, `db`, `models.audit`, `redis_client`, stdlib). No SEBI advisory
  surface. **Verdict: ACCEPT.**

## Tier-B Security review (independent Sonnet adversarial) — ACCEPT-WITH-CONDITIONS → conditions applied

7-point attack pass (fire-and-forget integrity, PII leak, tamper-evidence,
append-only, migration safety, boot/import safety, admin-route change).

- Conditions (both applied in-session, `audit/service.py`):
  1. **PII (must-fix):** `record_payment_event` failure log put raw `user_id`
     (UUID) in the message string, bypassing value-regex redaction → now logs
     `user_ref=hash_user_ref(user_id)` via structlog kwargs.
  2. **Hash reproducibility (must-fix):** `_row_hash` used `str(ts)`, unstable
     across the `timestamptz` round-trip → now normalises `datetime` with
     `.isoformat()`. Keeps the CI reproducibility test green.
- Accepted residuals (documented, non-blocking): second-AsyncSession latency
  amplification under auth-flood (hardening: per-call timeout); row_hash is
  app-layer tamper-evidence only, not a defence against a DB-level attacker
  (hash-chain = deferred §9 upgrade); pg_partman `part_config` orphan rows on
  downgrade.
- **Verdict after conditions: ACCEPT.**

## Status

Code complete; deterministic gates green. **Merge-eligible pending CI** (migration
job + integration tests). **Deploy-eligible** only after CI green + merge to `main`
+ the alembic upgrade applied on KVM4 (separate human-approved deploy step).
