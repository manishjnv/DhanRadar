# Feature — Compliance Audit module

**Status:** partial (audit-row linkage + disclaimer registry + archival built; admin
disclaimer-management / changelog / label-churn deferred to the Admin module) ·
**Phase:** B26 (post-Phase-7) · **Last updated:** 2026-06-06

## Purpose & scope

The immutable SEBI/DPDP compliance backbone. Records every served rating-engine label
to a 7-year `ai_recommendation_audit` trail tying it to the exact disclaimer version in
force (non-neg #9 / B26), holds the disclaimer version registry, and archives the audit
to R2 for the 7-yr lifecycle. Records and gates; produces no content.

## Non-goals

- No user UI beyond the disclaimer text. No RIA logic.
- No advisory output can be audited as served — `recommendation_type` is a positive
  allowlist (non-neg #1).
- Not the full §4 yet: admin disclaimer activation, `rating_engine_changelog`, the
  label-churn human-review gate, and `ai_low_confidence_log` are deferred (Admin module).

## Public interface (the only coupling surface)

- `GET /api/v1/disclaimers/{type}` — public, rate-limited, type-allowlisted; the active
  disclaimer for a type (e.g. `ai_recommendation`). 404 for unknown/inactive.
- `await compliance.service.record_served_label(...)` — fire-and-forget audit write,
  called at each served-label seam.
- `compliance.service.get_active_disclaimer(db, type)` / `active_disclaimer_version()`.

Consumers (caller writes): the MF module (`tasks/mf.py`, at report **generation**) and
the Notification module (`tasks/misc.py`, at successful **deliver**).

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

Redis `disclaimer:active:{type}` 1 h. R2 `audit/YYYY/MM/DD.jsonl.gz` (daily).

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

- Audit write fails → logged, swallowed, returns False (serve path unaffected). Residual:
  no failure METRIC yet (a systemic audit outage is not alertable — Observability module).
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
- **B34 (deploy gate):** the R2 archival exports `user_id`; the bucket must be verified
  India-resident before archival is enabled (the archive is the 7-yr record-of-serving and
  must stay user-identifiable — the control is residency, not de-identification).

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
