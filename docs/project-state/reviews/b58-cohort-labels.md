# Review — B58 peer-cohort benchmark (degenerate scoring labels fixed)

**Change-id:** b58-cohort-labels
**Date:** 2026-06-09
**Branch:** `fix/b58-cohort-labels`
**Tier:** C (scoring / label logic — load-bearing path; inline review required this session)
**Decision driver:** B58 — every uploaded fund got an identical label (`on_track` or
`insufficient_data`) because the category-relative rule inputs were hardcoded `False`.
The "explainable, differentiated labels" value prop was inert.

## What changed

- `mf/cohort.py` (NEW, pure) — `CohortBenchmark` (per-category **median** of peers'
  1Y/3Y return + max-drawdown), `build_benchmark`, `compare_to_cohort` →
  `CategoryRelative`. A fund must beat / trail the cohort median by more than a
  `_MARGIN_PCT` (2.0pp) band to count as out/under-performing; inside the band it is
  "matching category" → `on_track`. `_MIN_COHORT_PEERS = 5` or the benchmark is
  withheld. All thresholds tagged `provisional_model` (B6/B28 activation gate).
- `mf/signals.py` — `CategoryRelative` dataclass; `long_horizon_stats` (1Y/3Y return +
  max-drawdown from a ≥3y series; 3Y requires a ≥900-day-old base point or stays None);
  `compute_fund_signals` gains an optional `category_relative` param that maps the
  booleans onto `FundSignals`. Momentum/risk axis path is **byte-for-byte unchanged**.
- `tasks/mf.py` — `_compute_cohort` (reads only `mf` schema: `MfFund` + `mf_nav_history`,
  ≥1200-day load), wired at both scoring call sites (CAS report + monthly rescore).
- `tests/unit/test_mf_cohort.py` (NEW) — benchmark medians/withholding, compare cases,
  3Y-history gating, end-to-end label flips to `in_form`/`off_track`, explainability notes.

Effect: the rule table can now emit `in_form`/`off_track`, not only `on_track`/
`insufficient_data`. `out_of_form` stays honestly unreachable (needs `structural_concern`,
a fundamentals signal not yet ingested). **No migration; no numeric reaches the client.**

## Deterministic gates

- ruff: clean. Full unit suite: **557 passed, 1 xfailed**. `ci_guards.py`
  (anti-pattern + secrets + IGNORE-list): passed. mypy: deferred to CI (not installed
  locally; advisory). Integration `test_mf_nav_scoring` needs Postgres → CI only.

## Tier-C review panel (independent agents, fanned out in parallel)

### Compliance (Opus) — **ACCEPT-WITH-CONDITIONS** (no BLOCKER)

All six non-negotiables PASS: (1) SEBI educational boundary held — the surfaced
`contributing`/`contradicting` strings are descriptive-comparative ("ahead of / behind
category peers"), no advisory verb, symmetric framing, never a call to action;
(2) no numeric in DOM — strings carry no numbers, `unified_score` server-side only;
(3) label from the rule table, not the score; (4) confidence NOT over-claimed — zero new
axes added, coverage unchanged, `partial_coverage` still caps at `medium`; (5)
`insufficient_data` floor unchanged; (6) `out_of_form` stays unreachable, documented
honestly.

- **Cond-1 (DONE):** the sustained-underperformance string read as 🔴 severity on a 🟠
  `off_track` label → reworded to escalation-free "also behind category peers over three
  years."
- **Cond-2 (DEFERRED):** pin the five approved educational phrasings into the
  anti-pattern grep corpus so a future mutation toward "outperformer/top/winner" trips the
  gate. Tracked B58-f1.
- **Cond-3 (DOCUMENTED):** `drawdown_controlled` uses `<=` (no margin) while returns use a
  ±margin band — intentional (makes `in_form` marginally easier); logged as a conscious
  provisional threshold under B6/B28.

### Architect (Sonnet) — **ACCEPT-WITH-CONDITIONS**

Module isolation PASS (cohort.py pure; `_compute_cohort` reads only `mf` schema, no
cross-module JOIN/INSERT). Dependency direction PASS (no cycle). Correctness PASS.

- **Cond-1 (DEFERRED, gated on Plus go-live):** monthly rescore calls `_compute_cohort`
  per-portfolio in a loop → re-fetches the same cohort dataset per portfolio. Harmless
  today (~0 Plus users; rescore skips non-Plus), but must hoist benchmark-build outside
  the loop before the rescore serves real Plus load. Tracked B58-f2.
- **Cond-2 (DEFERRED, gated on scale):** `mf_funds.category` has no index → seq scan on
  the peer-lookup `IN` query. Trivial on ~5k funds today; add `ix_mf_funds_category` +
  migration before the fund universe grows. Tracked B58-f3.
- **Cond-3 (DONE):** loop-var shadowing renamed (`cat, cat_isins`).
- **Cond-5 (DONE):** duplicate `long_horizon_stats` for targets removed via a
  `stats_by_isin` cache.

### Product (Sonnet) — **ACCEPT-WITH-CONDITIONS** (no launch-blocker)

Confirms B58 is genuinely fixed — real portfolios will show a mix of labels. Median peer
comparison is the right job-to-be-done for a retail user evaluating holdings. `in_form`
appropriately selective.

- **DONE:** thin-cohort funds now surface "category peer benchmark unavailable — too few
  comparable funds" instead of a silent `on_track`; strong young funds surface
  "three-year track record not yet established."
- **Cond-2 (DEFERRED):** the 2pp margin is effectively inactive for debt categories
  (sub-2pp dispersion) → near-universal `on_track`. Acceptable under `provisional_model`;
  make `_MARGIN_PCT` category-class-aware before a sizeable debt user base. Tracked B58-f4.
- **DOCUMENTED:** benchmark quality depends on AMFI taxonomy consistency (feature doc);
  `out_of_form` absence warrants a UI label-glossary note (UI layer). Tracked B58-f5.

## Ledger

| Gate | Status |
|---|---|
| Deterministic (tests · ruff · ci_guards) | ✅ green |
| Compliance (Opus) | ✅ ACCEPT-WITH-CONDITIONS — cond-1 done, cond-2/3 logged |
| Architect | ✅ ACCEPT-WITH-CONDITIONS — cond-3/5 done, cond-1/2 logged (scale-gated) |
| Product | ✅ ACCEPT-WITH-CONDITIONS — UX notes done, calibration logged |
| **Merge-eligible** | ✅ yes |
| **Deploy-eligible** | needs Phase-7 §5 log + explicit human approval (KVM4) |

Deferred follow-ups B58-f1..f5 filed in `BLOCKERS.md`. None gate merge; B58-f2 gates the
monthly rescore at Plus go-live.
