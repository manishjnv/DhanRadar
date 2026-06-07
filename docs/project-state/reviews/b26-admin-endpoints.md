# Review — B26 Admin module: compliance endpoints + two audit tables

## Gate ledger

**Tier:** B (load-bearing: compliance + admin-auth) · **Class:** major (admin-gated
disclaimer activation = a compliance state transition; two new audit tables) ·
**Branch:** `hardening/launch-gate-blockers` · **Date:** 2026-06-07.

**Artifacts:**

- `backend/alembic/versions/0008_admin_compliance_tables.py` — new migration (rev `0008`,
  down `0007`): the `rating_engine_changelog` and `ai_low_confidence_log` tables plus the
  `uq_disclaimer_active_per_type` partial-unique index, all in the `compliance` schema.
- `backend/dhanradar/models/compliance.py` — `RatingEngineChangelog`, `AiLowConfidenceLog`
  models; partial-unique index added to `Disclaimer`.
- `backend/dhanradar/compliance/service.py` — `create_disclaimer`, `activate_disclaimer`,
  `_snapshot_from_rows`, `label_churn_review`, `log_low_confidence`, `record_engine_changelog`;
  `DisclaimerConflictError`, `ActivationConflictError`.
- `backend/dhanradar/admin/{__init__,schemas,router}.py` — admin router (3 endpoints),
  all `Depends(RequireAdmin())`.
- `backend/dhanradar/main.py` — admin router registered at `/api/v1`.
- `backend/tests/unit/test_admin_compliance.py` (10), `backend/tests/integration/test_admin.py` (10).

| Gate | Required | Verdict | Reviewer/tier |
|---|---|---|---|
| Deterministic (pytest unit + ci_guards + py_compile) | always | PASS (19 admin unit; 10 integration collect; ci_guards 0; compile 0) | machine |
| Architect | always | self-note (interface-only coupling; reuses `governance.review_batch`) | orchestrator (Opus) |
| Compliance | tier B/C | ACCEPT (no advisory/numeric leak; allowlist enforced; activation version-tie intact) | orchestrator (Opus) |
| Security | tier B | **ACCEPT-WITH-CONDITIONS** (8 vectors; 2 conditions + 1 hardening — all applied in-session) | Sonnet takeover (codex n/a) |

## Design

- **Admin router** (`/api/v1/admin/...`): `POST /disclaimers` (create INACTIVE, conflict-guarded),
  `POST /disclaimers/{version}/activate` (single-active-per-type transition + R2 HTML snapshot +
  Redis cache flush), `GET /audit/label-churn` (reuses `governance.review_batch`, surfaces the
  >5% human-review gate to the operator). Every route is `RequireAdmin()`-gated → **404** to all
  non-admins (surface-hiding, inherited from the admin-auth foundation).
- **Module isolation:** the admin module orchestrates via `compliance.service` functions (no
  cross-module INSERT) and imports only the *pure* `scoring.engine.governance` churn functions
  (interface coupling). `compliance.disclaimers` is written only by `compliance.service`.
- **Activation durability:** the DB transition commits FIRST (source of truth); the R2 snapshot
  and Redis flush are best-effort after commit (a storage/Redis blip never rolls back a committed
  activation). The public disclaimer cache (`disclaimer:active:{type}`) is invalidated so
  `GET /disclaimers/{type}` serves the new version.
- **Two tables, no writer yet:** `rating_engine_changelog` is written by the B6/B28 two-person
  scoring-activation gate (slice 2); `ai_low_confidence_log` is written by the B22 confidence-floor
  consumer — both built ahead like B20's call site, with helpers ready.
- **Churn is a documented proxy:** keyed by served subject (user_id → session/request id) over the
  two most-recent UTC audit days, until a dedicated instrument-universe batch-snapshot table lands
  with B28 engine activation. It reuses the canonical thresholds (>5% → hold; 80% distribution cap).

## Security (independent, adversarial — Sonnet takeover; Codex unavailable) — ACCEPT-WITH-CONDITIONS

8-vector review (gate bypass/ordering; single-active invariant; activation durability vs
side-effects; compliance non-negotiables; churn correctness; injection/DoS; fire-and-forget
discipline; migration safety). **No admin-gate bypass, no advisory/numeric leak, no SQLi, HTML
snapshot escaped, fire-and-forget mirrors `record_served_label`, migration additive + reversible.**
Conditions, **all applied this session before commit**:

1. **Bound disclaimer `content`** (admin-only DoS against DB/R2/Redis on activation) →
   `create_disclaimer` rejects `> 65536` chars (`service.py`); unit + integration 400 test.
2. **Validate `recommendation_type` against the allowlist in `label_churn_review`** (an
   unrecognized/advisory type silently returned `insufficient_data` + `requires_human_review=False`
   — a fail-open signal) → now raises `ValueError` → router 400 (`service.py`/`admin/router.py`);
   unit + integration 400 test.
3. **(Non-blocking hardening, applied)** single-active invariant was app-layer only (concurrent
   two-admin activation TOCTOU) → added the `uq_disclaimer_active_per_type` partial-unique index
   (migration + ORM), and `activate_disclaimer` maps the losing commit's `IntegrityError` →
   `ActivationConflictError` → router **409**; integration test proves the index rejects a second
   active row.

## Final status

**ACCEPT** (all conditions applied in-session). Merge-eligible; not deploy-eligible until the
batched pre-deploy gate + human approval. **Remaining B26-admin:** the `rating_engine_changelog`
WRITER is wired by slice 2 (B6/B28 two-person scoring-activation gate); `ai_low_confidence_log` has
no AI consumer until B22.
