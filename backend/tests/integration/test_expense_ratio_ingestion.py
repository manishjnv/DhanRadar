"""
Integration test -- AMC expense-ratio ingestion pipeline.

Requires a reachable Postgres (settings.database_url) and the fakeredis fixture.
Run inside the compose stack / CI; NOT runnable locally without a live DB.

Fixtures used
-------------
db_tables   : creates all ORM tables (session-scoped, idempotent)
patch_redis : replaces get_redis() with a fake so is_source_paused() works

Tests
-----
1. Happy-path (2 valid rows, mixed bot-blocked/ok status)
   - One mf.ingestion_runs row with source='amc_expense_ratios',
     status in ('success', 'partial'), records_written == 2.
   - Two mf.expense_ratio_history rows written.
   - mf_funds.expense_ratio_pct updated for both ISINs.

2. All-bot-blocked path (zero rows fetched)
   - One mf.ingestion_runs row exists with status='partial'.
   - Corresponding mf.source_health row has reachable=False.
   - Zero expense_ratio_history rows written.

ISIN format: ^INF[A-Z0-9]{9}$ (12 chars). All test ISINs follow this shape.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from dhanradar.market_data.amc_expense import ExpenseRatioRow
from dhanradar.models.mf import MfExpenseRatioHistory, MfFund, MfIngestionRun, MfSourceHealth
from dhanradar.tasks.mf_expense_ratio import _mf_expense_ratio_pipeline

# ---------------------------------------------------------------------------
# Test data -- 12-char ISINs (INF + 9 alphanumeric).
# ---------------------------------------------------------------------------
_ISIN_A = "INF123TST456"
_ISIN_B = "INF456TST012"

_FAKE_ROWS = [
    ExpenseRatioRow(isin=_ISIN_A, ter_pct=0.85, effective_date=datetime.date(2026, 6, 1)),
    ExpenseRatioRow(isin=_ISIN_B, ter_pct=1.20, effective_date=datetime.date(2026, 5, 15)),
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


async def _seed_funds(db_session, isins: list[str]) -> None:
    """Insert stub mf_funds rows so UPDATE expense_ratio_pct has a target."""
    vals = [
        {"isin": isin, "scheme_name": f"Test Fund {isin}", "expense_ratio_pct": None}
        for isin in isins
    ]
    stmt = pg_insert(MfFund).values(vals).on_conflict_do_nothing(index_elements=["isin"])
    await db_session.execute(stmt)
    await db_session.commit()


async def _cleanup(db_session, isins: list[str]) -> None:
    """Remove test rows (mf.* has no FK to auth.users; CASCADE won't reach it)."""
    if isins:
        await db_session.execute(
            text("DELETE FROM mf.expense_ratio_history WHERE isin = ANY(:isins)").bindparams(
                isins=isins
            )
        )
        await db_session.execute(
            text("DELETE FROM mf.mf_funds WHERE isin = ANY(:isins)").bindparams(isins=isins)
        )
    await db_session.execute(
        text("DELETE FROM mf.ingestion_runs WHERE source = 'amc_expense_ratios'")
    )
    await db_session.execute(
        text("DELETE FROM mf.source_health WHERE source = 'amc_expense_ratios'")
    )
    await db_session.commit()


# ===========================================================================
# Test 1 -- Happy path: 2 valid rows written, funds updated
# ===========================================================================

def _async_client_cm_mock():
    """Return a mock that behaves as `async with httpx.AsyncClient(...) as client:`."""
    fake_client = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=fake_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


async def test_happy_path_writes_rows_and_updates_funds(db_tables, patch_redis, db_session):
    """Two valid TER rows arrive -> written to history + mf_funds updated."""
    await _seed_funds(db_session, [_ISIN_A, _ISIN_B])

    # Patch the module-level import target so _mf_expense_ratio_pipeline uses our fake.
    # The pipeline does `from dhanradar.market_data.amc_expense import fetch_expense_ratios`
    # inside the function body; patch the name in the source module so the local import
    # picks up the patched object.  Use AsyncMock so `await fetch_fn(client)` works.
    with patch(
        "dhanradar.market_data.amc_expense.fetch_expense_ratios",
        new=AsyncMock(side_effect=_fake_fetch_ok),
    ):
        with patch("dhanradar.tasks.mf_expense_ratio.httpx.AsyncClient", return_value=_async_client_cm_mock()):
            await _mf_expense_ratio_pipeline()

    # --- ingestion_runs: one row written ---
    run_row = await db_session.scalar(
        select(MfIngestionRun)
        .where(MfIngestionRun.source == "amc_expense_ratios")
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

    # --- expense_ratio_history: two rows ---
    history_rows = (
        await db_session.scalars(
            select(MfExpenseRatioHistory).where(
                MfExpenseRatioHistory.isin.in_([_ISIN_A, _ISIN_B])
            )
        )
    ).all()
    assert len(history_rows) == 2, f"Expected 2 history rows, got {len(history_rows)}"

    # --- mf_funds.expense_ratio_pct updated ---
    fund_rows = (
        await db_session.scalars(
            select(MfFund).where(MfFund.isin.in_([_ISIN_A, _ISIN_B]))
        )
    ).all()
    for fund in fund_rows:
        assert fund.expense_ratio_pct is not None, (
            f"expense_ratio_pct not updated for {fund.isin}"
        )

    await _cleanup(db_session, [_ISIN_A, _ISIN_B])


# ===========================================================================
# Test 2 -- All-bot-blocked: zero rows -> run is partial + source unreachable
# ===========================================================================

async def test_all_bot_blocked_records_partial_unreachable(db_tables, patch_redis, db_session):
    """When all AMCs are blocked/unreachable, the run is partial and source_health.reachable=False."""
    with patch(
        "dhanradar.market_data.amc_expense.fetch_expense_ratios",
        new=AsyncMock(side_effect=_fake_fetch_all_blocked),
    ):
        with patch("dhanradar.tasks.mf_expense_ratio.httpx.AsyncClient", return_value=_async_client_cm_mock()):
            await _mf_expense_ratio_pipeline()

    # --- ingestion_runs: status='partial' ---
    run_row = await db_session.scalar(
        select(MfIngestionRun)
        .where(MfIngestionRun.source == "amc_expense_ratios")
        .order_by(MfIngestionRun.run_id.desc())
        .limit(1)
    )
    assert run_row is not None, "Expected one ingestion_runs row even for all-blocked path"
    assert run_row.status == "partial", f"Expected status='partial', got '{run_row.status}'"

    # --- source_health: reachable=False ---
    health_row = await db_session.scalar(
        select(MfSourceHealth)
        .where(MfSourceHealth.source == "amc_expense_ratios")
        .order_by(MfSourceHealth.check_time.desc())
        .limit(1)
    )
    assert health_row is not None, "Expected a source_health row"
    assert health_row.reachable is False, (
        f"Expected reachable=False, got {health_row.reachable}"
    )

    # --- no expense_ratio_history rows written ---
    count = await db_session.scalar(
        select(text("COUNT(*)")).select_from(MfExpenseRatioHistory).where(
            MfExpenseRatioHistory.source == "amc_expense_ratios"
        )
    )
    assert count == 0, f"Expected 0 history rows for all-blocked run, got {count}"

    await _cleanup(db_session, [])
