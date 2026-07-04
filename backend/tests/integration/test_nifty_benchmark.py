"""Nifty 50 benchmark daily-close series — unit + integration tests.

Covers:
  * Pure: _fetch_nifty_closes returns correct (date, value) pairs from a mock DataFrame.
  * Pure: _fetch_nifty_closes returns [] when DataFrame is empty.
  * Pure: _fetch_nifty_closes drops NaN rows.
  * PG:   nifty_close_daily task upserts a row; re-run is idempotent (ON CONFLICT DO UPDATE).
  * PG:   backfill_nifty_close_series upserts multiple rows in the correct order.
  * PG:   GET /mf/benchmark/nifty50 returns ASC rows; empty list before any rows exist;
          from/to date filters work; invalid date format returns 400.

yfinance is mocked throughout — no live network calls in tests.
"""

from __future__ import annotations

import math
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Table isolation — mf_benchmark_daily is a public table, so rows committed
# by TaskSessionLocal survive the per-test transaction rollback used for other
# personal-data tables.  Truncate before each test so every PG test starts
# from an empty table.  The fixture uses its own TaskSessionLocal connection
# (same as the production task) to stay consistent with the writes-under-test.
# It swallows connection errors gracefully so the three pure/unit tests
# (_fetch_nifty_closes_*) still pass in environments without a live Postgres.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _clean_benchmark():
    try:
        from dhanradar.db import task_session

        async with task_session() as db:
            await db.execute(text("DELETE FROM mf.mf_benchmark_daily"))
            await db.commit()
    except Exception:
        pass  # DB not available (pure-test environment) — silently skip
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_yf_df(rows: list[tuple[str, float]]):
    """Lightweight mock that duck-types yf.download() output used by _fetch_nifty_closes.

    Avoids importing pandas in tests — the function only needs:
      - .empty (bool)
      - ["Close"].items() → (timestamp-like, float) pairs
    """
    from datetime import date as _date

    class _Ts:
        def __init__(self, s: str) -> None:
            self._d = _date.fromisoformat(s)

        def date(self) -> _date:
            return self._d

    class _Series:
        def __init__(self, data: list[tuple[str, float]]) -> None:
            self._data = data

        def items(self):
            return ((_Ts(d), v) for d, v in self._data)

    class _DF:
        def __init__(self, data: list[tuple[str, float]]) -> None:
            self._data = data
            self.empty = len(data) == 0

        def __getitem__(self, key: str):
            if key == "Close":
                return _Series(self._data)
            raise KeyError(key)

    return _DF(rows)


def _make_empty_df():
    return _make_yf_df([])


# ---------------------------------------------------------------------------
# Pure: _fetch_nifty_closes
# ---------------------------------------------------------------------------


def _patch_yf(df):
    """Context manager: inject a fake yfinance into sys.modules so the lazy
    `import yfinance as yf` inside _fetch_nifty_closes resolves to the mock."""
    import sys

    mock_yf = MagicMock()
    mock_yf.download.return_value = df
    return patch.dict(sys.modules, {"yfinance": mock_yf})


def test_fetch_nifty_closes_returns_pairs():
    """_fetch_nifty_closes parses yf.download output into (date, float) pairs."""
    from dhanradar.tasks.mf import _fetch_nifty_closes

    mock_df = _make_yf_df([("2026-06-30", 24_500.00), ("2026-07-01", 24_650.50)])
    with _patch_yf(mock_df):
        result = _fetch_nifty_closes(date(2026, 6, 30), date(2026, 7, 1))

    assert len(result) == 2
    assert result[0] == (date(2026, 6, 30), 24_500.00)
    assert result[1] == (date(2026, 7, 1), 24_650.50)


def test_fetch_nifty_closes_empty_df():
    """_fetch_nifty_closes returns [] when yf.download returns an empty result."""
    from dhanradar.tasks.mf import _fetch_nifty_closes

    with _patch_yf(_make_empty_df()):
        result = _fetch_nifty_closes(date(2026, 7, 1), date(2026, 7, 1))

    assert result == []


def test_fetch_nifty_closes_drops_nan():
    """_fetch_nifty_closes silently drops rows where Close is NaN."""
    from dhanradar.tasks.mf import _fetch_nifty_closes

    mock_df = _make_yf_df([("2026-06-28", float("nan")), ("2026-06-30", 24_400.00)])
    with _patch_yf(mock_df):
        result = _fetch_nifty_closes(date(2026, 6, 28), date(2026, 6, 30))

    assert len(result) == 1
    assert not math.isnan(result[0][1])
    assert result[0] == (date(2026, 6, 30), 24_400.00)


def test_fetch_nifty_closes_multiindex_columns():
    """Regression: recent yfinance returns MultiIndex columns even for a single ticker,
    so raw['Close'] is a 1-column DataFrame — not a Series. _fetch_nifty_closes must
    collapse it to the ticker column and still yield scalar (date, float) pairs.
    Uses a REAL pandas MultiIndex frame (the hand-rolled mock above could not reproduce
    this shape, which is why the original code passed CI but failed against live yfinance)."""
    import pandas as pd

    from dhanradar.tasks.mf import _fetch_nifty_closes

    idx = pd.to_datetime(["2026-06-30", "2026-07-01"])
    df = pd.DataFrame(
        {("Close", "^NSEI"): [24_500.00, 24_650.50], ("Open", "^NSEI"): [24_400.0, 24_550.0]},
        index=idx,
    )
    df.columns = pd.MultiIndex.from_tuples(df.columns)  # ('Close','^NSEI'), ('Open','^NSEI')

    with _patch_yf(df):
        result = _fetch_nifty_closes(date(2026, 6, 30), date(2026, 7, 1))

    assert result == [(date(2026, 6, 30), 24_500.00), (date(2026, 7, 1), 24_650.50)]


# ---------------------------------------------------------------------------
# PG helpers
# ---------------------------------------------------------------------------


async def _seed_close(
    db_session, close_date: date, close_value: float, benchmark: str = "nifty50_price"
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_benchmark_daily (benchmark, close_date, close_value)"
            " VALUES (:b, :d, :v)"
            " ON CONFLICT (benchmark, close_date) DO UPDATE SET close_value = EXCLUDED.close_value"
        ),
        {"b": benchmark, "d": close_date, "v": close_value},
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# PG: nifty_close_daily task (mocked yfinance)
# ---------------------------------------------------------------------------


async def test_nifty_close_daily_upserts_row(db_session, async_client):
    """nifty_close_daily inserts today's close into mf_benchmark_daily."""
    from dhanradar.tasks.mf import BENCHMARK_KEY_NIFTY50, _nifty_close_daily_async

    mock_df = _make_yf_df([("2026-07-01", 24_800.00)])
    with _patch_yf(mock_df):
        result = await _nifty_close_daily_async()

    assert "nifty_close_daily: close_date=2026-07-01" in result

    row = (
        await db_session.execute(
            text(
                "SELECT close_value FROM mf.mf_benchmark_daily"
                " WHERE benchmark = :b AND close_date = '2026-07-01'"
            ),
            {"b": BENCHMARK_KEY_NIFTY50},
        )
    ).scalar_one_or_none()
    assert row is not None
    assert abs(float(row) - 24_800.00) < 0.01


async def test_nifty_close_daily_idempotent(db_session, async_client):
    """Running nifty_close_daily twice updates close_value (ON CONFLICT DO UPDATE)."""
    from dhanradar.tasks.mf import BENCHMARK_KEY_NIFTY50, _nifty_close_daily_async

    for val in (24_700.00, 24_750.25):
        mock_df = _make_yf_df([("2026-07-01", val)])
        with _patch_yf(mock_df):
            await _nifty_close_daily_async()

    row = (
        await db_session.execute(
            text(
                "SELECT close_value FROM mf.mf_benchmark_daily"
                " WHERE benchmark = :b AND close_date = '2026-07-01'"
            ),
            {"b": BENCHMARK_KEY_NIFTY50},
        )
    ).scalar_one_or_none()
    assert row is not None
    assert abs(float(row) - 24_750.25) < 0.01


async def test_nifty_close_daily_no_op_on_empty_data(db_session, async_client):
    """nifty_close_daily returns no_data gracefully when yfinance returns empty."""
    from dhanradar.tasks.mf import _nifty_close_daily_async

    with _patch_yf(_make_empty_df()):
        result = await _nifty_close_daily_async()

    assert "no_data" in result


# ---------------------------------------------------------------------------
# PG: backfill_nifty_close_series (mocked yfinance)
# ---------------------------------------------------------------------------


async def test_backfill_upserts_multiple_rows(db_session, async_client):
    """backfill_nifty_close_series bulk-upserts a range of historical closes."""
    from dhanradar.tasks.mf import BENCHMARK_KEY_NIFTY50, _backfill_nifty_close_series_async

    rows = [
        ("2026-06-27", 24_100.00),
        ("2026-06-28", 24_050.50),
        ("2026-06-30", 24_300.00),
    ]
    mock_df = _make_yf_df(rows)
    with _patch_yf(mock_df):
        result = await _backfill_nifty_close_series_async(years=1)

    assert "upserted=3" in result

    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM mf.mf_benchmark_daily WHERE benchmark = :b"),
            {"b": BENCHMARK_KEY_NIFTY50},
        )
    ).scalar_one()
    assert count >= 3


# ---------------------------------------------------------------------------
# PG: GET /mf/benchmark/nifty50 endpoint
# ---------------------------------------------------------------------------


async def test_benchmark_endpoint_empty_before_backfill(db_session, async_client):
    """Returns 200 with empty points when no rows exist yet."""
    r = await async_client.get("/api/v1/mf/benchmark/nifty50")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["benchmark"] == "nifty50_price"
    assert body["point_count"] == 0
    assert body["points"] == []
    assert "excludes dividends" in body["disclosure"]


async def test_benchmark_endpoint_returns_asc(db_session, async_client):
    """Rows are returned ascending by close_date."""
    await _seed_close(db_session, date(2026, 6, 30), 24_300.00)
    await _seed_close(db_session, date(2026, 7, 1), 24_800.00)
    await _seed_close(db_session, date(2026, 6, 27), 24_100.00)

    r = await async_client.get("/api/v1/mf/benchmark/nifty50")
    assert r.status_code == 200, r.text
    pts = r.json()["points"]
    assert len(pts) >= 3
    dates = [p["close_date"] for p in pts]
    assert dates == sorted(dates), "points must be ascending by date"


async def test_benchmark_endpoint_from_to_filter(db_session, async_client):
    """?from and ?to date params filter the results correctly."""
    await _seed_close(db_session, date(2026, 6, 27), 24_100.00)
    await _seed_close(db_session, date(2026, 6, 30), 24_300.00)
    await _seed_close(db_session, date(2026, 7, 1), 24_800.00)

    r = await async_client.get("/api/v1/mf/benchmark/nifty50?from=2026-06-30&to=2026-06-30")
    assert r.status_code == 200, r.text
    pts = r.json()["points"]
    assert len(pts) == 1
    assert pts[0]["close_date"] == "2026-06-30"
    assert abs(pts[0]["close_value"] - 24_300.00) < 0.01


async def test_benchmark_endpoint_invalid_date(db_session, async_client):
    """Invalid date format returns HTTP 400."""
    r = await async_client.get("/api/v1/mf/benchmark/nifty50?from=not-a-date")
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# Registry-driven daily/backfill tasks + GET /mf/benchmark/{key} (item 3, 2026-07)
# ---------------------------------------------------------------------------


async def test_all_benchmarks_daily_close_upserts_every_registry_key(db_session, async_client):
    """The registry-wide daily task upserts a row for every BENCHMARK_REGISTRY key
    (one mocked Yahoo call each), each keyed by its own storage_key."""
    from dhanradar.tasks.mf import BENCHMARK_REGISTRY, _all_benchmarks_daily_close_async

    mock_df = _make_yf_df([("2026-07-01", 100.0)])
    with _patch_yf(mock_df):
        result = await _all_benchmarks_daily_close_async()

    assert "nifty_close_daily: close_date=2026-07-01" in result  # nifty50 label preserved

    for spec in BENCHMARK_REGISTRY.values():
        row = (
            await db_session.execute(
                text(
                    "SELECT close_value FROM mf.mf_benchmark_daily"
                    " WHERE benchmark = :b AND close_date = '2026-07-01'"
                ),
                {"b": spec.storage_key},
            )
        ).scalar_one_or_none()
        assert row is not None, f"missing row for {spec.storage_key}"


async def test_backfill_all_benchmarks_upserts_every_registry_key(db_session, async_client):
    """backfill_nifty_close_series('all') upserts every registered benchmark."""
    from dhanradar.tasks.mf import BENCHMARK_REGISTRY, _backfill_all_benchmarks_async

    rows = [("2026-06-27", 100.0), ("2026-06-30", 101.0)]
    mock_df = _make_yf_df(rows)
    with _patch_yf(mock_df):
        result = await _backfill_all_benchmarks_async(years=1)

    assert "backfill_nifty_close_series: upserted=2" in result  # nifty50 label preserved

    for spec in BENCHMARK_REGISTRY.values():
        count = (
            await db_session.execute(
                text("SELECT COUNT(*) FROM mf.mf_benchmark_daily WHERE benchmark = :b"),
                {"b": spec.storage_key},
            )
        ).scalar_one()
        assert count >= 2, f"missing rows for {spec.storage_key}"


async def test_benchmark_endpoint_by_key_returns_seeded_series(db_session, async_client):
    """GET /mf/benchmark/{key} returns 200 + the mapped display name's disclosure
    for a registered non-nifty50 key."""
    await _seed_close(db_session, date(2026, 6, 30), 8_200.00, benchmark="nifty100")

    r = await async_client.get("/api/v1/mf/benchmark/nifty100")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["benchmark"] == "nifty100"
    assert body["point_count"] == 1
    assert body["points"][0]["close_value"] == 8_200.00
    assert "Nifty 100" in body["disclosure"]
    assert "excludes dividends" in body["disclosure"]


async def test_benchmark_endpoint_by_key_unknown_404(db_session, async_client):
    """GET /mf/benchmark/{key} 404s (RFC7807) for a key not in BENCHMARK_REGISTRY."""
    r = await async_client.get("/api/v1/mf/benchmark/not_a_real_benchmark")
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "benchmark_not_found"
