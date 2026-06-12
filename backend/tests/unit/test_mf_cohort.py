"""
Unit tests for the MF peer-cohort benchmark + category-relative labels (B58).

These cover the fix for the degenerate-labels blocker: with a cohort benchmark the
rule table can now emit in_form / off_track (not only on_track / insufficient_data).

  * build_benchmark   — median aggregation + thin-cohort withholding.
  * compare_to_cohort — outperformer / underperformer / matching / no-benchmark.
  * long_horizon_stats — 3Y return requires genuine 3Y history.
  * end-to-end        — a cohort outperformer scores in_form, an underperformer
    off_track, through the published engine interface (the core B58 goal).

No DB / Redis / network. asyncio_mode = "auto" (pyproject.toml).
"""

from __future__ import annotations

import datetime

from dhanradar.mf.cohort import (
    CohortBenchmark,
    build_benchmark,
    compare_to_cohort,
)
from dhanradar.mf.scoring_bridge import score_fund
from dhanradar.mf.signals import CategoryRelative, compute_fund_signals, long_horizon_stats
from dhanradar.scoring.engine import RatingEngine, VerbLabel


# --- fakes (mirror test_mf_signals.py) ---------------------------------------
class _FakeHystStore:
    def __init__(self) -> None:
        self.d: dict = {}

    async def get(self, key):
        return self.d.get(key)

    async def set(self, key, state):
        self.d[key] = state


class _FakeResultStore:
    def __init__(self) -> None:
        self.d: dict = {}

    async def set(self, key, value, ex=None):
        self.d[key] = value


def _engine() -> RatingEngine:
    return RatingEngine(hysteresis_store=_FakeHystStore(), result_store=_FakeResultStore())


_AS_OF = datetime.date(2026, 6, 6)


def _daily_series(*, start_nav: float, daily_growth_pct: float, days: int, end: datetime.date):
    """Build a daily NAV series of ``days`` points ENDING at ``end`` (compounding)."""
    pts: list[tuple[datetime.date, float]] = []
    nav = start_nav
    for i in range(days):
        d = end - datetime.timedelta(days=(days - 1 - i))
        pts.append((d, round(nav, 4)))
        nav *= 1.0 + daily_growth_pct / 100.0
    return pts


# --- build_benchmark ---------------------------------------------------------
def test_thin_cohort_withholds_benchmark():
    # 4 peers (< _MIN_COHORT_PEERS=5) → medians withheld, even though data exists.
    stats = [(10.0, 30.0, 12.0)] * 4
    bm = build_benchmark("Large Cap", stats)
    assert bm.n_peers == 4
    assert bm.median_return_1y is None and bm.median_return_3y is None


def test_benchmark_medians_are_robust_to_outliers():
    # 5 peers; one 1Y outlier should not move the median off the central value.
    stats = [
        (8.0, 25.0, 10.0),
        (10.0, 30.0, 12.0),
        (12.0, 35.0, 14.0),
        (9.0, 28.0, 11.0),
        (999.0, 33.0, 13.0),  # outlier on 1Y only
    ]
    bm = build_benchmark("Large Cap", stats)
    assert bm.n_peers == 5
    assert bm.median_return_1y == 10.0  # central value, not dragged by 999
    assert bm.median_return_3y == 30.0


def test_benchmark_aggregates_each_window_independently():
    # A young peer with no 3Y still contributes its 1Y to the 1Y median.
    stats = [
        (10.0, 30.0, 12.0),
        (11.0, None, 13.0),  # young fund: no 3Y
        (9.0, 28.0, 11.0),
        (10.0, 32.0, 12.0),
        (10.0, 30.0, 12.0),
    ]
    bm = build_benchmark("Mid Cap", stats)
    assert bm.median_return_1y == 10.0
    # 3Y median computed over the 4 peers that HAVE a 3Y return.
    assert bm.median_return_3y == 30.0


# --- compare_to_cohort -------------------------------------------------------
_BENCH = CohortBenchmark("Large Cap", median_return_1y=10.0, median_return_3y=30.0,
                         median_max_drawdown=15.0, n_peers=20)


def test_no_benchmark_yields_all_false():
    cr = compare_to_cohort((50.0, 80.0, 5.0), None)
    assert cr == CategoryRelative()  # all False → on_track


def test_outperformer_sets_in_form_inputs():
    # Ahead on 1Y and 3Y by > margin, shallower drawdown than peers.
    cr = compare_to_cohort((18.0, 45.0, 9.0), _BENCH)
    assert cr.outperform_1y and cr.outperform_3y and cr.drawdown_controlled
    assert cr.underperform_12m is False and cr.sustained_underperformance is False
    assert any("ahead of category peers" in s for s in cr.contributing)


def test_underperformer_sets_off_track_input():
    # Behind on 1Y by > margin → underperform_12m drives off_track.
    cr = compare_to_cohort((4.0, 33.0, 20.0), _BENCH)
    assert cr.underperform_12m is True
    assert cr.outperform_1y is False
    # Behind on 1Y but ahead-ish on 3Y → not sustained.
    assert cr.sustained_underperformance is False
    assert any("behind category peers" in s for s in cr.contradicting)


def test_sustained_underperformer_flags_both_windows():
    cr = compare_to_cohort((3.0, 20.0, 25.0), _BENCH)
    assert cr.underperform_12m and cr.sustained_underperformance


def test_within_margin_is_matching_on_track():
    # Inside the ±margin band on both return windows, drawdown no better than peers
    # → no label-driving flag set → on_track.
    cr = compare_to_cohort((10.5, 29.5, 16.0), _BENCH)
    assert cr == CategoryRelative()


def test_drawdown_controlled_alone_does_not_flip_label():
    # Shallower drawdown but returns merely matching → drawdown_controlled True yet
    # the label stays on_track (in_form also needs 1Y+3Y outperformance).
    cr = compare_to_cohort((10.5, 29.5, 9.0), _BENCH)
    assert cr.drawdown_controlled is True
    assert cr.outperform_1y is False and cr.outperform_3y is False
    assert cr.underperform_12m is False


def test_young_fund_without_3y_is_never_in_form_input():
    # own 3Y None → outperform_3y False even when 1Y is strong.
    cr = compare_to_cohort((25.0, None, 8.0), _BENCH)
    assert cr.outperform_1y is True
    assert cr.outperform_3y is False  # no 3Y track record
    # Explainability: a strong young fund says WHY it cannot reach in_form.
    assert any("three-year track record not yet established" in s for s in cr.contributing)


def test_thin_benchmark_surfaces_explanation_not_silence():
    # A CohortBenchmark with withheld medians (thin cohort) → on_track, but the
    # report explains the cohort was too thin rather than implying a real match.
    thin = CohortBenchmark("Sectoral", median_return_1y=None, median_return_3y=None,
                           median_max_drawdown=None, n_peers=3)
    cr = compare_to_cohort((30.0, 50.0, 5.0), thin)
    assert cr.outperform_1y is False and cr.underperform_12m is False  # → on_track
    assert any("too few comparable funds" in s for s in cr.contributing)


def test_sustained_underperformance_phrasing_is_escalation_free():
    # The two-window underperformance must not read as the most-severe label, since
    # it maps to off_track (out_of_form needs a structural concern). (Compliance cond-1.)
    cr = compare_to_cohort((3.0, 20.0, 25.0), _BENCH)
    assert cr.sustained_underperformance is True
    joined = " ".join(cr.contradicting)
    assert "also behind category peers over three years" in joined


# --- long_horizon_stats ------------------------------------------------------
def test_three_year_return_requires_three_year_history():
    short = _daily_series(start_nav=100.0, daily_growth_pct=0.05, days=200, end=_AS_OF)
    r1, r3, dd = long_horizon_stats(short, as_of=_AS_OF)
    assert r1 is not None  # ~200 days supports a 1Y-ish return
    assert r3 is None      # but not a genuine 3Y return
    assert dd is not None


def test_long_series_supports_three_year_return():
    long = _daily_series(start_nav=100.0, daily_growth_pct=0.03, days=1200, end=_AS_OF)
    r1, r3, dd = long_horizon_stats(long, as_of=_AS_OF)
    assert r1 is not None and r3 is not None and dd is not None
    assert r3 > r1  # 3Y compounding exceeds 1Y for a steadily rising series


# --- end-to-end: cohort comparison flips the LABEL (the B58 acceptance) -------
async def test_cohort_outperformer_scores_in_form():
    pts = _daily_series(start_nav=100.0, daily_growth_pct=0.04, days=400, end=_AS_OF)
    cr = CategoryRelative(outperform_1y=True, outperform_3y=True, drawdown_controlled=True)
    sig = compute_fund_signals("INF_WINNER", pts, as_of=_AS_OF, category_relative=cr)
    result = await score_fund(_engine(), sig)
    assert result.verb_label == VerbLabel.in_form


async def test_cohort_underperformer_scores_off_track():
    pts = _daily_series(start_nav=100.0, daily_growth_pct=0.04, days=400, end=_AS_OF)
    cr = CategoryRelative(underperform_12m=True,
                          contradicting=["behind category peers over the trailing 12 months"])
    sig = compute_fund_signals("INF_LAGGARD", pts, as_of=_AS_OF, category_relative=cr)
    result = await score_fund(_engine(), sig)
    assert result.verb_label == VerbLabel.off_track


async def test_no_cohort_still_yields_on_track_not_in_form():
    # The pre-B58 behaviour is preserved when no benchmark is supplied.
    pts = _daily_series(start_nav=100.0, daily_growth_pct=0.04, days=400, end=_AS_OF)
    sig = compute_fund_signals("INF_PLAIN", pts, as_of=_AS_OF)
    result = await score_fund(_engine(), sig)
    assert result.verb_label == VerbLabel.on_track


# --- B63: peer NAV loads are chunked (memory-bounded), results unchanged ------
class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    """Serves the two _compute_cohort queries: target categories, then peers."""

    def __init__(self, cat_rows, peer_rows):
        self._results = [_FakeResult(cat_rows), _FakeResult(peer_rows)]

    async def execute(self, _stmt):
        return self._results.pop(0)


async def test_cohort_peer_load_is_chunked_and_equivalent(monkeypatch):
    # Loading ALL peers' 1200-day series at once OOM-killed the 640M worker on
    # the complete NAV dataset (B63). The fix loads peers in bounded chunks;
    # this asserts (a) no single load exceeds the chunk size and (b) the
    # category-relative output is byte-identical to the one-shot computation.
    from dhanradar.tasks import mf as tasks_mf

    peers = [f"INF{i:04d}" for i in range(7)]
    cat_rows = [(peers[0], "equity_mid")]
    peer_rows = [(i, "equity_mid") for i in peers]
    series = {
        i: _daily_series(start_nav=100.0, daily_growth_pct=0.02 + 0.005 * k, days=400, end=_AS_OF)
        for k, i in enumerate(peers)
    }

    batches: list[int] = []

    async def _fake_load(db, isins, lookback_days=400):
        batches.append(len(isins))
        return {i: series[i] for i in isins}, {}

    monkeypatch.setattr(tasks_mf, "_load_nav_series", _fake_load)

    monkeypatch.setattr(tasks_mf, "_COHORT_PEER_CHUNK", 3)
    chunked = await tasks_mf._compute_cohort(_FakeDb(cat_rows, peer_rows), [peers[0]], as_of=_AS_OF)
    assert batches and max(batches) <= 3  # every load bounded by the chunk size

    batches.clear()
    monkeypatch.setattr(tasks_mf, "_COHORT_PEER_CHUNK", 10_000)
    oneshot = await tasks_mf._compute_cohort(_FakeDb(cat_rows, peer_rows), [peers[0]], as_of=_AS_OF)
    assert batches == [len(peers)]  # one-shot control loaded everything at once

    assert chunked == oneshot  # identical math either way


# --- B58-f2: hoisted context build + pure lookup == one-call compute ----------
async def test_hoisted_context_lookup_matches_compute_cohort(monkeypatch):
    # The monthly rescore builds ONE _CohortContext per run and derives each
    # portfolio's label inputs by pure lookup; the result must be identical to
    # the single-call _compute_cohort path (which the CAS upload still uses).
    from dhanradar.tasks import mf as tasks_mf

    peers = [f"INF{i:04d}" for i in range(7)]
    cat_rows = [(peers[0], "equity_mid")]
    peer_rows = [(i, "equity_mid") for i in peers]
    series = {
        i: _daily_series(start_nav=100.0, daily_growth_pct=0.02 + 0.005 * k, days=400, end=_AS_OF)
        for k, i in enumerate(peers)
    }

    async def _fake_load(db, isins, lookback_days=400):
        return {i: series[i] for i in isins}, {}

    monkeypatch.setattr(tasks_mf, "_load_nav_series", _fake_load)

    direct = await tasks_mf._compute_cohort(_FakeDb(cat_rows, peer_rows), [peers[0]], as_of=_AS_OF)
    ctx = await tasks_mf._build_cohort_context(_FakeDb(cat_rows, peer_rows), [peers[0]], as_of=_AS_OF)
    hoisted = tasks_mf._relative_from_context(ctx, [peers[0]])
    assert direct  # non-empty — the comparison is real, not vacuous
    assert hoisted == direct

    # An ISIN unknown at build time is simply absent from the lookup result —
    # the downstream honest fail-safe (no category red flag → on_track).
    assert "INF_UNSEEN" not in tasks_mf._relative_from_context(ctx, ["INF_UNSEEN", peers[0]])

    # Empty targets short-circuit to the shared empty context.
    assert await tasks_mf._build_cohort_context(_FakeDb([], []), []) is tasks_mf._EMPTY_COHORT_CONTEXT


# --- B58-f4: the label band is category-class-aware (model v1.1) --------------
_DEBT_BENCH = CohortBenchmark(
    "Debt Scheme - Banking and PSU Fund",
    median_return_1y=7.0, median_return_3y=21.0, median_max_drawdown=2.0, n_peers=20,
)
_EQUITY_BENCH = CohortBenchmark(
    "Equity Scheme - Large Cap Fund",
    median_return_1y=10.0, median_return_3y=30.0, median_max_drawdown=15.0, n_peers=20,
)


def test_margin_is_category_class_aware():
    from dhanradar.mf.cohort import margin_pct_for_category

    assert margin_pct_for_category("Debt Scheme - Banking and PSU Fund") == 0.5
    assert margin_pct_for_category("Hybrid Scheme - Aggressive Hybrid Fund") == 1.0
    assert margin_pct_for_category("Equity Scheme - Large Cap Fund") == 2.0
    # Unknown / unparseable class → the conservative default band (on_track-leaning).
    assert margin_pct_for_category("Large Cap") == 2.0
    assert margin_pct_for_category("Solution Oriented Scheme - Retirement Fund") == 2.0


def test_debt_fund_one_pp_ahead_now_outperforms():
    # +1.0pp on both windows: INSIDE the old flat 2.0pp band (→ on_track forever),
    # OUTSIDE the 0.5pp debt band — the label can genuinely flip (RCA B58 lesson:
    # assert real flips, not just "a label exists").
    cr = compare_to_cohort((8.0, 22.0, 1.5), _DEBT_BENCH)
    assert cr.outperform_1y and cr.outperform_3y
    assert cr.drawdown_controlled  # shallower drawdown than the debt cohort median


def test_debt_fund_one_pp_behind_now_underperforms():
    cr = compare_to_cohort((6.0, 20.0, 3.0), _DEBT_BENCH)
    assert cr.underperform_12m and cr.sustained_underperformance


def test_debt_fund_within_half_pp_still_matching():
    cr = compare_to_cohort((7.3, 21.2, 2.5), _DEBT_BENCH)
    assert cr == CategoryRelative()  # inside the 0.5pp debt band → on_track


_HYBRID_BENCH = CohortBenchmark(
    "Hybrid Scheme - Aggressive Hybrid Fund",
    median_return_1y=9.0, median_return_3y=27.0, median_max_drawdown=10.0, n_peers=20,
)


def test_hybrid_fund_one_and_half_pp_ahead_now_outperforms():
    # +1.5pp on both windows: inside the old flat 2.0pp band, outside the 1.0pp
    # hybrid band — the hybrid label can genuinely flip both ways too.
    cr = compare_to_cohort((10.5, 28.5, 9.0), _HYBRID_BENCH)
    assert cr.outperform_1y and cr.outperform_3y


def test_hybrid_fund_one_and_half_pp_behind_now_underperforms():
    cr = compare_to_cohort((7.5, 25.5, 12.0), _HYBRID_BENCH)
    assert cr.underperform_12m and cr.sustained_underperformance


def test_equity_band_unchanged_at_two_pp():
    # +1.0pp for an equity fund stays inside the 2.0pp band — v1 behaviour is
    # bit-identical for equity categories (v1.1 changes debt/hybrid only).
    cr = compare_to_cohort((11.0, 31.0, 16.0), _EQUITY_BENCH)
    assert cr == CategoryRelative()


def test_margin_manifest_lockstep_with_config():
    # ranking_configs_v1.json carries the v1.1 margin manifest; the pure module's
    # constants must match it exactly (methodology versioning, B6/B28).
    import json
    from pathlib import Path

    from dhanradar.mf import cohort as cohort_mod

    cfg_path = (
        Path(cohort_mod.__file__).resolve().parents[1] / "scoring" / "ranking_configs_v1.json"
    )
    manifest = json.loads(cfg_path.read_text(encoding="utf-8"))["labels"]["cohort_margin_pct"]
    assert manifest["default"] == cohort_mod._MARGIN_PCT_DEFAULT
    assert manifest["by_class"] == cohort_mod._MARGIN_PCT_BY_CLASS
