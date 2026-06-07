# Feature — Compliance Audit module

**Status:** built (audit-row linkage + disclaimer registry + archival + admin
disclaimer-management / label-churn gate / changelog + low-confidence tables) — table WRITERS
for `rating_engine_changelog` (B6/B28) and `ai_low_confidence_log` (B22) still pending ·
**Phase:** B26 (post-Phase-7) · **Last updated:** 2026-06-07

## Purpose & scope

The immutable SEBI/DPDP compliance backbone. Records every served rating-engine label
to a 7-year `ai_recommendation_audit` trail tying it to the exact disclaimer version in
force (non-neg #9 / B26), holds the disclaimer version registry, and archives the audit
to R2 for the 7-yr lifecycle. Records and gates; produces no content.

## Non-goals

- No user UI beyond the disclaimer text. No RIA logic.
- No advisory output can be audited as served — `recommendation_type` is a positive
  allowlist (non-neg #1).
- No RIA logic. The admin surface is operator-only (allowlist-gated, 404 to all others).
- Built in the Admin module (2026-06-07): admin disclaimer create/activate, the
  `rating_engine_changelog` + `ai_low_confidence_log` tables, and the label-churn
  human-review gate. Their WRITERS are still pending: `rating_engine_changelog` is
  written by the B6/B28 scoring-activation gate; `ai_low_confidence_log` by the B22
  confidence-floor consumer.

## Public interface (the only coupling surface)

- `GET /api/v1/disclaimers/{type}` — public, rate-limited, type-allowlisted; the active
  disclaimer for a type (e.g. `ai_recommendation`). 404 for unknown/inactive.
- `await compliance.service.record_served_label(...)` — fire-and-forget audit write,
  called at each served-label seam.
- `compliance.service.get_active_disclaimer(db, type)` / `active_disclaimer_version()`.

Consumers (caller writes): the MF module (`tasks/mf.py`, at report **generation**) and
the Notification module (`tasks/misc.py`, at successful **deliver**).

Admin surface (operator-only, `RequireAdmin()` → 404 to all non-admins;
`dhanradar/admin/router.py`, mounted `/api/v1/admin`):

- `POST /admin/disclaimers` — create a disclaimer version INACTIVE (conflict-guarded; body
  bounded to 64 KiB).
- `POST /admin/disclaimers/{version}/activate` — single-active-per-type transition (enforced
  atomically by the `uq_disclaimer_active_per_type` partial-unique index) → R2 HTML snapshot →
  flush `disclaimer:active:{type}`. Concurrent-activation loser → 409.
- `GET /admin/audit/label-churn` — reuses `scoring.engine.governance.review_batch` over the two
  most-recent audit days; surfaces the >5% human-review gate (`pending_publish`). Type is
  allowlist-validated (400 on a non-allowlisted/advisory type).

## Data

Postgres schema `compliance` (Alembic 0006):

- `disclaimers` — `version` (PK, globally-unique date-stamped id), `type`, `content`,
  `active`, `effective_from/to`. Seeded with the in-force `2026-06-06.v1`.
- `ai_recommendation_audit` — `(id, served_at)` composite PK; `user_id` (**no FK** — see
  retention below), `recommendation_type` (DB CHECK = allowlist), `label`, `content_hash`
  (SHA-256 of the served payload), `model`, `prompt_version`, `confidence_score/band`,
  `disclaimer_version` (denormalized NOT-NULL, **no hard FK**), `surface`, `session_id`,
  `request_id`, `created_at`. RANGE-partitioned monthly on `served_at` with a **DEFAULT
  partition** (an insert always lands) + guarded pg_partman 84-month retention.

Alembic 0008 adds two append-only tables (no writer wired yet):

- `rating_engine_changelog` — one row per scoring/rating methodology version change
  (factors before/after, methodology URL, `two_person_ok`, `activated`/`activated_at`);
  written by the B6/B28 two-person scoring-activation gate. Helper:
  `service.record_engine_changelog`.
- `ai_low_confidence_log` — one row per AI/scoring emission below the confidence floor;
  written by the B22 confidence-floor consumer. Helper: `service.log_low_confidence`
  (fire-and-forget, own session, never raises).

Redis `disclaimer:active:{type}` 1 h. R2 `audit/YYYY/MM/DD.jsonl.gz` (daily) +
`disclaimers/{type}/{version}.html` (immutable activation snapshot).

## Pipeline / behaviour

1. A served label (MF report generation / notification delivery) calls
   `record_served_label(...)` → one append-only audit row with `(label, model_used,
   disclaimer_version)`. The write opens its OWN DB session and swallows all errors so the
   serve path never breaks; `served_at` is server-set (no backdating).
2. The served surface stamps the SAME `disclaimer_version` (MF `PortfolioReport` field +
   footer; notification footer), so the user-visible output and the audit row provably
   carry the same version.
3. `archive_audit_daily` (Celery beat 02:00 IST, batch queue) exports the prior IST day's
   rows to R2 as gzip-JSONL; best-effort (rows stay in Postgres on failure).

## Config & flags

No new env. Uses `storage.py` (R2) + Redis + the in-force `DISCLAIMER_VERSION` from the
rating engine (compliance is the recording authority via `active_disclaimer_version()`).

## Failure modes & fallbacks

- Audit write fails → logged, swallowed, returns False (serve path unaffected). **B34:** the
  failure path now also bumps a best-effort daily Redis counter
  `metrics:compliance:audit_write_failures:{YYYYMMDD}` (`bump_audit_metric`, 35-day TTL,
  never raises) so a systemic audit outage is alertable.
- **Reconcile (B34):** `reconcile_audit_disclaimers` (beat 02:30 IST) flags any audited
  `disclaimer_version` not present in the `disclaimers` registry (a served label tied to an
  unregistered disclaimer = broken version tie); logs each orphan + bumps
  `metrics:compliance:audit_orphan_disclaimer_versions`.
- DEFAULT partition + denormalized `disclaimer_version` → a row is never lost to a missing
  monthly partition or a referential hiccup.
- Archival fails / R2 unconfigured → logged, rows kept in Postgres, next run retries.
- Disclaimer cache miss → Postgres; unknown type → 404 before any DB/Redis touch.

## Compliance & DPDP posture (read before go-live)

- **Non-neg #1:** `recommendation_type` is a positive DB allowlist (`educational_label`,
  `mood_regime`) + a service allowlist — no advisory verb can be audited as served.
- **7-yr retention vs DPDP erasure (accepted exception):** `user_id` carries no FK/CASCADE
  so the audit OUTLIVES a user erasure. The legal basis is the SEBI recordkeeping
  obligation (ADR-0022). The erasure module MUST skip this table and log the override.
  This means a `user_id` (DPDP personal data) is retained 7 years post-erasure — an
  intentional, documented exception, not a leak.
- **B34 (deploy gate — R2 residency, OPEN):** the R2 archival exports `user_id`; the bucket
  must be verified India-resident before archival is enabled (the archive is the 7-yr
  record-of-serving and must stay user-identifiable — the control is residency, not
  de-identification). This part is human/infra and remains a deploy gate. The two CODEABLE
  B34 items — the audit-write-failure metric and the disclaimer-version reconcile job — are
  **DONE 2026-06-07** (above).

## Dependencies

Consumes: `storage` (R2), Redis, the rating engine's in-force disclaimer version. Consumed
by: MF + Notification (via `record_served_label`). Build (boto3/S3).

## Verification

- `pytest tests/unit/test_compliance.py` (6: content_hash, allowlist refusal) +
  `tests/integration/test_compliance.py` (7: disclaimer GET 200/404, write happy-path,
  allowlist refusal returns False + zero rows, DB CHECK IntegrityError, archival → R2).
- `python scripts/ci_guards.py` + `scripts/anti_pattern_sweep.py`.

## Changelog

- 2026-06-06 — Module built (B26): `compliance` schema + Alembic 0006; audit table
  (partitioned, DEFAULT partition, 7-yr); disclaimers registry; fire-and-forget write +
  two caller seams (MF generation, notification deliver); public disclaimer endpoint;
  daily R2 archival; ADR-0022. Tier-B governance (Architect+Security+Compliance), all
  ACCEPT-WITH-CONDITIONS; MAJORs fixed in-branch (allowlist, version stamping, endpoint
  DoS, backdating). B26 ADDRESSED for the two shipped surfaces; B34 filed. Ledger:
  `reviews/b26-compliance-audit.md`.
- 2026-06-07 — **B26 Admin endpoints DONE:** admin router (`dhanradar/admin/`,
  `RequireAdmin()`-gated, 404 to non-admins) — `POST /admin/disclaimers`,
  `POST /admin/disclaimers/{version}/activate` (single-active transition + R2 HTML snapshot +
  cache flush; concurrent loser → 409), `GET /admin/audit/label-churn` (reuses
  `governance.review_batch`, >5% gate). Alembic 0008: `rating_engine_changelog` +
  `ai_low_confidence_log` (no writer yet) + `uq_disclaimer_active_per_type` partial-unique index.
  Tier-B review: Security ACCEPT-WITH-CONDITIONS (Sonnet takeover; codex n/a) — content bound +
  churn-type allowlist + atomic single-active index, all applied in-session. 10 unit + 10
  integration tests. Ledger `reviews/b26-admin-endpoints.md`.
- 2026-06-07 — **B34 codeable parts DONE:** `bump_audit_metric` daily Redis counter +
  audit-write-failure metric on the fire-and-forget failure path (`compliance/service.py`);
  `reconcile_audit_disclaimers` beat task (02:30 IST) flagging audited `disclaimer_version`s
  absent from the registry (`tasks/compliance.py`, `celery_app.py`). Right-sized
  (Builder+Architect; additive observability + read-only reconcile, no enforcement/auth/PII
  surface). +1 unit test, +2 integration tests (collect; run in CI). B34's R2-residency
  deploy gate remains OPEN (human/infra).
