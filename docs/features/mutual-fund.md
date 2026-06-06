# Feature — Mutual Fund Module (CAS → ≤60s report)

**Status:** CAS→report vertical slice built (upload→parse→snapshot→score→report) with consent gate, disclaimer, 24h purge; AMFI NAV pipeline + casparser lib + scheme metadata are data/infra-deferred     **Phase:** Phase 5 (architecture Tier-C MF Module)
**Last updated:** 2026-06-06

## Purpose & scope

The launch wedge: a logged-in user uploads a CAMS/KFintech CAS PDF and gets a labelled portfolio report in ≤60s. The module ingests holdings, computes analytics (XIRR, allocation, overlap), and consumes the Rating Engine's label per fund — it never renders UI and never recomputes the score.

## Non-goals

- No NSDL/CDSL equity CAS (casparser is CAMS/KFintech MF only — anti-pattern guard).
- Does not own the scoring algorithm (consumes the engine's published interface), nor consent flows (uses `RequireConsent`), nor UI.
- No buy/sell/rebalance output — labels are educational (non-neg #1); the unified score numeric never reaches a client (non-neg #2).

## Public interface (all under `/api/v1`)

- `POST /mf/upload/cas` — multipart (file + optional password). **Auth (401) then `RequireConsent("mf_analytics")` (403, B20)**. SHA-256 dedup → existing job on a repeat. Writes `mf_cas_jobs` queued, enqueues `mf.cas.parse`, returns `{job_id, estimated_seconds:60}` in <200ms (202).
- `GET /mf/cas/{job_id}/status` — own job only (IDOR-guarded): `{status, progress_pct, error_message}`.
- `GET /mf/report/{job_id}` — own job only: `PortfolioReport` (label + band per fund, portfolio facts, **disclosure injected, no unified_score**).

## Data / pipeline (architecture §MF)

Steps: (1) POST → SHA-256 → `mf:cas:dedup` → existing job on hit. (2) write `mf_cas_jobs` queued, persist raw file, enqueue, return <200ms. (3) worker `casparser.read_cas_pdf` (injectable) → walk `folios[].schemes[]`, keep ISIN rows (progress 40). (4) upsert `mf_user_holdings` (source=cas, progress 70). (5) snapshot: latest NAV (or CAS valuation) → current value, **XIRR (scipy brentq)**, category allocation, overlap. (6) per fund → Rating Engine `score()` → upsert `user_fund_scores`; cache report 2h (progress 100, done). (7) raw file deleted after parse; daily `purge_cas_files` is the 24h backstop.

Schema (`mf`): `mf_funds`, `mf_nav_history` (TimescaleDB hypertable, 1-month chunks), `mf_user_holdings`, `mf_portfolio_snapshots`, `mf_cas_jobs`, `user_fund_scores` (Alembic 0004; hypertable/CAGG guarded on the timescaledb extension).

## Dependencies

`casparser` (worker, lazily imported), `scipy` (XIRR), Redis (dedup + report cache + job state), the Rating Engine (`score()` interface), `RequireConsent`. Module isolation: `user_id` FKs `auth.users` for integrity; no cross-module table writes.

## Verification

`backend/tests/unit/test_mf_module.py` (12) + `test_mf_snapshot.py` (19): CAS parse normalization (ISIN filter, txns, parse-failure); SHA-256 dedup; report assembly injects disclosure + has NO `unified_score` (asserted on the serialized JSON); `FundSignals`/`FactorInputs` exclude `risk_profile`; holdings→snapshot NAV application + CAS fallback; XIRR/allocation/overlap; consent-gate wiring (`mf_analytics`). Full unit suite 162; ci_guards 0. The upload→status→report round trip + Celery worker run in CI/integration (no local Postgres/Redis/casparser — B1).

## Known limitations / deferred (tracked)

- **AMFI NAV pipeline** (`nav_daily_fetch`) is a stub — the AMFI `NAVAll.txt` fetch + hypertable bulk-upsert + targeted invalidation is the data pipeline, deferred. Without it, snapshots use the CAS-reported valuation and most funds score `insufficient_data` (honest, fail-safe).
- Scheme metadata (`mf_funds` category/expense) is not seeded → category in the snapshot is `uncategorized` and fund signals are thin until the metadata + NAV feeds land.
- `casparser` not installed in the local dev image (worker-only); the parse path is unit-tested via an injected reader.
- TimescaleDB continuous aggregate `mf_nav_monthly_agg` is named but not materialized in 0004 (created with the NAV pipeline).
- **B20** consent gate is enforced here; the **cross-border** check applies only when user data is sent to a non-Indian LLM — the CAS report core uses no LLM, so N/A for this path (a later "3-line why" enhancement would gate it).

## Changelog

- 2026-06-06 — CAS→report slice built (Phase 5): consent-gated upload + SHA-256 dedup + <200ms enqueue; casparser-injectable parse; XIRR/allocation/overlap snapshot; Rating-Engine bridge → `user_fund_scores`; disclosure-injected, no-numeric report; 24h raw-file purge; Alembic 0004 mf schema. Snapshot math delegated to Sonnet (Opus-reviewed); compliance core + router on Opus (Tier-B).
- 2026-06-06 — Tier-B governance fan-out (Architect/Security/Compliance): 2 BLOCKERs + MAJ/MIN fixed in-branch — **per-user dedup key** (was a cross-user job_id leak), public `model_version` (no engine-internals), bounded upload read + PDF magic-byte check, CAS password off the Celery broker (ephemeral Redis), opaque error codes, migration CAGG orphan removed, `updated_at` on upsert. Residuals B26/B29/B30. 163 unit tests. Ledger: `reviews/phase5-mf-module.md`.
