# Review — B26 Admin module: admin-authorization foundation (`RequireAdmin`)

## Gate ledger

**Tier:** B (new authorization primitive gating compliance-admin surfaces) · **Class:** major
(security foundation for the Admin module) · **Artifacts:** `backend/dhanradar/config.py`
(`ADMIN_USER_IDS` + `admin_user_ids`), `backend/dhanradar/deps.py` (`RequireAdmin`),
`backend/tests/unit/test_admin_auth.py` (8 tests) · **Branch:** `hardening/launch-gate-blockers`
· **Date:** 2026-06-07.

| Gate | Required | Verdict | Reviewer/tier |
|---|---|---|---|
| Deterministic (pytest + ci_guards) | always | PASS (8 admin-auth tests; ci_guards exit 0) | machine |
| Architect | always | self-note (right-sized) | orchestrator (Opus) |
| Security | tier B | **ACCEPT** (independent, adversarial — 8 vectors, no fail-open) | Sonnet takeover |

**Decision:** there is no admin tier/role in the DB. Per the operator's choice, admins are a
**config allowlist** (`settings.ADMIN_USER_IDS`, operator-set via env/secret) — simplest,
infra-controlled, no migration, fail-closed.

**Design (safe-by-default):** `RequireAdmin` returns **404 not_found** to EVERY non-admin —
anonymous OR authenticated non-admin — hiding the admin surface entirely (no 401-vs-403/404
oracle that the route exists or is admin-gated). Empty allowlist ⇒ no admins ⇒ all admin
endpoints disabled (mirrors `INTERNAL_API_TOKEN`). `user_id` is normalized via `str(UUID(...))`
on both sides; malformed allowlist entries are dropped (fail-closed); a non-string/`None`
`user_id` hits the `TypeError` branch → 404 (never a 500). Returns the admin `UserContext` so
endpoints can attribute actions (created_by / approved_by / activated_by).

**Final status:** ACCEPT. Foundation only — the admin HTTP endpoints (disclaimer create/activate +
HTML-snapshot-to-R2, label-churn + >5% gate), `rating_engine_changelog` and `ai_low_confidence_log`
tables are the next B26-admin steps, all built on `RequireAdmin`.

## Security (independent, adversarial — Sonnet takeover; Codex unavailable) — ACCEPT

8-vector review (bypass, empty/blank allowlist, UUID normalization false-pos/neg, garbage entry,
property freshness, 500-oracle, anon-vs-non-admin oracle, test quality). **No fail-open found.**
Conditions applied this turn:

- Operational note: `ADMIN_USER_IDS` is read at process start — adding/removing an admin needs a
  restart (documented in the config field comment). Fail-closed either way.
- Test added for a non-string `user_id` → 404 (TypeError branch coverage).
- The parse/normalize test now asserts the monkeypatch actually mutated the field (guards against a
  vacuous test if the field were ever made immutable).

## Tracked (next B26-admin steps)

- Admin router: `POST /admin/disclaimers` + `/{version}/activate` (+ HTML snapshot to R2 + cache
  flush), `GET /admin/audit/label-churn` (+ the >5% churn human-review gate; churn LOGIC already in
  `scoring/engine/governance.py`) — all `Depends(RequireAdmin())`.
- `rating_engine_changelog` table (ties to the B6/B28 activation gate) + `ai_low_confidence_log`
  table (no AI consumer writes it yet — like B20's call site).
