"""
Integration test — RBI 91-day T-bill yield ingestion pipeline.

Requires a reachable Postgres (settings.database_url) and the fakeredis fixture.
Run inside the compose stack / CI; NOT runnable locally without a live DB.

Fixtures used
-------------
db_tables   : creates all ORM tables (function-scoped, idempotent)
patch_redis : replaces get_redis() with a fake so is_source_paused() works
db_session  : function-scoped async session for assertions

Tests
-----
1. Happy-path (1 valid T-bill row)
   - One mf.ingestion_runs row with source='rbi_tbill', status='success',
     records_written==1.
   - One mf.macro_indicators row with indicator_key='tbill_91d_yield_pct'.
   - Source health row recorded with reachable=True.

2. Re-run idempotency (on_conflict_do_update)
   - Running the pipeline twice with the same row results in exactly 1
     macro_indicators row (no duplicates), and both runs appear in
     ingestion_runs (two rows), both status='success'.

3. Out-of-range value rejected
   - Yield value outside [3.0, 10.0] → stats.failed incremented, row not written.

NOTE: This test is NOT runnable locally without a running Postgres instance
(settings.database_url must resolve). CI is the gate for integration tests
(see project memory: "CI is the gate, not local pytest").
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import func, select, text

from dhanradar.market_data.rbi import MacroRow
from dhanradar.models.mf import MfIngestionRun, MfMacroIndicator, MfSourceHealth
from dhanradar.tasks.rbi_tbill import _rbi_tbill_pipeline

# ---------------------------------------------------------------------------
# Deterministic test fixtures — MacroRow objects
# ---------------------------------------------------------------------------


async def _fake_fetch_valid(client) -> MacroRow:
    """Return a valid T-bill yield row."""
    return MacroRow(
        indicator_key="tbill_91d_yield_pct",
        indicator_value=6.8307,
        unit="percent",
        as_of_date=date(2026, 7, 3),
    )


async def _fake_fetch_out_of_range(client) -> MacroRow:
    """Return an out-of-range T-bill yield (12% > max 10%)."""
    return MacroRow(
        indicator_key="tbill_91d_yield_pct",
        indicator_value=12.0,
        unit="percent",
        as_of_date=date(2026, 7, 3),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_httpx_client_cm():
    """Return a mock that behaves as `async with httpx.AsyncClient(...) as client:`."""
    fake_client = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=fake_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


async def _cleanup(db_session) -> None:
    """Remove all test rows so tests are independent."""
    await db_session.execute(text("DELETE FROM mf.macro_indicators WHERE source = 'rbi_tbill'"))
    await db_session.execute(text("DELETE FROM mf.ingestion_runs WHERE source = 'rbi_tbill'"))
    await db_session.execute(text("DELETE FROM mf.source_health WHERE source = 'rbi_tbill'"))
    await db_session.commit()


# ===========================================================================
# Test 1 — Happy path: 1 valid T-bill row written
# ===========================================================================


async def test_happy_path_writes_one_row(db_tables, patch_redis, db_session):
    """1 valid T-bill row → ingestion_runs success + 1 macro_indicators + source healthy."""
    await _cleanup(db_session)

    with patch(
        "dhanradar.market_data.rbi_tbill.fetch_tbill_yield",
        new=AsyncMock(side_effect=_fake_fetch_valid),
    ):
        with patch(
            "dhanradar.tasks.rbi_tbill.httpx.AsyncClient",
            return_value=_mock_httpx_client_cm(),
        ):
            await _rbi_tbill_pipeline()

    # --- ingestion_runs: one row, status='success', records_written==1 ---
    run_row = await db_session.scalar(
        select(MfIngestionRun)
        .where(MfIngestionRun.source == "rbi_tbill")
        .order_by(MfIngestionRun.run_id.desc())
        .limit(1)
    )
    assert run_row is not None, "Expected one ingestion_runs row"
    assert run_row.status == "success", f"Expected status='success', got '{run_row.status}'"
    assert run_row.records_written == 1, (
        f"Expected records_written=1, got {run_row.records_written}"
    )

    # --- macro_indicators: 1 row with indicator_key='tbill_91d_yield_pct' ---
    indicator_row = await db_session.scalar(
        select(MfMacroIndicator).where(
            MfMacroIndicator.source == "rbi_tbill",
            MfMacroIndicator.indicator_key == "tbill_91d_yield_pct",
        )
    )
    assert indicator_row is not None, "Expected one macro_indicators row"
    # indicator_value is a Numeric(18,4) column -> comes back as Decimal; compare
    # via float() to avoid a Decimal-vs-float exact-representation mismatch.
    assert float(indicator_row.indicator_value) == pytest.approx(6.8307)
    assert indicator_row.unit == "percent"
    assert indicator_row.as_of_date == date(2026, 7, 3)

    # --- source_health: reachable=True ---
    health_row = await db_session.scalar(
        select(MfSourceHealth)
        .where(MfSourceHealth.source == "rbi_tbill")
        .order_by(MfSourceHealth.check_time.desc())
        .limit(1)
    )
    assert health_row is not None, "Expected a source_health row"
    assert health_row.reachable is True, f"Expected reachable=True, got {health_row.reachable}"

    await _cleanup(db_session)


# ===========================================================================
# Test 2 — Re-run idempotency: same row, second run updates not duplicates
# ===========================================================================


async def test_rerun_does_not_duplicate_rows(db_tables, patch_redis, db_session):
    """Running the pipeline twice with the same row → 1 indicator row (no duplicates)."""
    await _cleanup(db_session)

    with patch(
        "dhanradar.market_data.rbi_tbill.fetch_tbill_yield",
        new=AsyncMock(side_effect=_fake_fetch_valid),
    ):
        with patch(
            "dhanradar.tasks.rbi_tbill.httpx.AsyncClient",
            return_value=_mock_httpx_client_cm(),
        ):
            await _rbi_tbill_pipeline()
            await _rbi_tbill_pipeline()

    # --- macro_indicators: still exactly 1 row (on_conflict_do_update, not INSERT) ---
    indicator_count = await db_session.scalar(
        select(func.count())
        .select_from(MfMacroIndicator)
        .where(MfMacroIndicator.source == "rbi_tbill")
    )
    assert indicator_count == 1, (
        f"Expected 1 macro_indicators row after two runs, got {indicator_count}"
    )

    # --- ingestion_runs: 2 rows (one per run) ---
    run_count = await db_session.scalar(
        select(func.count()).select_from(MfIngestionRun).where(MfIngestionRun.source == "rbi_tbill")
    )
    assert run_count == 2, f"Expected 2 ingestion_runs rows (one per pipeline run), got {run_count}"

    # Both runs must have status='success'.
    run_rows = (
        await db_session.scalars(select(MfIngestionRun).where(MfIngestionRun.source == "rbi_tbill"))
    ).all()
    for run in run_rows:
        assert run.status == "success", (
            f"Expected status='success', got '{run.status}' for run_id={run.run_id}"
        )

    await _cleanup(db_session)


# ===========================================================================
# Test 3 — Out-of-range value rejected
# ===========================================================================


async def test_out_of_range_value_rejected(db_tables, patch_redis, db_session):
    """Yield value outside [3.0, 10.0] → stats.failed incremented, row not written."""
    await _cleanup(db_session)

    with patch(
        "dhanradar.market_data.rbi_tbill.fetch_tbill_yield",
        new=AsyncMock(side_effect=_fake_fetch_out_of_range),
    ):
        with patch(
            "dhanradar.tasks.rbi_tbill.httpx.AsyncClient",
            return_value=_mock_httpx_client_cm(),
        ):
            await _rbi_tbill_pipeline()

    # --- ingestion_runs: one row. _derive_status (tasks/ingestion_run.py) treats
    # "fetched but everything failed validation, nothing written" as status='failed'
    # (same policy every other source-ingestion task follows) -- the fetch itself
    # succeeding is irrelevant to the run's overall status when 0 rows land.
    run_row = await db_session.scalar(
        select(MfIngestionRun)
        .where(MfIngestionRun.source == "rbi_tbill")
        .order_by(MfIngestionRun.run_id.desc())
        .limit(1)
    )
    assert run_row is not None, "Expected one ingestion_runs row"
    assert run_row.status == "failed", f"Expected status='failed', got '{run_row.status}'"
    assert run_row.records_written == 0, (
        f"Expected records_written=0, got {run_row.records_written}"
    )
    assert run_row.records_failed == 1, f"Expected records_failed=1, got {run_row.records_failed}"

    # --- macro_indicators: 0 rows (out-of-range value was rejected) ---
    indicator_count = await db_session.scalar(
        select(func.count())
        .select_from(MfMacroIndicator)
        .where(MfMacroIndicator.source == "rbi_tbill")
    )
    assert indicator_count == 0, (
        f"Expected 0 macro_indicators rows (out-of-range rejected), got {indicator_count}"
    )

    await _cleanup(db_session)
