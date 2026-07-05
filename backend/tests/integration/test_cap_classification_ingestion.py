"""
Integration test -- AMFI cap-classification ingestion pipeline.

Requires a reachable Postgres (settings.database_url) and the fakeredis fixture.
Run inside the compose stack / CI; NOT runnable locally without a live DB.

Fixtures used
-------------
db_tables   : creates all ORM tables (session-scoped, idempotent)
patch_redis : replaces get_redis() with a fake so is_source_paused() works

Tests
-----
1. Happy-path (2 valid rows) -> one ingestion_runs row (source=
   'amfi_cap_classification'), 2 stock_cap_classification rows written.
2. Freshness addendum: when the current-half data already exists, the
   pipeline exits with status='skipped' and makes NO network call.
3. Fetch failure (ProviderError, e.g. both candidate periods 404) ->
   ingestion_runs row status='partial', source_health.reachable=False,
   zero rows written.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

from sqlalchemy import select, text

from dhanradar.market_data.amfi_cap_classification import StockCapRow
from dhanradar.market_data.exceptions import ProviderError
from dhanradar.models.mf import MfIngestionRun, MfSourceHealth, MfStockCapClassification
from dhanradar.tasks.mf_cap_classification import _mf_cap_classification_pipeline

_ISIN_A = "INE002A01018"
_ISIN_B = "INE040A01034"

_FAKE_ROWS = [
    StockCapRow(
        stock_isin=_ISIN_A,
        stock_name="Reliance Industries Ltd",
        cap_class="Large Cap",
        avg_market_cap_cr=1873286.77,
        effective_period="2026H1",
    ),
    StockCapRow(
        stock_isin=_ISIN_B,
        stock_name="HDFC Bank Ltd.",
        cap_class="Mid Cap",
        avg_market_cap_cr=1286453.23,
        effective_period="2026H1",
    ),
]
_FAKE_URL = "https://portal.amfiindia.com/spages/AverageMarketCapitalization30Jun2026.xlsx"


async def _fake_fetch_ok(client, today):
    return _FAKE_ROWS, "2026H1", _FAKE_URL


async def _fake_fetch_failure(client, today):
    raise ProviderError("no candidate half-year period resolved")


async def _cleanup(db_session, isins: list[str]) -> None:
    if isins:
        await db_session.execute(
            text(
                "DELETE FROM mf.stock_cap_classification WHERE stock_isin = ANY(:isins)"
            ).bindparams(isins=isins)
        )
    await db_session.execute(
        text("DELETE FROM mf.ingestion_runs WHERE source = 'amfi_cap_classification'")
    )
    await db_session.execute(
        text("DELETE FROM mf.source_health WHERE source = 'amfi_cap_classification'")
    )
    await db_session.commit()


async def test_happy_path_writes_rows(db_tables, patch_redis, db_session):
    """Two valid rows arrive -> written to stock_cap_classification."""
    with patch(
        "dhanradar.market_data.amfi_cap_classification.fetch_cap_classification",
        new=AsyncMock(side_effect=_fake_fetch_ok),
    ):
        await _mf_cap_classification_pipeline(today=date(2026, 7, 5))

    run_row = await db_session.scalar(
        select(MfIngestionRun)
        .where(MfIngestionRun.source == "amfi_cap_classification")
        .order_by(MfIngestionRun.run_id.desc())
        .limit(1)
    )
    assert run_row is not None
    assert run_row.status in ("success", "partial")
    assert run_row.records_written == 2

    rows = (
        await db_session.scalars(
            select(MfStockCapClassification).where(
                MfStockCapClassification.stock_isin.in_([_ISIN_A, _ISIN_B])
            )
        )
    ).all()
    assert len(rows) == 2
    for row in rows:
        assert row.effective_period == "2026H1"
        assert row.source_url == _FAKE_URL

    await _cleanup(db_session, [_ISIN_A, _ISIN_B])


async def test_freshness_addendum_skips_when_already_stored(db_tables, patch_redis, db_session):
    """When the current half's data is already stored, the pipeline exits
    with status='skipped' and never calls the fetch function."""
    with patch(
        "dhanradar.market_data.amfi_cap_classification.fetch_cap_classification",
        new=AsyncMock(side_effect=_fake_fetch_ok),
    ) as fetch_mock:
        await _mf_cap_classification_pipeline(today=date(2026, 7, 5))
        fetch_mock.reset_mock()
        # Second run, same "today" -> data for 2026H1 already exists.
        result = await _mf_cap_classification_pipeline(today=date(2026, 7, 6))
        fetch_mock.assert_not_called()

    assert "skipped" in result

    run_row = await db_session.scalar(
        select(MfIngestionRun)
        .where(MfIngestionRun.source == "amfi_cap_classification")
        .order_by(MfIngestionRun.run_id.desc())
        .limit(1)
    )
    assert run_row is not None
    assert run_row.status == "skipped"

    await _cleanup(db_session, [_ISIN_A, _ISIN_B])


async def test_fetch_failure_records_partial_unreachable(db_tables, patch_redis, db_session):
    """Both candidate periods fail to resolve -> run is partial, source unreachable."""
    with patch(
        "dhanradar.market_data.amfi_cap_classification.fetch_cap_classification",
        new=AsyncMock(side_effect=_fake_fetch_failure),
    ):
        await _mf_cap_classification_pipeline(today=date(2026, 7, 5))

    run_row = await db_session.scalar(
        select(MfIngestionRun)
        .where(MfIngestionRun.source == "amfi_cap_classification")
        .order_by(MfIngestionRun.run_id.desc())
        .limit(1)
    )
    assert run_row is not None
    assert run_row.status == "partial"

    health_row = await db_session.scalar(
        select(MfSourceHealth)
        .where(MfSourceHealth.source == "amfi_cap_classification")
        .order_by(MfSourceHealth.check_time.desc())
        .limit(1)
    )
    assert health_row is not None
    assert health_row.reachable is False

    remaining = (
        await db_session.scalars(
            select(MfStockCapClassification.id).where(
                MfStockCapClassification.effective_period == "2026H1"
            )
        )
    ).all()
    assert len(remaining) == 0

    await _cleanup(db_session, [])
