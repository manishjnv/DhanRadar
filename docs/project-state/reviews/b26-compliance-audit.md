# Review — B26: Compliance Audit module (`ai_recommendation_audit` + caller writes)

## Gate ledger

**Tier:** B (audit/DPDP backbone holding user-linked label provenance; the write is
at compliance-critical seams). · **Class:** major · **Base:** `main` (post #15,
`6d3e43f`) · **Date:** 2026-06-06.

| Gate | Required by tier | Verdict | Reviewer |
|---|---|---|---|
| Deterministic (ci_guards + anti-pattern sweep + unit pytest + F-lint + compile) | always | PASS (224 unit; 7+6 new; integ collect) | machine |
| Architect | always | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |
| Security (adversarial) | tier B | ACCEPT-WITH-CONDITIONS | Sonnet (independent; codex:rescue substitute, fallback ladder) |
| Compliance | tier B | ACCEPT-WITH-CONDITIONS | Opus (independent of builder) |

**Final status:** ACCEPT-WITH-CONDITIONS — every cross-validated MAJOR fixed in-branch;
deploy-gated residual filed (B34). **B26 is now ADDRESSED** for the two shipped
served-label surfaces (MF report + notification deliver). Merge-eligible; not
deploy-eligible.

## What B26 delivers

- `compliance` schema + Alembic 0006: `disclaimers` registry (seeded with the in-force
  `2026-06-06.v1`) + `ai_recommendation_audit` — RANGE-partitioned monthly on `served_at`
  with a **DEFAULT partition** (an insert always lands — never lose an audit row) and a
  guarded pg_partman registration (84-month/7-yr retention, no-ops without the extension).
- `compliance.service.record_served_label(...)` — fire-and-forget, own-session, never
  raises; `get_active_disclaimer` (Redis-cached); `active_disclaimer_version()` authority.
- Caller writes: MF report at **generation** (once per fund, full provenance, `tasks/mf.py`)
  and notification at successful **deliver** (`tasks/misc.py`).
- `GET /api/v1/disclaimers/{type}` (public, rate-limited, type-allowlisted).
- `archive_audit_daily` (beat 02:00 IST) → gzip-JSONL to R2.

## MAJOR / MINOR — fixed this turn (in-branch, remediating the gate)

- **[Security MAJOR] denylist → positive allowlist** — `recommendation_type` was only
  blocked for the literal `buy_sell`; a caller could have audited `strong_buy` etc. Now an
  allowlist (`educational_label`, `mood_regime`) at BOTH the service and the DB CHECK
  (`ck_audit_recommendation_type`) — no advisory type can enter the trail (non-neg #1).
- **[Compliance MAJOR] disclaimer_version not on the served MF report** — added
  `disclaimer_version` to `PortfolioReport` + the cached report payload (sourced from the
  in-force version), so the served surface and the audit row carry the SAME version (§4
  tie-to-version).
- **[Compliance MAJOR] notification audited the live constant, not the served version** —
  the deliver seam now pins `disclaimer_version` from the job (generation-time), falling
  back to the **compliance** version authority — which also removed the
  notification→`scoring.engine.schemas` import (**Architect isolation finding**). Now uses
  ISIN + `confidence_band` from the job too (provenance symmetry with the MF seam).
- **[Security MAJOR] disclaimer endpoint DoS** — unique `{type}` values flooded Redis
  `disclaimer:active:{type}` keys. Now a `RateLimit(30/60s)` + a `_KNOWN_TYPES` allowlist
  validated BEFORE any DB/Redis access.
- **[Security MINOR] backdating** — `served_at` is no longer caller-supplied; it is always
  the server's `now()`, so an audit row cannot be misdated to a different in-force version.

## Adjudicated / deferred (documented, not fixed now)

- **B34 (NEW, deploy gate)** — the daily R2 archival exports `user_id` (a DPDP personal
  identifier); the R2 bucket jurisdiction (India-residency) must be verified before
  archival is enabled in production. **Do not pseudonymize the archive** — it is the 7-yr
  SEBI record-of-serving and must remain user-identifiable; the control is bucket
  residency, not de-identification.
- **7-yr `user_id` retention post-erasure** — intentional (SEBI recordkeeping is the legal
  basis; the audit outlives a DPDP erasure via no-FK/CASCADE). Recorded in ADR-0022 +
  the feature doc as an accepted retention exception the erasure module must honor.
- **Audit-write-failure observability** — fire-and-forget logs each failure but emits no
  metric; a systemic audit outage is not yet alertable (Observability module; noted).
- **Full §4 remainder (deferred to the Admin module):** admin `POST /disclaimers` +
  `/activate` + HTML-snapshot-to-R2; `rating_engine_changelog`; `GET /admin/audit/label-churn`
  plus the >5% churn human-review gate wiring; `ai_low_confidence_log`. The governance LOGIC
  already exists in `scoring/engine/governance.py`; only the admin plumbing is owed.
- **Archival format** — gzip-JSONL (no pyarrow dep) vs the architecture's parquet; a
  documented launch substitute.
