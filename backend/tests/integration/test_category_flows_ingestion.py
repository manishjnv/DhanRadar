"""
Integration test -- AMFI category-flows ingestion pipeline.

Requires a reachable Postgres (settings.database_url) and the fakeredis fixture.
Run inside the compose stack / CI; NOT runnable locally without a live DB.

Fixtures used
-------------
db_tables   : creates all ORM tables (session-scoped, idempotent)
patch_redis : replaces get_redis() with a fake so is_source_paused() works

Tests
-----
1. Happy-path (2 valid rows) -> one ingestion_runs row (source=
   'amfi_category_flows'), 2 mf_category_flows rows written.
2. Freshness addendum: when the latest candidate month already exists, the
   pipeline exits with status='skipped' and makes NO network call.
3. Fetch failure (ProviderError, e.g. both candidate months 404) ->
   ingestion_runs row status='partial', source_health.reachable=False,
   zero rows written.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

from sqlalchemy import select, text

from dhanradar.market_data.amfi_category_flows import CategoryFlowRow
from dhanradar.market_data.exceptions import ProviderError
from dhanradar.models.mf import MfCategoryFlows, MfIngestionRun, MfSourceHealth
from dhanradar.tasks.mf_category_flows import _mf_category_flows_pipeline

_PERIOD = date(2026, 6, 1)

_FAKE_ROWS = [
    CategoryFlowRow(
        period_month=_PERIOD,
        scheme_type="Open ended Schemes",
        scheme_category="Overnight Fund",
        num_schemes=37,
        num_folios=769280,
        funds_mobilized_cr=609290.59,
        redemption_cr=624815.36,
        net_flow_cr=-15524.77,
        net_aum_cr=89939.73,
        avg_aum_cr=125683.05,
    ),
    CategoryFlowRow(
        period_month=_PERIOD,
        scheme_type="Open ended Schemes",
        scheme_category="Liquid Fund",
        num_schemes=42,
        num_folios=3128442,
        funds_mobilized_cr=384615.25,
        redemption_cr=414296.19,
        net_flow_cr=-29680.94,
        net_aum_cr=609456.75,
        avg_aum_cr=647737.83,
    ),
]
_FAKE_URL = "https://portal.amfiindia.com/spages/amjun2026repo.xls"


async def _fake_fetch_ok(client, today):
    return _FAKE_ROWS, _PERIOD, _FAKE_URL


async def _fake_fetch_failure(client, today):
    raise ProviderError("no candidate month resolved")


async def _cleanup(db_session) -> None:
    await db_session.execute(
        text("DELETE FROM mf.mf_category_flows WHERE period_month = :p").bindparams(p=_PERIOD)
    )
    await db_session.execute(
        text("DELETE FROM mf.ingestion_runs WHERE source = 'amfi_category_flows'")
    )
    await db_session.execute(
        text("DELETE FROM mf.source_health WHERE source = 'amfi_category_flows'")
    )
    await db_session.commit()


async def test_happy_path_writes_rows(db_tables, patch_redis, db_session):
    """Two valid rows arrive -> written to mf_category_flows."""
    with patch(
        "dhanradar.market_data.amfi_category_flows.fetch_category_flows",
        new=AsyncMock(side_effect=_fake_fetch_ok),
    ):
        await _mf_category_flows_pipeline(today=date(2026, 7, 5))

    run_row = await db_session.scalar(
        select(MfIngestionRun)
        .where(MfIngestionRun.source == "amfi_category_flows")
        .order_by(MfIngestionRun.run_id.desc())
        .limit(1)
    )
    assert run_row is not None
    assert run_row.status in ("success", "partial")
    assert run_row.records_written == 2

    rows = (
        await db_session.scalars(
            select(MfCategoryFlows).where(MfCategoryFlows.period_month == _PERIOD)
        )
    ).all()
    assert len(rows) == 2
    categories = {r.scheme_category for r in rows}
    assert categories == {"Overnight Fund", "Liquid Fund"}
    for row in rows:
        assert row.source_url == _FAKE_URL

    await _cleanup(db_session)


async def test_freshness_addendum_skips_when_already_stored(db_tables, patch_redis, db_session):
    """When the latest candidate month is already stored, the pipeline exits
    with status='skipped' and never calls the fetch function."""
    with patch(
        "dhanradar.market_data.amfi_category_flows.fetch_category_flows",
        new=AsyncMock(side_effect=_fake_fetch_ok),
    ) as fetch_mock:
        # today=2026-07-05 -> candidate_months()[0] == 2026-06-01 == _PERIOD
        await _mf_category_flows_pipeline(today=date(2026, 7, 5))
        fetch_mock.reset_mock()
        result = await _mf_category_flows_pipeline(today=date(2026, 7, 6))
        fetch_mock.assert_not_called()

    assert "skipped" in result

    run_row = await db_session.scalar(
        select(MfIngestionRun)
        .where(MfIngestionRun.source == "amfi_category_flows")
        .order_by(MfIngestionRun.run_id.desc())
        .limit(1)
    )
    assert run_row is not None
    assert run_row.status == "skipped"

    await _cleanup(db_session)


async def test_fetch_failure_records_partial_unreachable(db_tables, patch_redis, db_session):
    """Both candidate months fail to resolve -> run is partial, source unreachable."""
    with patch(
        "dhanradar.market_data.amfi_category_flows.fetch_category_flows",
        new=AsyncMock(side_effect=_fake_fetch_failure),
    ):
        await _mf_category_flows_pipeline(today=date(2026, 7, 5))

    run_row = await db_session.scalar(
        select(MfIngestionRun)
        .where(MfIngestionRun.source == "amfi_category_flows")
        .order_by(MfIngestionRun.run_id.desc())
        .limit(1)
    )
    assert run_row is not None
    assert run_row.status == "partial"

    health_row = await db_session.scalar(
        select(MfSourceHealth)
        .where(MfSourceHealth.source == "amfi_category_flows")
        .order_by(MfSourceHealth.check_time.desc())
        .limit(1)
    )
    assert health_row is not None
    assert health_row.reachable is False

    remaining = (
        await db_session.scalars(
            select(MfCategoryFlows.id).where(MfCategoryFlows.period_month == _PERIOD)
        )
    ).all()
    assert len(remaining) == 0

    await _cleanup(db_session)
