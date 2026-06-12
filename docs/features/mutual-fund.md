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

### Category-relative labelling (peer-cohort benchmark)

The peer-cohort benchmark is the per-category MEDIAN of 1Y/3Y return and max-drawdown computed
from existing AMFI NAV data in `mf_nav_history` — no new external source, no migration. Pure
module `dhanradar/mf/cohort.py` builds the benchmark; `dhanradar/mf/signals.py:long_horizon_stats`
derives the 1Y/3Y/drawdown inputs, and `compute_fund_signals` gained a `category_relative` param.
A fund maps to `in_form` when it beats the category median by more than the margin on both 1Y and
3Y return and `drawdown_controlled=True`; it maps to `off_track` when it trails the median by more
than the margin on 1Y return (`underperform_12m`); all other cases remain `on_track`. The
deterministic rule table lives in `dhanradar/scoring/engine/labels.py`.

**Category-class-aware margin (model v1.1, B58-f4).** The out/under-performance band is no
longer a flat 2pp. The AMFI category class (prefix before ` - ` in the full category string,
e.g. `"Debt Scheme"` from `"Debt Scheme - Banking and PSU Fund"`) sets the margin:
Debt Scheme 0.5pp · Hybrid Scheme 1.0pp · all other classes (Equity, Solution Oriented,
Other Scheme, unknown) 2.0pp. An unparseable or unrecognised class falls back to the default
2.0pp (wider = harder to flag = `on_track`, the fail-safe). The margin map is mirrored in
`ranking_configs_v1.json` (`labels.cohort_margin_pct`) and kept in lockstep by a
test (`test_margin_manifest_lockstep_with_config`). Shipped as `model_version v1.1`; ADR-0030;
registry activation row written at deploy.

A category needs ≥5 peers (each with a usable 1Y return) or the benchmark is withheld and
the fund stays `on_track` with an explainability note ("category peer benchmark unavailable")
— it does NOT become `insufficient_data` (that floor is reserved for a fund whose own NAV
history is too sparse to score). The 3Y return input additionally needs ≥~2.5 years of the
fund's own NAV history, else it is omitted (a young fund can never reach `in_form`).
The `out_of_form` label requires a `structural_concern` fundamentals signal not yet ingested
and is intentionally unreachable at this stage. Benchmark quality depends on AMFI category
taxonomy consistency — miscategorised funds upstream silently distort the peer median (a
known dependency). All thresholds are subject to the B6/B28 activation gate before production
use. No numeric score or factor weight reaches the client; labels remain non-advisory
(educational only, non-neg #1 and #2).

**Monthly-rescore cohort hoisting (B58-f2).** `_monthly_rescore` now calls
`_build_cohort_context` once per run over the union of all Plus portfolios' holdings, then
calls `_relative_from_context` (a pure dict lookup) per portfolio. Previously each portfolio
re-fetched the same category peer NAV sets independently. The single-portfolio CAS upload
path is unchanged — it still calls the `_compute_cohort` wrapper which builds and looks up
in one shot. A portfolio that turns Plus mid-run is absent from the pre-built union and
scores without category flags that month — the same honest fail-safe as an uncategorised fund.

## Changelog

- 2026-06-12 — B58-f4: category-class-aware cohort label band shipped as model v1.1 —
  Debt Scheme 0.5pp / Hybrid Scheme 1.0pp / default 2.0pp; AMFI class = prefix before
  ` - `; unknown class falls back to default wider band (fail-safe); manifest in
  `ranking_configs_v1.json` `labels.cohort_margin_pct` (lockstep test-enforced); ADR-0030;
  registry activation row written at deploy.
- 2026-06-12 — B58-f2: cohort context hoisted out of monthly-rescore per-portfolio loop;
  `_build_cohort_context` called once over union of Plus holdings; `_relative_from_context`
  is a pure lookup per portfolio; CAS path unchanged via `_compute_cohort` wrapper.
- 2026-06-06 — CAS→report slice built (Phase 5): consent-gated upload + SHA-256 dedup +
  <200ms enqueue; casparser-injectable parse; XIRR/allocation/overlap snapshot; Rating-Engine
  bridge → `user_fund_scores`; disclosure-injected, no-numeric report; 24h raw-file purge;
  Alembic 0004 mf schema. Snapshot math delegated to Sonnet (Opus-reviewed); compliance
  core + router on Opus (Tier-B).
- 2026-06-06 — Tier-B governance fan-out (Architect/Security/Compliance): 2 BLOCKERs +
  MAJ/MIN fixed in-branch — **per-user dedup key** (was a cross-user job_id leak), public
  `model_version` (no engine-internals), bounded upload read + PDF magic-byte check, CAS
  password off the Celery broker (ephemeral Redis), opaque error codes, migration CAGG orphan
  removed, `updated_at` on upsert. Residuals B26/B29/B30. 163 unit tests.
  Ledger: `reviews/phase5-mf-module.md`.
