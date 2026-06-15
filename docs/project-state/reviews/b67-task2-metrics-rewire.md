# Review Ledger — B67 Task 2: MF Cohort Metrics Rewire

**Change ID:** b67-task2-metrics-rewire
**PR:** #121 (merged 2026-06-13, `326049e`)
**Tier:** C (scoring engine — load-bearing path)
**Reviewed:** 2026-06-15 (retroactive; code was live since 2026-06-13)
**codex:rescue:** n/a — companion MCP unavailable on this account; Sonnet adversarial takeover.

## What Changed

`_build_cohort_context` in `backend/dhanradar/tasks/mf.py` (lines 507–643) was rewired from
loading raw peer NAV series into Python memory at runtime to reading precomputed stats from
`mf_fund_metrics`. A nightly Celery task `mf_metrics_refresh` (00:15 IST) populates this table
by running the same `long_horizon_stats()` function on the same NAV data.

**Invariant:** scoring formula unchanged — only the data source changes. Same
`long_horizon_stats()`, same 1200-day lookback, same `FundStats` tuple type.

## Phase 0 Audit Findings

1. `mf/cohort.py` is pure math (zero DB access) — the DB loading layer was always in `tasks/mf.py`.
2. `mf_fund_metrics` columns `(return_1y_pct, return_3y_pct, max_drawdown_pct)` exactly match
   `FundStats = tuple[float|None, float|None, float|None]`.
3. `mf_metrics_refresh` is wired at `crontab(hour=0, minute=15)` in `celery_app.py` (before
   `compute_market_ranks` at 01:00 IST — correct dependency ordering).
4. Empty-table fallback (lines 649–672) replicates the old live-NAV math with `logger.critical`.
5. `_COHORT_PEER_CHUNK=200` is correctly repurposed for IN()-clause bind-param batching (not NAV
   loading). Equivalence test in `test_mf_cohort.py:277–307` confirms `chunk=3 == chunk=10_000`.
6. Observation 8528 ("B67 Task 2 not implemented") was a false negative — it audited
   `mf/cohort.py` (pure math) without reading `tasks/mf.py` where the DB load lives.

## Architect Review

**Agent:** Sonnet adversarial takeover (codex:rescue n/a)
**Verdict:** ACCEPT-WITH-CONDITIONS

### Conditions

**C1 (code) — Partial-miss silent gap:** `found_any=True` permanently skips the fallback even
for peers with no `mf_fund_metrics` row (new funds ingested today). These default to
`(None, None, None)` with no log line, silently skewing the category median.

*Applied:* Added `seen_isins` set and `logger.warning` in `_build_cohort_context` (lines 585,
601, 603–611) to emit count + sample ISINs when `found_any=True` but some peers have no row.

**C2 (doc) — `as_of` forward-compatibility trap:** `_metrics_refresh_pipeline` uses
`as_of=today`; the cohort fallback uses `as_of or date.today()`. Since `long_horizon_stats`
currently ignores `as_of` (windows anchor on latest NAV point), there is no live divergence.
But the next maintainer could wire `as_of` to anchor windows and silently break equivalence.

*Applied:* Comment added at `long_horizon_stats` call sites in both the refresh pipeline and
fallback branch explaining the current window-irrelevance and the reconciliation requirement if
`as_of` ever becomes window-sensitive.

### Dismissed

- Numerical equivalence: verified by `test_metrics_refresh_round_trip_is_bit_identical`; model
  uses `Float` (not `Numeric`) for bit-identity.
- Missing peer `→ (None,None,None)`: `long_horizon_stats([]) → (None,None,None)` confirmed at
  `signals.py:244`; `test_metrics_refresh_empty_series_yields_none_triple` asserts this.
- Beat schedule timing (45 min window): 28 chunks × bounded session is well within 45 minutes
  for 14k ISINs; no blocking defect.
- Session scope: per-chunk `TaskSessionLocal` is correct pattern for long tasks (avoids holding
  one connection open for minutes).
- `_COHORT_PEER_CHUNK` vs `_UPSERT_CHUNK`: correctly scoped to SELECT vs INSERT operations.

## Compliance Review

**Agent:** Sonnet adversarial takeover (codex:rescue n/a)
**Verdict:** ACCEPT-WITH-CONDITIONS

### Conditions

**C1 (compliance) — `return_1y_pct` in Fund Explorer API:**
Reviewer flagged serializing `return_1y_pct`/`return_3y_pct` to unauthenticated clients as a
non-neg #2 violation.

*Dismissed by Opus orchestrator:* MF Analytics Skill §18 explicitly states "factual performance
numbers (NAV/returns/XIRR/risk) MAY be displayed — the no-numeric-in-DOM rule applies to the
*proprietary score/weights/fair value*, not to factual data." `return_1y_pct = 18.5%` is a
factual NAV-derived 1-year return (identical category to what every AMFI-compliant fund platform
shows). It is not the proprietary `unified_score`, a factor weight, or a fair-value estimate.
`unified_score` is confirmed absent from all Fund Explorer responses (asserted by
`test_fund_explorer_item_has_no_unified_score`).

**C2 (code) — Partial-staleness warning (overlaps Architect C1):** Same condition.
*Applied:* See Architect C1 above.

**C3 (doc) — `as_of` fallback comment (overlaps Architect C2):** Same condition.
*Applied:* See Architect C2 above.

**C4 (filed) — Audit trail provenance:** `ai_recommendation_audit` rows do not record whether
cohort stats came from the precomputed path or the live-NAV fallback, or the `as_of_date` of the
precomputed metrics. Filed as **B72** in `BLOCKERS.md`.

### Dismissed

- SEBI boundary preserved: label set `{in_form, on_track, off_track, out_of_form,
  insufficient_data}` and `derive_label()` path unchanged; this change touches only the data
  source for the peer benchmark inputs.
- `insufficient_data` invariant: `nav_points < _MIN_POINTS → (None,None,None)` propagates
  identically through both paths; the `nav_points` column is diagnostic-only, not a decision gate
  here.
- `out_of_form` reachability: unchanged — still requires `structural_concern` which has no writer.
- Type contract: `FundStats = tuple[float|None, float|None, float|None]` preserved end-to-end.

## Final Verdict

**ACCEPT** — both conditions applied, Compliance C1 dismissed with documented justification, C4
filed to BLOCKERS.md.

The change correctly eliminates the B63 OOM root cause, preserves numerical equivalence, handles
the empty-table deploy regression, and correctly repurposes `_COHORT_PEER_CHUNK` for IN()-clause
batching. With C1 and C2 applied, the governance gap is closed.

## Gate Ledger

| Gate | Result |
|------|--------|
| Scoring formula unchanged | PASS — same `long_horizon_stats()`, same lookback, same FundStats type |
| `mf_nav_history` not dropped/altered | PASS — table untouched; still the write target for `nav_daily_fetch` |
| Missing metrics row → `(None,None,None)` | PASS — `row_map.get(i, (None,None,None))` default; confirmed equivalent to old empty-NAV path |
| Nightly refresh before scoring | PASS — `crontab(hour=0, minute=15)` before `crontab(hour=1, minute=0)` |
| `_COHORT_PEER_CHUNK=200` correctly repurposed | PASS — binds IN() queries; `_UPSERT_CHUNK` is the separate write constant |
| Empty-table fallback observable | PASS — `logger.critical` + partial-miss `logger.warning` added |
| Equivalence test | PASS — `test_mf_cohort.py:277–307` (chunked=3 vs oneshot=10k) |
| No `unified_score` in DOM | PASS — `test_fund_explorer_item_has_no_unified_score` asserts absence |
| Architect review | ACCEPT-WITH-CONDITIONS → conditions applied → ACCEPT |
| Compliance review | ACCEPT-WITH-CONDITIONS → conditions applied / dismissed → ACCEPT |
