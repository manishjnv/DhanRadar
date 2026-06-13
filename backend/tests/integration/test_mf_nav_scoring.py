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
_AS_OF = datetime.date(2026, 6, 6)


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
