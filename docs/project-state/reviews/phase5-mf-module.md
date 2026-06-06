# Review — Phase 5: Mutual Fund module, CAS → ≤60s report (branch `phase5/mf-module`)

## Gate ledger

**Tier:** B (CAS upload = DPDP data-processing / financial PII + consent) + A
(report surface) · **Class:** major · **Base:** `main` (post #11) · **Commits:**
`acb6def` (build) + condition fixes (this turn) · **Date:** 2026-06-06.

| Gate | Required by tier | Verdict | Reviewer |
|---|---|---|---|
| Deterministic (ci_guards + unit pytest + py_compile + markdownlint) | always | PASS (163 unit) | machine |
| Architect | always | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |
| Security (adversarial) | tier B | ACCEPT-WITH-CONDITIONS | Sonnet (independent; codex:rescue substitute) |
| Compliance | tier B | ACCEPT-WITH-CONDITIONS (no BLOCKER) | Opus (independent of builder) |

**Final status:** ACCEPT-WITH-CONDITIONS — 2 consensus BLOCKERs + the cheap
MAJOR/MINORs fixed in-branch; data/infra + header residuals tracked (B26/B29/B30).
Merge-eligible; NOT deploy-eligible (B26 audit write + B29 NAV pipeline + PC4/PC5).

## BLOCKERs — fixed this turn

- **[Security] Dedup cross-user leak** — `mf:cas:dedup:{hash}` had no user scope, so
  user B uploading identical CAS bytes received user A's job_id (a financial
  co-relationship leak). **Fix:** key is now `mf:cas:dedup:{user_id}:{hash}`
  (`service.dedup_key`); each user gets an independent job. Unit-tested.
- **[Architect] Engine internals access** — the task read `rengine._config.model_version`.
  **Fix:** added a public `RatingEngine.model_version` property; the task uses it
  (module isolation restored).

## MAJOR/MINOR — fixed this turn

- **[Security] Unbounded `file.read()` before the size check** → bounded read
  `file.read(_MAX_CAS_BYTES + 1)` caps memory; **PDF magic-byte** (`%PDF-`) check
  before touching disk.
- **[Security] CAS password on the Celery broker** → password is stashed in a
  short-lived Redis key (`mf:cas:pw:{job}`, 600s) the worker consumes-and-deletes;
  it is never a task argument (off the broker/result backend).
- **[Security] `error_message` echoed the raw exception** → opaque codes
  (`parse_failed` / `internal_error`) to the client; full detail logged server-side.
- **[Architect] migration orphan CAGG** → removed the `mf_nav_monthly_agg` downgrade
  step + docstring (CAGG lands with the NAV pipeline); hypertable step retained, guarded.
- **[Architect] `updated_at` never updated on upsert** → added `func.now()` to the
  `on_conflict_do_update` set_.
- **[Architect] consent gate manual call** → invoked with keyword args + comment
  (intentional, to preserve 401-before-403); the same fail-closed RequireConsent.

## Confirmed sound (reviewers)

DPDP consent enforced fail-closed BEFORE any file processing (B20 sense); raw file
purged in `finally` (success + failure) + 24h backstop; parsed PII only in the
user's own rows; IDOR clean (status/report scoped `user_id == current`, UUID jobs,
404-indistinguishable); path traversal impossible (server-uuid filename); **no
`unified_score`** in any MF response (asserted on serialized JSON); disclosure +
NOT_ADVICE injected unconditionally incl. empty/not-ready; non-advisory labels only;
no LLM/cross-border in the CAS path; erasure via `ON DELETE CASCADE` on all MF PII;
module isolation (no auth/billing internal imports).

## Tracked residuals (BLOCKERS) — NOT in this PR

- **B26** `ai_recommendation_audit` write `(label, model_used, disclaimer_version)` —
  the MF report is now a live caller owing this before deploy.
- **B29** MF data pipeline: AMFI NAV daily fetch (stub), `mf_funds` metadata seeding,
  `mf_nav_monthly_agg` CAGG.
- **B30** upload hardening: `Idempotency-Key` header (non-neg #6); transport-layer
  body-size cap; consent-on-read gap (documented intentional). MINOR.
