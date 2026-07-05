"""
Integration test (B29) — seed mf_funds + mf_nav_history → REAL label.

Proves the DB read path that the CAS pipeline uses:
  * NAV rows land in mf.mf_nav_history (the hypertable on a TimescaleDB box; a
    plain table built from ORM metadata on the CI test DB — the scoring path
    reads the table directly, NOT the continuous aggregate, so it is portable).
  * tasks.mf._load_nav_series reads them back as an ascending series.
  * signals.compute_fund_signals + scoring_bridge.score_fund turn that series
    into a label that is NOT insufficient_data — the core B29 acceptance.

Requires a reachable Postgres (settings.database_url). Run inside the compose
stack / CI; skipped collection-time elsewhere via the db_* fixtures.
"""

from __future__ import annotations

import datetime

from sqlalchemy import delete, insert

from dhanradar.mf.scoring_bridge import score_fund
from dhanradar.mf.signals import compute_fund_signals
from dhanradar.models.mf import MfFund, MfNavHistory
from dhanradar.scoring.engine import RatingEngine, VerbLabel
from dhanradar.scoring.engine.schemas import ConfidenceBand
from dhanradar.tasks.mf import _load_nav_series

_DEMO_ISIN = "INF_B29TEST01"
# Anchor to "today" so the seeded NAV window always sits inside _load_nav_series's
# now()-relative 400-day lookback. A fixed past date is a time-bomb: as real time
# advances, the earliest seeded row eventually ages out of the window and the row
# count drops below 14. The scoring outcome depends on the series SHAPE, not on
# absolute dates, so anchoring to today is behaviour-preserving and time-stable.
_AS_OF = datetime.datetime.now(datetime.UTC).date()


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


async def test_seeded_nav_history_scores_real_label(db_session, db_tables):
    # --- seed scheme metadata + ~14 months of monthly NAV --------------------
    await db_session.execute(
        insert(MfFund).values(
            isin=_DEMO_ISIN,
            amfi_code="999999",
            scheme_name="DhanRadar B29 Demo Fund - Growth",
            category="Equity Scheme - Large Cap Fund",
        )
    )
    nav = 100.0
    rows = []
    for i in range(14):
        d = _AS_OF - datetime.timedelta(days=30 * (13 - i))
        rows.append({"isin": _DEMO_ISIN, "nav_date": d, "nav": round(nav, 4), "source": "amfi"})
        nav *= 1.015
    await db_session.execute(insert(MfNavHistory).values(rows))
    await db_session.commit()

    try:
        # --- the real DB read path the CAS pipeline uses ---------------------
        series, latest = await _load_nav_series(db_session, [_DEMO_ISIN])
        assert _DEMO_ISIN in series and len(series[_DEMO_ISIN]) == 14
        assert latest[_DEMO_ISIN] == series[_DEMO_ISIN][-1][1]
        # Series is ascending by date (the loader's ORDER BY contract).
        dates = [d for d, _ in series[_DEMO_ISIN]]
        assert dates == sorted(dates)

        # --- signals → engine → REAL label -----------------------------------
        signals = compute_fund_signals(_DEMO_ISIN, series[_DEMO_ISIN], as_of=_AS_OF)
        engine = RatingEngine(hysteresis_store=_FakeHystStore(), result_store=_FakeResultStore())
        result = await score_fund(engine, signals)

        assert result.verb_label != VerbLabel.insufficient_data
        assert result.verb_label in {
            VerbLabel.in_form, VerbLabel.on_track, VerbLabel.off_track, VerbLabel.out_of_form,
        }
        assert result.confidence_band != ConfidenceBand.insufficient_data
    finally:
        # mf_funds / mf_nav_history have no FK to auth.users, so the db_session
        # teardown's CASCADE truncate does not reach them — clean up explicitly.
        await db_session.execute(delete(MfNavHistory).where(MfNavHistory.isin == _DEMO_ISIN))
        await db_session.execute(delete(MfFund).where(MfFund.isin == _DEMO_ISIN))
        await db_session.commit()


_PROV_ISIN = "INF_PROV0019"
_METRICS_ISINS = [f"INF_METRICS{i:02d}" for i in range(6)]
_METRICS_CATEGORY = "Equity Scheme - Large Cap Fund"
_METRICS_AS_OF = datetime.date(2026, 6, 13)


async def test_nav_insert_stamps_ingested_at_provenance(db_session, db_tables):
    """Migration 0019 / data-platform provenance: a NAV row inserted WITHOUT an
    explicit ingested_at is stamped by the column server default (now()) — the
    "when received" provenance is never left unknown for freshly-ingested rows."""
    from sqlalchemy import select

    try:
        await db_session.execute(
            insert(MfNavHistory).values(
                isin=_PROV_ISIN,
                nav_date=datetime.date(2026, 6, 6),
                nav=123.4567,
                source="amfi",
            )
        )
        await db_session.commit()

        row = (
            await db_session.execute(
                select(MfNavHistory).where(MfNavHistory.isin == _PROV_ISIN)
            )
        ).scalar_one()
        # Server default populated the ingestion wall-clock without us supplying it.
        assert row.ingested_at is not None
    finally:
        await db_session.execute(delete(MfNavHistory).where(MfNavHistory.isin == _PROV_ISIN))
        await db_session.commit()


async def test_mf_fund_metrics_refresh_equivalence(db_session, db_tables):
    """Tier-C equivalence oracle: mf_fund_metrics refresh → cohort-builder path
    produces bit-identical benchmarks and CategoryRelative outputs vs direct
    long_horizon_stats + build_benchmark (the old math).

    Seeds 6 funds in one category with enough 1Y history (some with 3Y), runs the
    reference computation, runs the refresh upsert, then calls the rewired
    _build_cohort_context and asserts exact equality on benchmarks + per-fund labels.
    """
    from sqlalchemy import func
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from dhanradar.mf.cohort import build_benchmark, compare_to_cohort
    from dhanradar.mf.signals import long_horizon_stats
    from dhanradar.models.mf import MfFundMetrics
    from dhanradar.tasks.mf import (
        _COHORT_LOOKBACK_DAYS,
        _build_cohort_context,
        _relative_from_context,
    )

    # --- seed mf_funds -------------------------------------------------------
    fund_rows = [
        {
            "isin": isin,
            "scheme_name": f"Test Fund {i}",
            "category": _METRICS_CATEGORY,
            # v1.2 (B66-f1 pt2): cohorts now group on the validated sebi_category.
            # _METRICS_CATEGORY is already a canonical SEBI leaf, so sebi == category.
            "sebi_category": _METRICS_CATEGORY,
        }
        for i, isin in enumerate(_METRICS_ISINS)
    ]
    await db_session.execute(insert(MfFund).values(fund_rows))

    # --- seed NAV history: 6 funds, varying history lengths ------------------
    # Funds 0-3: ~400 days (supports 1Y; no genuine 3Y).
    # Funds 4-5: ~1200 days (supports both 1Y and 3Y).
    nav_rows = []
    growth_rates = [0.04, 0.02, 0.06, 0.03, 0.05, 0.01]
    for fund_idx, isin in enumerate(_METRICS_ISINS):
        days = 1200 if fund_idx >= 4 else 400
        nav = 100.0
        for i in range(days):
            d = _METRICS_AS_OF - datetime.timedelta(days=(days - 1 - i))
            nav_rows.append({
                "isin": isin,
                "nav_date": d,
                "nav": round(nav, 4),
                "source": "amfi",
            })
            nav *= 1.0 + growth_rates[fund_idx] / 365.0
    await db_session.execute(insert(MfNavHistory).values(nav_rows))
    await db_session.commit()

    try:
        # --- REFERENCE: compute stats + benchmark the OLD way ----------------
        from dhanradar.tasks.mf import _load_nav_series

        ref_series, _ = await _load_nav_series(
            db_session, _METRICS_ISINS, lookback_days=_COHORT_LOOKBACK_DAYS
        )
        ref_stats = {
            isin: long_horizon_stats(ref_series.get(isin, []), as_of=_METRICS_AS_OF)
            for isin in _METRICS_ISINS
        }
        ref_benchmark = build_benchmark(
            _METRICS_CATEGORY, [ref_stats[i] for i in _METRICS_ISINS]
        )
        ref_labels = {
            isin: compare_to_cohort(ref_stats[isin], ref_benchmark)
            for isin in _METRICS_ISINS
        }

        # --- REFRESH: populate mf_fund_metrics (simulates the nightly task) --
        today = _METRICS_AS_OF
        upsert_dicts = []
        for isin in _METRICS_ISINS:
            r1, r3, dd = long_horizon_stats(
                ref_series.get(isin, []), as_of=today
            )
            upsert_dicts.append({
                "isin": isin,
                "return_1y_pct": r1,
                "return_3y_pct": r3,
                "max_drawdown_pct": dd,
                "nav_points": len(ref_series.get(isin, [])),
                "as_of_date": today,
            })
        stmt = pg_insert(MfFundMetrics).values(upsert_dicts).on_conflict_do_update(
            index_elements=["isin"],
            set_={
                "return_1y_pct": pg_insert(MfFundMetrics).excluded.return_1y_pct,
                "return_3y_pct": pg_insert(MfFundMetrics).excluded.return_3y_pct,
                "max_drawdown_pct": pg_insert(MfFundMetrics).excluded.max_drawdown_pct,
                "nav_points": pg_insert(MfFundMetrics).excluded.nav_points,
                "as_of_date": pg_insert(MfFundMetrics).excluded.as_of_date,
                "computed_at": func.now(),
            },
        )
        await db_session.execute(stmt)
        await db_session.commit()

        # --- REWIRED PATH: _build_cohort_context reads mf_fund_metrics -------
        ctx = await _build_cohort_context(
            db_session, _METRICS_ISINS, as_of=_METRICS_AS_OF
        )
        new_labels = _relative_from_context(ctx, _METRICS_ISINS)

        # --- ASSERT: benchmarks are bit-identical ----------------------------
        new_bm = ctx.benchmarks.get(_METRICS_CATEGORY)
        assert new_bm is not None, "Benchmark missing from rewired context"
        assert new_bm.n_peers == ref_benchmark.n_peers
        assert new_bm.median_return_1y == ref_benchmark.median_return_1y
        assert new_bm.median_return_3y == ref_benchmark.median_return_3y
        assert new_bm.median_max_drawdown == ref_benchmark.median_max_drawdown

        # --- ASSERT: per-fund CategoryRelative is identical ------------------
        for isin in _METRICS_ISINS:
            # Funds categorised in context produce a label; absent = on_track fail-safe.
            new_cr = new_labels.get(isin)
            ref_cr = ref_labels.get(isin)
            assert new_cr == ref_cr, (
                f"CategoryRelative mismatch for {isin}: rewired={new_cr!r} ref={ref_cr!r}"
            )

    finally:
        await db_session.execute(
            delete(MfFundMetrics).where(MfFundMetrics.isin.in_(_METRICS_ISINS))
        )
        await db_session.execute(
            delete(MfNavHistory).where(MfNavHistory.isin.in_(_METRICS_ISINS))
        )
        await db_session.execute(
            delete(MfFund).where(MfFund.isin.in_(_METRICS_ISINS))
        )
        await db_session.commit()


# ---------------------------------------------------------------------------
# W2 (§10.1, migration 0064) — compute_market_ranks persists band/factors/signals
# with NO divergence from the rule table (the second scored concept, gate item d).
# ---------------------------------------------------------------------------

_RANKS_CATEGORY = "Equity Scheme - W2 Persistence Test Fund"
_RANKS_ISINS = ["INF_W2RANKA1", "INF_W2RANKB2"]


async def test_compute_market_ranks_persists_band_factors_signals_no_divergence(
    db_session, db_tables, patch_redis
):
    """Seeds 2 funds in one category, runs the REAL `_compute_market_ranks_pipeline`,
    then independently recomputes each fund's ScoringResult via the same
    build_benchmark/compare_to_cohort/compute_fund_signals/score_fund call chain
    (fresh engine, cold hysteresis — first-ever eval publishes immediately, so it is
    directly comparable). The persisted mf_fund_ranks row must equal that independent
    computation exactly — proving the job persists the SAME result the label came
    from, never a re-derived one."""
    from sqlalchemy import select

    from dhanradar.mf.cohort import build_benchmark, compare_to_cohort
    from dhanradar.models.mf import MfFundMetrics, MfFundRanks
    from dhanradar.scoring.engine.schemas import VerbLabel
    from dhanradar.tasks.mf import _compute_market_ranks_pipeline

    stats_by_isin = {
        _RANKS_ISINS[0]: (28.0, 55.0, -12.0),  # clear outperformer
        _RANKS_ISINS[1]: (4.0, 9.0, -30.0),  # clear underperformer
    }
    for isin, (r1, r3, dd) in stats_by_isin.items():
        await db_session.execute(
            insert(MfFund).values(
                isin=isin,
                scheme_name=f"W2 Persistence {isin}",
                sebi_category=_RANKS_CATEGORY,
                category="Equity",
            )
        )
        await db_session.execute(
            insert(MfFundMetrics).values(
                isin=isin,
                return_1y_pct=r1,
                return_3y_pct=r3,
                max_drawdown_pct=dd,
                nav_points=300,
                as_of_date=_AS_OF,
            )
        )
    await db_session.commit()

    try:
        summary = await _compute_market_ranks_pipeline()
        assert "failed" not in summary

        # --- independent recomputation (same inputs, fresh cold engine) ------
        stats_list = list(stats_by_isin.values())
        benchmark = build_benchmark(_RANKS_CATEGORY, stats_list)
        expected: dict[str, dict] = {}
        for isin, fund_stats in stats_by_isin.items():
            cat_rel = compare_to_cohort(fund_stats, benchmark)
            signals = compute_fund_signals(isin, [], category_relative=cat_rel)
            engine = RatingEngine(hysteresis_store=_FakeHystStore(), result_store=_FakeResultStore())
            result = await score_fund(engine, signals)
            refused = result.verb_label == VerbLabel.insufficient_data
            expected[isin] = {
                "verb_label": result.verb_label.value,
                "confidence_band": None if refused else result.confidence_band.value,
                "confidence_factors": None if refused else dict(result.confidence_factors),
                "contributing_signals": list(result.contributing_signals),
                "contradicting_signals": list(result.contradicting_signals),
            }

        # --- read back the persisted rows ------------------------------------
        rows = (
            (
                await db_session.execute(
                    select(MfFundRanks).where(MfFundRanks.isin.in_(_RANKS_ISINS))
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        for row in rows:
            exp = expected[row.isin]
            assert row.verb_label == exp["verb_label"], row.isin
            assert row.confidence_band == exp["confidence_band"], row.isin
            assert row.confidence_factors == exp["confidence_factors"], row.isin
            assert row.contributing_signals == exp["contributing_signals"], row.isin
            assert row.contradicting_signals == exp["contradicting_signals"], row.isin
            # non-neg #2: no numeric ever lands on the row via this path.
            assert row.confidence_factors is None or set(row.confidence_factors.values()) <= {
                "high", "medium", "low",
            }
    finally:
        await db_session.execute(
            delete(MfFundRanks).where(MfFundRanks.isin.in_(_RANKS_ISINS))
        )
        await db_session.execute(
            delete(MfFundMetrics).where(MfFundMetrics.isin.in_(_RANKS_ISINS))
        )
        await db_session.execute(delete(MfFund).where(MfFund.isin.in_(_RANKS_ISINS)))
        await db_session.commit()


# ---------------------------------------------------------------------------
# RCA 2026-07-05 — compute_market_ranks passed an EMPTY NAV list to
# compute_fund_signals, tripping its _MIN_POINTS guard before category_relative
# was applied: every market label degraded to insufficient_data since 2026-06-15.
# This test seeds real NAV + a real cohort and asserts differentiated labels,
# non-null bands, and non-empty signals persist — it FAILS on the old code path
# (which persisted insufficient_data/None/[] for every fund). Also asserts the
# NAV load is chunked (bounded batches) and chunk-size-invariant (same style as
# test_cohort_peer_load_is_chunked_and_equivalent).
# ---------------------------------------------------------------------------

_NAVFIX_CATEGORY = "Equity Scheme - W2 NAV Regression Test Fund"
_NAVFIX_WINNER = "INF_NAVFIXW1"
_NAVFIX_LAGGARD = "INF_NAVFIXL1"
_NAVFIX_THIN = "INF_NAVFIXT1"  # < _MIN_POINTS NAV points → guard must still refuse
_NAVFIX_FILLERS = [f"INF_NAVFIXF{i}" for i in range(3)]
_NAVFIX_ISINS = [_NAVFIX_WINNER, _NAVFIX_LAGGARD, _NAVFIX_THIN, *_NAVFIX_FILLERS]


def _monthly_nav(isin: str, months: int) -> list[dict]:
    """`months` monthly NAV rows ending today (compounding growth) — enough points
    for the momentum/risk axes, all inside _load_nav_series' 400-day window."""
    rows = []
    nav = 100.0
    for i in range(months):
        d = _AS_OF - datetime.timedelta(days=30 * (months - 1 - i))
        rows.append({"isin": isin, "nav_date": d, "nav": round(nav, 4), "source": "amfi"})
        nav *= 1.015
    return rows


async def test_compute_market_ranks_real_nav_yields_real_labels_chunked(
    db_session, db_tables, patch_redis, monkeypatch
):
    from sqlalchemy import select

    from dhanradar.models.mf import MfFundMetrics, MfFundRanks
    from dhanradar.tasks import mf as tasks_mf

    # 6 funds with 1Y returns → n_peers ≥ _MIN_COHORT_PEERS (5), benchmark published.
    # Equity margin is 2.0pp; medians: 1Y 10.25 / 3Y 20.5 / DD 20.5 (DD is a
    # positive magnitude — see signals._max_drawdown_pct).
    stats_by_isin: dict[str, tuple[float, float, float]] = {
        _NAVFIX_WINNER: (28.0, 55.0, 12.0),  # ahead 1Y+3Y, controlled DD → in_form
        _NAVFIX_LAGGARD: (2.0, 5.0, 30.0),  # behind 1Y (and 3Y) → off_track
        _NAVFIX_THIN: (10.0, 20.0, 20.0),
        _NAVFIX_FILLERS[0]: (9.5, 19.0, 19.0),
        _NAVFIX_FILLERS[1]: (10.5, 21.0, 21.0),
        _NAVFIX_FILLERS[2]: (11.0, 22.0, 22.0),
    }
    for isin, (r1, r3, dd) in stats_by_isin.items():
        await db_session.execute(
            insert(MfFund).values(
                isin=isin,
                scheme_name=f"NAV Regression {isin}",
                sebi_category=_NAVFIX_CATEGORY,
                category="Equity",
            )
        )
        await db_session.execute(
            insert(MfFundMetrics).values(
                isin=isin,
                return_1y_pct=r1,
                return_3y_pct=r3,
                max_drawdown_pct=dd,
                nav_points=300,
                as_of_date=_AS_OF,
            )
        )
    # NAV: winner + laggard get a real 14-month series; thin gets 2 points
    # (< _MIN_POINTS=4 → the honest-refusal guard must still fire); fillers none.
    await db_session.execute(insert(MfNavHistory).values(_monthly_nav(_NAVFIX_WINNER, 14)))
    await db_session.execute(insert(MfNavHistory).values(_monthly_nav(_NAVFIX_LAGGARD, 14)))
    await db_session.execute(insert(MfNavHistory).values(_monthly_nav(_NAVFIX_THIN, 2)))
    await db_session.commit()

    # Record every NAV-load batch to assert bounded, chunked access (640MiB worker).
    real_load = tasks_mf._load_nav_series
    batch_sizes: list[int] = []

    async def _recording_load(db, isins, lookback_days=400):
        batch_sizes.append(len(isins))
        return await real_load(db, isins, lookback_days=lookback_days)

    monkeypatch.setattr(tasks_mf, "_load_nav_series", _recording_load)

    async def _read_rows() -> dict[str, dict]:
        rows = (
            (
                await db_session.execute(
                    select(MfFundRanks).where(MfFundRanks.isin.in_(_NAVFIX_ISINS))
                )
            )
            .scalars()
            .all()
        )
        return {
            r.isin: {
                "verb_label": r.verb_label,
                "confidence_band": r.confidence_band,
                "confidence_factors": r.confidence_factors,
                "contributing_signals": r.contributing_signals,
                "contradicting_signals": r.contradicting_signals,
            }
            for r in rows
        }

    try:
        # --- run 1: tiny chunk → the NAV load MUST split into bounded batches ---
        monkeypatch.setattr(tasks_mf, "_RANKS_NAV_CHUNK", 2)
        summary = await tasks_mf._compute_market_ranks_pipeline()
        assert "failed" not in summary
        assert len(batch_sizes) > 1, "NAV load was not chunked"
        assert max(batch_sizes) <= 2, f"a NAV batch exceeded the chunk cap: {batch_sizes}"
        chunked = await _read_rows()

        # Differentiated labels + band + signals persisted (all were
        # insufficient_data/None/[] on the pre-fix empty-list code path).
        winner = chunked[_NAVFIX_WINNER]
        assert winner["verb_label"] == "in_form"
        assert winner["confidence_band"] in {"high", "medium", "low"}
        assert winner["contributing_signals"], "winner must carry contributing signals"

        laggard = chunked[_NAVFIX_LAGGARD]
        assert laggard["verb_label"] == "off_track"
        assert laggard["contradicting_signals"], "laggard must carry contradicting signals"

        # < _MIN_POINTS NAV → the honest-refusal guard still wins.
        thin = chunked[_NAVFIX_THIN]
        assert thin["verb_label"] == "insufficient_data"
        assert thin["confidence_band"] is None
        assert thin["confidence_factors"] is None

        # --- run 2: one-shot chunk → identical persisted output (chunk-invariant) ---
        batch_sizes.clear()
        monkeypatch.setattr(tasks_mf, "_RANKS_NAV_CHUNK", 10_000)
        await tasks_mf._compute_market_ranks_pipeline()
        assert await _read_rows() == chunked
    finally:
        await db_session.execute(delete(MfFundRanks).where(MfFundRanks.isin.in_(_NAVFIX_ISINS)))
        await db_session.execute(
            delete(MfFundMetrics).where(MfFundMetrics.isin.in_(_NAVFIX_ISINS))
        )
        await db_session.execute(delete(MfNavHistory).where(MfNavHistory.isin.in_(_NAVFIX_ISINS)))
        await db_session.execute(delete(MfFund).where(MfFund.isin.in_(_NAVFIX_ISINS)))
        await db_session.commit()
