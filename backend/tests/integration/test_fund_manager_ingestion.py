"""
Integration test -- AMC fund-manager ingestion pipeline.

Requires a reachable Postgres (settings.database_url) and the fakeredis fixture.
Run inside the compose stack / CI; NOT runnable locally without a live DB.

Fixtures used
-------------
db_tables   : creates all ORM tables (function-scoped, idempotent)
patch_redis : replaces get_redis() with a fake so is_source_paused() works
db_session  : function-scoped async session; used for assertions + cleanup

Tests
-----
1. Happy-path (2 valid rows, mixed bot-blocked/ok status)
   - One mf.ingestion_runs row with source='amc_fund_managers',
     status in ('success', 'partial'), records_written == 2.
   - Two mf.fund_manager_history rows written.
   - A SECOND pipeline run does NOT duplicate them (idempotent / dedup).

2. All-bot-blocked path (zero rows fetched)
   - One mf.ingestion_runs row exists with status='partial'.
   - Corresponding mf.source_health row has reachable=False.
   - Zero fund_manager_history rows written.

ISIN format: ^INF[A-Z0-9]{9}$ (12 chars). All test ISINs follow this shape.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select, text

from dhanradar.market_data.amc_managers import FundManagerRow
from dhanradar.models.mf import MfFundManagerHistory, MfIngestionRun, MfSourceHealth
from dhanradar.tasks.mf_fund_manager import _mf_fund_manager_pipeline

# ---------------------------------------------------------------------------
# Test data -- 12-char ISINs (INF + 9 alphanumeric).
# ---------------------------------------------------------------------------
_ISIN_A = "INF123MGR456"
_ISIN_B = "INF456MGR012"

_FAKE_ROWS = [
    FundManagerRow(
        scheme_uid=_ISIN_A,
        manager_name="Priya Sharma",
        start_date=datetime.date(2021, 6, 1),
        end_date=None,
    ),
    FundManagerRow(
        scheme_uid=_ISIN_B,
        manager_name="Rahul Mehta",
        start_date=datetime.date(2019, 3, 15),
        end_date=datetime.date(2023, 12, 31),
    ),
]

_FAKE_STATUS_OK = {
    "bot_blocked": ["HDFC", "SBI"],
    "unreachable": [],
    "ok": ["NIPPON"],
}

_FAKE_STATUS_ALL_BLOCKED = {
    "bot_blocked": ["HDFC", "SBI", "ICICI_PRU", "KOTAK", "AXIS"],
    "unreachable": ["NIPPON", "MIRAE"],
    "ok": [],
}


async def _fake_fetch_ok(client, sources=None):
    """Deterministic fake: returns 2 valid rows + mixed-blocked status."""
    return _FAKE_ROWS, _FAKE_STATUS_OK


async def _fake_fetch_all_blocked(client, sources=None):
    """Deterministic fake: returns no rows because all AMCs are blocked."""
    return [], _FAKE_STATUS_ALL_BLOCKED


def _async_client_cm_mock():
    """Return a mock that behaves as `async with httpx.AsyncClient(...) as client:`."""
    fake_client = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=fake_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


async def _cleanup(db_session, isins: list[str]) -> None:
    """Remove test rows so tests don't bleed into each other."""
    if isins:
        await db_session.execute(
            text(
                "DELETE FROM mf.fund_manager_history WHERE scheme_uid = ANY(:isins)"
            ).bindparams(isins=isins)
        )
    await db_session.execute(
        text("DELETE FROM mf.ingestion_runs WHERE source = 'amc_fund_managers'")
    )
    await db_session.execute(
        text("DELETE FROM mf.source_health WHERE source = 'amc_fund_managers'")
    )
    await db_session.commit()


# ===========================================================================
# Test 1 -- Happy path: 2 valid rows written
# ===========================================================================

async def test_happy_path_writes_rows(db_tables, patch_redis, db_session):
    """Two valid fund-manager rows arrive -> written to fund_manager_history."""
    with patch(
        "dhanradar.market_data.amc_managers.fetch_fund_managers",
        new=AsyncMock(side_effect=_fake_fetch_ok),
    ):
        with patch(
            "dhanradar.tasks.mf_fund_manager.httpx.AsyncClient",
            return_value=_async_client_cm_mock(),
        ):
            await _mf_fund_manager_pipeline()

    # --- ingestion_runs: one row written ---
    run_row = await db_session.scalar(
        select(MfIngestionRun)
        .where(MfIngestionRun.source == "amc_fund_managers")
        .order_by(MfIngestionRun.run_id.desc())
        .limit(1)
    )
    assert run_row is not None, "Expected one ingestion_runs row"
    assert run_row.status in ("success", "partial"), (
        f"Unexpected status '{run_row.status}'"
    )
    assert run_row.records_written == 2, (
        f"Expected records_written=2, got {run_row.records_written}"
    )

    # --- fund_manager_history: two rows ---
    history_rows = (
        await db_session.scalars(
            select(MfFundManagerHistory).where(
                MfFundManagerHistory.scheme_uid.in_([_ISIN_A, _ISIN_B])
            )
        )
    ).all()
    assert len(history_rows) == 2, f"Expected 2 history rows, got {len(history_rows)}"

    await _cleanup(db_session, [_ISIN_A, _ISIN_B])


# ===========================================================================
# Test 2 -- Idempotent: second run does NOT duplicate rows
# ===========================================================================

async def test_second_run_does_not_duplicate(db_tables, patch_redis, db_session):
    """Running the pipeline twice for the same rows must not create duplicates."""
    for _ in range(2):
        with patch(
            "dhanradar.market_data.amc_managers.fetch_fund_managers",
            new=AsyncMock(side_effect=_fake_fetch_ok),
        ):
            with patch(
                "dhanradar.tasks.mf_fund_manager.httpx.AsyncClient",
                return_value=_async_client_cm_mock(),
            ):
                await _mf_fund_manager_pipeline()

    history_rows = (
        await db_session.scalars(
            select(MfFundManagerHistory).where(
                MfFundManagerHistory.scheme_uid.in_([_ISIN_A, _ISIN_B])
            )
        )
    ).all()
    assert len(history_rows) == 2, (
        f"Expected exactly 2 rows after 2 runs (idempotent), got {len(history_rows)}"
    )

    await _cleanup(db_session, [_ISIN_A, _ISIN_B])


# ===========================================================================
# Test 3 -- All-bot-blocked: zero rows -> run is partial + source unreachable
# ===========================================================================

async def test_all_bot_blocked_records_partial_unreachable(db_tables, patch_redis, db_session):
    """When all AMCs are blocked/unreachable, the run is partial and source_health.reachable=False."""
    with patch(
        "dhanradar.market_data.amc_managers.fetch_fund_managers",
        new=AsyncMock(side_effect=_fake_fetch_all_blocked),
    ):
        with patch(
            "dhanradar.tasks.mf_fund_manager.httpx.AsyncClient",
            return_value=_async_client_cm_mock(),
        ):
            await _mf_fund_manager_pipeline()

    # --- ingestion_runs: status='partial' ---
    run_row = await db_session.scalar(
        select(MfIngestionRun)
        .where(MfIngestionRun.source == "amc_fund_managers")
        .order_by(MfIngestionRun.run_id.desc())
        .limit(1)
    )
    assert run_row is not None, "Expected one ingestion_runs row even for all-blocked path"
    assert run_row.status == "partial", f"Expected status='partial', got '{run_row.status}'"

    # --- source_health: reachable=False ---
    health_row = await db_session.scalar(
        select(MfSourceHealth)
        .where(MfSourceHealth.source == "amc_fund_managers")
        .order_by(MfSourceHealth.check_time.desc())
        .limit(1)
    )
    assert health_row is not None, "Expected a source_health row"
    assert health_row.reachable is False, (
        f"Expected reachable=False, got {health_row.reachable}"
    )

    # --- no fund_manager_history rows written ---
    count = await db_session.scalar(
        text(
            "SELECT COUNT(*) FROM mf.fund_manager_history "
            "WHERE source = 'amc_fund_managers'"
        )
    )
    assert count == 0, f"Expected 0 history rows for all-blocked run, got {count}"

    await _cleanup(db_session, [])
