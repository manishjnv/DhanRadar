# Review ledger — MF master-DB Task 2: mf_fund_metrics precompute + cohort rewire

Change-id: `mf-master-db-task2-fund-metrics`
Date: 2026-06-13
Builder: Claude (Fable 5) — implementation delegated to Sonnet (worktree), Opus design + line-by-line review + blocker fix.
Tier: **C** (scoring read path) — reviewed inline this session (load-bearing).

## What changed

- `mf.mf_fund_metrics` table (migration 0021) — precomputed per-fund long-horizon
  stats (`return_1y_pct`, `return_3y_pct`, `max_drawdown_pct` as **Float/float8**,
  `nav_points`, `as_of_date`, `computed_at`). isin PK; server-side only.
- `mf_metrics_refresh` Celery task + `_metrics_refresh_pipeline` — nightly (00:15 IST,
  after `nav_daily_fetch` 23:30) computes `long_horizon_stats` (reused verbatim) over
  all ISINs with NAV, in 500-fund chunks, idempotent upsert.
- `_build_cohort_context` rewired: step 3 reads precomputed metrics for the peer set
  instead of loading every peer's 1200-day NAV series into worker memory. Steps 1/2/4
  (category resolution, peer selection, `build_benchmark`) byte-unchanged. `cohort.py`
  untouched.
- Tests: an integration **equivalence oracle** (`test_mf_fund_metrics_refresh_equivalence`)
  + DB-free round-trip invariants + a fallback-equivalence test.

## Equivalence determination (the Tier-C gate)

**Label-EQUIVALENT — a pure performance/architecture refactor, NOT a scoring-model
change. The ADR-0026 activation gate does NOT apply (no methodology/version change).**
Rationale: the refresh stores exactly `long_horizon_stats(series, lookback=1200)`; the
cohort reads the tuple back; `build_benchmark`/`compare_to_cohort` are unchanged. Same
function, same NAV, same lookback → bit-identical `FundStats` → bit-identical medians +
labels. `Float`/`float8` round-trips Python floats exactly (Numeric would round) — proven
through the real DB in the integration test with strict `==` on benchmark medians and
per-fund `CategoryRelative`.

## Deterministic gates (my own runs, worktree)

- pytest: `test_mf_cohort.py` 31 pass (incl. fallback test) · `test_mf_signals` +
  `test_nav_ingestion` + cohort = 64 pass. Integration equivalence test runs in CI
  (needs Postgres).
- alembic: single head `0021` (chain 0020→0021).
- ruff: `tasks/mf.py` clean; remaining advisories are pre-existing `Optional[...]`/`I001`
  house style (identical to 0020), no new categories.

## Adversarial review (Sonnet takeover; codex n/a) — ACCEPT-WITH-CONDITIONS

Confirmed label-EQUIVALENT. Findings:

1. **BLOCKER — empty-table deploy regression.** On a fresh deploy `mf_fund_metrics` is
   empty until the first refresh → every benchmark withheld → silent `on_track` for all.
   **RESOLVED in-code:** `_build_cohort_context` now detects an empty table for the whole
   peer set and **falls back to the live NAV computation for that run** (the exact
   pre-refactor math — equivalent) with a `logger.critical` so a missed populate is
   observable, not silent. Tested (`test_cohort_falls_back_to_live_when_metrics_empty`
   asserts fallback == metrics path). PLUS the deploy runbook populates the table before
   the new code serves (below).
2. **should-fix — refresh error-swallow/no-retry.** Kept consistent with the existing
   `nav_daily_fetch` convention (no retry; re-runs next night; idempotent) — a failed
   refresh degrades to ≤24h-stale (still valid metrics, not empty → no label flip), and
   `logger.exception` is captured by the B38 Sentry wiring. Logged as a residual.
3. **nit — peer-set asymmetry** (mf_funds vs mf_nav_history): identical to the old path;
   comment added.
4. Numeric leak: NONE — `MfFundMetrics` is imported only by the task + model; not in any
   router/schema/serializer (server-side, like `unified_score`). Compliance: labels
   unchanged, no new numeric/advisory surface.

## Residuals (accepted, documented)

- Cross-day staleness: cohort reads ≤24h-old peer metrics. `return_1y/3y` (label-
  determining) are intraday-stable (latest NAV unchanged until the 23:30 fetch; refresh
  at 00:15 uses that NAV); `max_drawdown` can differ by a 1-day window slide but never
  independently flips a label (`compare_to_cohort` uses it only as a contributing
  signal). ~45-min window (23:30 fetch → 00:15 refresh) where a CAS run sees fresh own-
  NAV but day-old peers — negligible, low-traffic.
- Refresh failure → ≤24h-stale metrics (not wrong), observable via Sentry; no retry by
  convention.

## Deploy gate (MANDATORY ordering)

Additive migration + a populate step. Sequence: `git pull` → build fastapi+celery images
→ `alembic upgrade head` (creates `mf_fund_metrics`) → **run `mf_metrics_refresh` once to
populate** → bring up the new code (celery + fastapi) so the rewired cohort reads a
populated table. The in-code fallback covers the case if this is missed, but populate
first so the first scoring runs are fast (no live fallback).

## Status

- [x] Deterministic gates green (local; CI is the gate of record)
- [x] Tier-C adversarial ACCEPT-WITH-CONDITIONS → blocker resolved in-code + tested
- [x] Compliance: label-equivalent, no numeric leak (Opus)
- [ ] CI green on PR (pending)
- [ ] Deploy: alembic upgrade + populate + verify celery memory (pending)
