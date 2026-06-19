"""
Integration tests for the AMFI Scheme Master ingestion pipeline.

CI-only: requires a live Postgres test database (no local Postgres on dev boxes).
Run via `pytest tests/integration/test_scheme_master_ingestion.py` inside the
container (pytest.ini / pyproject.toml marks these as `integration`).

Covers:
  - _mf_scheme_master_pipeline() with monkeypatched fetch_scheme_master creates:
    * exactly one mf.ingestion_runs row (source='amfi_scheme_master',
      status in ('success', 'partial'), records_written==2)
    * exactly 2 mf.mf_funds rows with the fixture ISINs

Fixtures used: db_tables (creates all ORM tables), patch_redis (fake Redis).
TaskSessionLocal is the DB access path (NullPool; same as production).
"""

from __future__ import annotations

import datetime

import pytest

from dhanradar.market_data.amfi_scheme_master import SchemeMasterRow

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Fixture rows for monkeypatching
# ---------------------------------------------------------------------------

_TODAY = datetime.date.today()

# Two valid scheme master rows — one with both ISINs, one with growth-only.
_FIXTURE_ROWS = [
    SchemeMasterRow(
        amfi_code="119551",
        scheme_name="HDFC Top 100 Fund - Direct Plan - Growth",
        amc_name="HDFC Mutual Fund",
        scheme_type="Open Ended Schemes",
        scheme_category="Equity Scheme - Large Cap Fund",
        isin_growth="INF179KB1HA2",
        isin_reinvest=None,
        launch_date=datetime.date(2013, 1, 1),
        closure_date=None,
    ),
    SchemeMasterRow(
        amfi_code="118701",
        scheme_name="Nippon India Large Cap Fund - Regular Plan - Dividend",
        amc_name="Nippon India Mutual Fund",
        scheme_type="Open Ended Schemes",
        scheme_category="Equity Scheme - Large Cap Fund",
        isin_growth="INF204K01EY6",
        isin_reinvest="INF204K01EZ3",
        launch_date=datetime.date(2004, 8, 1),
        closure_date=None,
    ),
]

# Semicolon-delimited text that parse_scheme_master would produce the above rows from.
# We monkeypatch fetch_scheme_master to return this and also monkeypatch
# parse_scheme_master to return _FIXTURE_ROWS so the test is hermetic (no ISIN regex
# dependence on fixture text).
_FIXTURE_TEXT = (
    "AMC;Code;Scheme Name;Scheme Type;Scheme Category;Scheme NAV Name;"
    "Scheme Minimum Amount;Launch Date;Closure Date;"
    "ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment\n"
    "HDFC Mutual Fund;119551;HDFC Top 100 Fund - Direct Plan - Growth;"
    "Open Ended Schemes;Equity Scheme - Large Cap Fund;"
    "HDFC Top 100 - Direct Growth;100;01-Jan-2013;;"
    "INF179KB1HA2;-\n"
    "Nippon India Mutual Fund;118701;Nippon India Large Cap Fund - Regular Plan - Dividend;"
    "Open Ended Schemes;Equity Scheme - Large Cap Fund;"
    "Nippon Large Cap - Regular - Div;500;01-Aug-2004;;"
    "INF204K01EY6;INF204K01EZ3\n"
)


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------


async def test_scheme_master_pipeline_writes_runs_and_funds(
    db_tables,
    patch_redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Full pipeline integration test (DB-backed, CI-only):
    1. Monkeypatch fetch_scheme_master to return _FIXTURE_TEXT.
    2. Monkeypatch parse_scheme_master to return _FIXTURE_ROWS (hermetic — no
       real HTTP; parse behaviour is separately unit-tested).
    3. Call _mf_scheme_master_pipeline().
    4. Assert:
       - exactly one mf.ingestion_runs row with source='amfi_scheme_master',
         status in ('success', 'partial'), records_written==2.
       - exactly 2 mf.mf_funds rows with the fixture ISINs.
    """
    from sqlalchemy import select

    from dhanradar.db import TaskSessionLocal
    from dhanradar.models.mf import MfFund, MfIngestionRun
    from dhanradar.tasks.mf_scheme_master import _mf_scheme_master_pipeline

    # Patch the provider: fetch returns fixture text; parse returns fixture rows.
    import dhanradar.market_data.amfi_scheme_master as _provider_mod

    async def _fake_fetch(client):  # noqa: ARG001
        return _FIXTURE_TEXT

    monkeypatch.setattr(_provider_mod, "fetch_scheme_master", _fake_fetch)
    monkeypatch.setattr(_provider_mod, "parse_scheme_master", lambda _text: _FIXTURE_ROWS)

    # -----------------------------------------------------------------
    # Run the pipeline
    # -----------------------------------------------------------------
    result = await _mf_scheme_master_pipeline()

    # The return string must mention written counts (non-advisory).
    assert "written" in result

    # -----------------------------------------------------------------
    # Verify ingestion_runs
    # -----------------------------------------------------------------
    async with TaskSessionLocal() as db:
        run_rows = (
            await db.execute(
                select(MfIngestionRun).where(
                    MfIngestionRun.source == "amfi_scheme_master"
                )
            )
        ).scalars().all()

    assert len(run_rows) == 1, (
        f"Expected exactly 1 ingestion_runs row for amfi_scheme_master, got {len(run_rows)}"
    )
    run = run_rows[0]
    assert run.status in ("success", "partial"), (
        f"Expected status 'success' or 'partial', got {run.status!r}"
    )
    assert run.records_written == 2, (
        f"Expected records_written==2, got {run.records_written}"
    )

    # -----------------------------------------------------------------
    # Verify mf_funds rows exist for both ISINs
    # -----------------------------------------------------------------
    fixture_isins = {"INF179KB1HA2", "INF204K01EY6"}
    async with TaskSessionLocal() as db:
        fund_rows = (
            await db.execute(
                select(MfFund).where(MfFund.isin.in_(fixture_isins))
            )
        ).scalars().all()

    found_isins = {f.isin for f in fund_rows}
    assert found_isins == fixture_isins, (
        f"Expected mf_funds ISINs {fixture_isins}, found {found_isins}"
    )

    # Spot-check that the upserted data is correct for one row.
    hdfc = next(f for f in fund_rows if f.isin == "INF179KB1HA2")
    assert hdfc.amfi_code == "119551"
    assert hdfc.scheme_name == "HDFC Top 100 Fund - Direct Plan - Growth"
    assert hdfc.amc_name == "HDFC Mutual Fund"
    assert hdfc.category == "Equity Scheme - Large Cap Fund"
    assert hdfc.launch_date == datetime.date(2013, 1, 1)
