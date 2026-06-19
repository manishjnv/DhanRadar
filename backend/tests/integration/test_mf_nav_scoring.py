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
