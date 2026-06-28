"""
Integration test — RBI DBIE macro data ingestion pipeline.

Requires a reachable Postgres (settings.database_url) and the fakeredis fixture.
Run inside the compose stack / CI; NOT runnable locally without a live DB.

Fixtures used
-------------
db_tables   : creates all ORM tables (function-scoped, idempotent)
patch_redis : replaces get_redis() with a fake so is_source_paused() works
db_session  : function-scoped async session for assertions

Tests
-----
1. Happy-path (3 valid rows)
   - One mf.ingestion_runs row with source='rbi_dbie', status='success',
     records_written==3.
   - Three mf.macro_indicators rows written.
   - Source health row recorded with reachable=True.

2. Re-run idempotency (on_conflict_do_update)
   - Running the pipeline twice with the same 3 rows results in exactly 3
     macro_indicators rows (no duplicates), and both runs appear in
     ingestion_runs (two rows), both status='success'.

NOTE: This test is NOT runnable locally without a running Postgres instance
(settings.database_url must resolve). CI is the gate for integration tests
(see project memory: "CI is the gate, not local pytest").
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import func, select, text

from dhanradar.models.mf import MfIngestionRun, MfMacroIndicator, MfSourceHealth
from dhanradar.tasks.macro_data import _macro_data_pipeline

# ---------------------------------------------------------------------------
# Deterministic test fixture — 3 valid macro rows as CSV.
# ---------------------------------------------------------------------------

_FAKE_CSV = """\
indicator_key,indicator_value,unit,as_of_date
repo_rate,6.50,percent,2024-04-01
cpi_inflation,4.83,percent,2024-03-01
gdp_growth,8.20,percent,2024-01-01
"""


async def _fake_fetch_ok(client) -> str:
    """Return 3 valid rows."""
    return _FAKE_CSV


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
    await db_session.execute(
        text("DELETE FROM mf.macro_indicators WHERE source = 'rbi_dbie'")
    )
    await db_session.execute(
        text("DELETE FROM mf.ingestion_runs WHERE source = 'rbi_dbie'")
    )
    await db_session.execute(
        text("DELETE FROM mf.source_health WHERE source = 'rbi_dbie'")
    )
    await db_session.commit()


# ===========================================================================
# Test 1 — Happy path: 3 valid rows written
# ===========================================================================


async def test_happy_path_writes_three_rows(db_tables, patch_redis, db_session):
    """3 valid rows → ingestion_runs success + 3 macro_indicators + source healthy."""
    await _cleanup(db_session)

    with patch(
        "dhanradar.market_data.rbi.fetch_macro_indicators",
        new=AsyncMock(side_effect=_fake_fetch_ok),
    ):
        with patch(
            "dhanradar.tasks.macro_data.httpx.AsyncClient",
            return_value=_mock_httpx_client_cm(),
        ):
            await _macro_data_pipeline()

    # --- ingestion_runs: one row, status='success', records_written==3 ---
    run_row = await db_session.scalar(
        select(MfIngestionRun)
        .where(MfIngestionRun.source == "rbi_dbie")
        .order_by(MfIngestionRun.run_id.desc())
        .limit(1)
    )
    assert run_row is not None, "Expected one ingestion_runs row"
    assert run_row.status == "success", (
        f"Expected status='success', got '{run_row.status}'"
    )
    assert run_row.records_written == 3, (
        f"Expected records_written=3, got {run_row.records_written}"
    )

    # --- macro_indicators: 3 rows ---
    indicator_rows = (
        await db_session.scalars(
            select(MfMacroIndicator).where(MfMacroIndicator.source == "rbi_dbie")
        )
    ).all()
    assert len(indicator_rows) == 3, (
        f"Expected 3 macro_indicators rows, got {len(indicator_rows)}"
    )

    # Verify the keys are what we expect.
    written_keys = {r.indicator_key for r in indicator_rows}
    assert written_keys == {"repo_rate", "cpi_inflation", "gdp_growth"}

    # --- source_health: reachable=True ---
    health_row = await db_session.scalar(
        select(MfSourceHealth)
        .where(MfSourceHealth.source == "rbi_dbie")
        .order_by(MfSourceHealth.check_time.desc())
        .limit(1)
    )
    assert health_row is not None, "Expected a source_health row"
    assert health_row.reachable is True, (
        f"Expected reachable=True, got {health_row.reachable}"
    )

    await _cleanup(db_session)


# ===========================================================================
# Test 2 — Re-run idempotency: same 3 rows, second run updates not duplicates
# ===========================================================================


async def test_rerun_does_not_duplicate_rows(db_tables, patch_redis, db_session):
    """Running the pipeline twice with the same rows → 3 indicator rows (no duplicates)."""
    await _cleanup(db_session)

    with patch(
        "dhanradar.market_data.rbi.fetch_macro_indicators",
        new=AsyncMock(side_effect=_fake_fetch_ok),
    ):
        with patch(
            "dhanradar.tasks.macro_data.httpx.AsyncClient",
            return_value=_mock_httpx_client_cm(),
        ):
            await _macro_data_pipeline()
            await _macro_data_pipeline()

    # --- macro_indicators: still exactly 3 rows (on_conflict_do_update, not INSERT) ---
    indicator_count = await db_session.scalar(
        select(func.count()).select_from(MfMacroIndicator).where(
            MfMacroIndicator.source == "rbi_dbie"
        )
    )
    assert indicator_count == 3, (
        f"Expected 3 macro_indicators rows after two runs, got {indicator_count}"
    )

    # --- ingestion_runs: 2 rows (one per run) ---
    run_count = await db_session.scalar(
        select(func.count()).select_from(MfIngestionRun).where(
            MfIngestionRun.source == "rbi_dbie"
        )
    )
    assert run_count == 2, (
        f"Expected 2 ingestion_runs rows (one per pipeline run), got {run_count}"
    )

    # Both runs must have status='success'.
    run_rows = (
        await db_session.scalars(
            select(MfIngestionRun).where(MfIngestionRun.source == "rbi_dbie")
        )
    ).all()
    for run in run_rows:
        assert run.status == "success", (
            f"Expected status='success', got '{run.status}' for run_id={run.run_id}"
        )

    await _cleanup(db_session)
