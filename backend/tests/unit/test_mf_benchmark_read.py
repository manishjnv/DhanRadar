"""Focused tests for public benchmark-row resolution order."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from dhanradar.mf.benchmark_read import get_benchmark_row


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Session:
    def __init__(self, fund, mapped=None, tri_rows=(), category_rows=()):
        self.fund = fund
        self.mapped = mapped
        self.tri_rows = tri_rows
        self.category_rows = category_rows

    async def get(self, model, key):
        if model.__name__ == "MfFund":
            return self.fund
        return self.mapped

    async def execute(self, _statement):
        return _Result(self.tri_rows if self.mapped is not None else self.category_rows)


@pytest.mark.asyncio
async def test_mapped_series_wins_over_category_fallback() -> None:
    fund = SimpleNamespace(isin="INF174K01KH7", benchmark_index="Nifty 50 TRI", sebi_category="Equity")
    mapped = SimpleNamespace(index_key="nifty50_tri")
    tri_rows = [
        SimpleNamespace(tri_date=date(2024, 1, 1), tri_value=100),
        SimpleNamespace(tri_date=date(2025, 1, 1), tri_value=110),
        SimpleNamespace(tri_date=date(2026, 1, 1), tri_value=120),
    ]
    result = await get_benchmark_row(_Session(fund, mapped, tri_rows, []), fund.isin)
    assert result["source"] == "benchmark"
    assert result["label"] == "Nifty 50 TRI"
    assert result["returns"]["1y"] is not None


@pytest.mark.asyncio
async def test_short_series_never_reports_longer_windows() -> None:
    """A 2-year series must yield 1Y only — 3Y/5Y stay None, never a relabelled
    shorter-window return (window-start tolerance guard)."""
    fund = SimpleNamespace(isin="INF174K01KH7", benchmark_index="Nifty 50 TRI", sebi_category="Equity")
    mapped = SimpleNamespace(index_key="nifty50_tri")
    tri_rows = [
        SimpleNamespace(tri_date=date(2024, 1, 1), tri_value=100),
        SimpleNamespace(tri_date=date(2025, 1, 1), tri_value=110),
        SimpleNamespace(tri_date=date(2026, 1, 1), tri_value=120),
    ]
    result = await get_benchmark_row(_Session(fund, mapped, tri_rows, []), fund.isin)
    assert result["returns"]["1y"] is not None
    assert result["returns"]["3y"] is None
    assert result["returns"]["5y"] is None


@pytest.mark.asyncio
async def test_category_series_is_the_fallback_when_mapping_is_absent() -> None:
    fund = SimpleNamespace(isin="INF174K01KH7", benchmark_index="Unmapped", sebi_category="Equity")
    category_rows = [
        SimpleNamespace(series_date=date(2024, 1, 1), index_value=100),
        SimpleNamespace(series_date=date(2026, 1, 1), index_value=118),
    ]
    result = await get_benchmark_row(_Session(fund, None, [], category_rows), fund.isin)
    assert result["source"] == "category_median"
    assert result["label"] == "Category median"


@pytest.mark.asyncio
async def test_unmapped_without_category_series_is_explicit_no_data() -> None:
    fund = SimpleNamespace(isin="INF174K01KH7", benchmark_index="Unmapped", sebi_category="Equity")
    result = await get_benchmark_row(_Session(fund, None, [], []), fund.isin)
    assert result == {"no_data": True, "reason": "benchmark_unmapped"}
