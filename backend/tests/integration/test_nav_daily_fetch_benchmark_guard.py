"""
Regression test — RCA 2026-07-11: nav_daily_fetch's nightly mf_funds upsert clobbered
AMFI Fund-Performance-sourced benchmark names with NULL.

CI-only: requires a live Postgres test database (no local Postgres on dev boxes).

Root cause: `_navrows_to_fund_upserts` (dhanradar/tasks/mf.py) derives benchmark_index
as None for every fund EXCEPT high-confidence index-fund name matches (Block 0.7). The
nightly nav_daily_fetch upsert (mf.py ~line 1783) previously wrote
``"benchmark_index": insert(MfFund).excluded.benchmark_index`` unconditionally, so every
active (non-index) fund's real benchmark — populated by the separate AMFI
Fund-Performance ingestion (PR #544) — was overwritten with NULL on every nightly run.

Fix: COALESCE the incoming value against the existing column (mirrors the isin2 guard
already used by mf_scheme_master_refresh) — incoming wins when non-null, existing
survives when incoming is NULL.

Covers both upsert paths through the real `_nav_daily_pipeline_body` code (not a
reimplementation of the SQL), so the test fails if the guard regresses:
  1. Active (non-index) fund, incoming benchmark_index derives None → existing value
     (simulating PR #544 AMFI Fund-Performance data) survives untouched.
  2. Index fund matched against BENCHMARK_REGISTRY, incoming benchmark_index derives
     a real value → the column updates.
"""

from __future__ import annotations

import datetime

import pytest

from dhanradar.market_data.amfi import NavRow

pytestmark = pytest.mark.integration

_TODAY = datetime.date.today()

# Fund A: active large-cap fund. AMFI category is NOT the index-fund leaf, so
# _navrows_to_fund_upserts derives benchmark_index=None for it every run — the exact
# defect shape. Its existing benchmark_index (seeded below) must survive the upsert.
_ISIN_ACTIVE = "INF000A0ACT1"
_ROW_ACTIVE = NavRow(
    amfi_code="900001",
    isin_growth=_ISIN_ACTIVE,
    isin_reinvest=None,
    scheme_name="Sample Large Cap Fund - Direct Plan - Growth",
    nav=123.45,
    nav_date=_TODAY,
    category="Equity Scheme - Large Cap Fund",
)

# Fund B: index fund whose name matches the BENCHMARK_REGISTRY "nifty50" pattern once its
# AMFI category canonicalizes to "Other Scheme - Index Funds". Incoming benchmark_index
# derives a real (non-null) value, so it must overwrite whatever was seeded.
_ISIN_INDEX = "INF000A0IDX1"
_ROW_INDEX = NavRow(
    amfi_code="900002",
    isin_growth=_ISIN_INDEX,
    isin_reinvest=None,
    scheme_name="Sample Nifty 50 Index Fund - Direct Plan - Growth",
    nav=67.89,
    nav_date=_TODAY,
    category="Index Funds - Equity Funds",
)


async def test_nav_daily_fetch_never_clobbers_benchmark_index_with_null(
    db_tables,
    patch_redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import insert, select

    import dhanradar.market_data.amfi as _amfi_mod
    from dhanradar.db import TaskSessionLocal
    from dhanradar.models.mf import MfFund
    from dhanradar.tasks.mf import _nav_daily_pipeline

    # Seed pre-existing mf_funds rows as if PR #544's AMFI Fund-Performance ingestion
    # (fund A) and a prior nav_daily_fetch run (fund B, still unmapped) had already run.
    async with TaskSessionLocal() as db:
        await db.execute(
            insert(MfFund),
            [
                {
                    "isin": _ISIN_ACTIVE,
                    "scheme_name": "Sample Large Cap Fund - Direct Plan - Growth",
                    "benchmark_index": "NIFTY 50 TRI",  # the real fact that must survive
                },
                {
                    "isin": _ISIN_INDEX,
                    "scheme_name": "Sample Nifty 50 Index Fund - Direct Plan - Growth",
                    "benchmark_index": None,
                },
            ],
        )
        await db.commit()

    async def _fake_fetch_navall_rows_with_category(*_args, **_kwargs):
        return [_ROW_ACTIVE, _ROW_INDEX]

    monkeypatch.setattr(
        _amfi_mod, "fetch_navall_rows_with_category", _fake_fetch_navall_rows_with_category
    )

    result = await _nav_daily_pipeline()
    assert "nav_daily_fetch" in result

    async with TaskSessionLocal() as db:
        rows = (
            await db.execute(
                select(MfFund.isin, MfFund.benchmark_index).where(
                    MfFund.isin.in_([_ISIN_ACTIVE, _ISIN_INDEX])
                )
            )
        ).all()
    by_isin = {r.isin: r.benchmark_index for r in rows}

    # Defect case: incoming derives None for a non-index fund — existing fact survives.
    assert by_isin[_ISIN_ACTIVE] == "NIFTY 50 TRI", (
        f"benchmark_index clobbered: expected 'NIFTY 50 TRI' to survive, got "
        f"{by_isin[_ISIN_ACTIVE]!r}"
    )
    # Update case: incoming derives a real registry value — it must still win.
    assert by_isin[_ISIN_INDEX] == "nifty50", (
        f"benchmark_index failed to update from a real incoming value, got {by_isin[_ISIN_INDEX]!r}"
    )
