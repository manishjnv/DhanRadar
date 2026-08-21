"""Public benchmark-return read model for compare and watchlist surfaces."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.models.mf import MfBenchmarkMap, MfBenchmarkTri, MfCategorySeries, MfFund

_BENCHMARK_WINDOWS = (365, 1095, 1825)
_MIN_CATEGORY_FUND_COUNT = 5


async def get_benchmark_row(session: AsyncSession, isin: str) -> dict:
    """Resolve factual 1Y/3Y/5Y benchmark returns with an honest fallback."""
    fund = await session.get(MfFund, isin)
    if fund is None:
        return {"no_data": True, "reason": "fund_not_found"}

    raw_name = fund.benchmark_index
    mapped = await session.get(MfBenchmarkMap, raw_name) if raw_name else None
    source = "benchmark"
    label = raw_name
    rows: list[tuple[date, float]] = []

    if mapped is not None:
        rows = [
            (row.tri_date, float(row.tri_value))
            for row in (
                await session.execute(
                    select(MfBenchmarkTri.tri_date, MfBenchmarkTri.tri_value)
                    .where(MfBenchmarkTri.index_key == mapped.index_key)
                    .order_by(MfBenchmarkTri.tri_date.asc())
                )
            ).all()
        ]

    if not rows and fund.sebi_category:
        source = "category_median"
        label = "Category median"
        rows = [
            (row.series_date, float(row.index_value))
            for row in (
                await session.execute(
                    select(MfCategorySeries.series_date, MfCategorySeries.index_value)
                    .where(
                        MfCategorySeries.category == fund.sebi_category,
                        MfCategorySeries.fund_count >= _MIN_CATEGORY_FUND_COUNT,
                    )
                    .order_by(MfCategorySeries.series_date.asc())
                )
            ).all()
        ]

    if not rows:
        return {"no_data": True, "reason": "benchmark_unmapped"}

    end_date = rows[-1][0]
    values: dict[str, float | None] = {}
    for name, days in zip(("1y", "3y", "5y"), _BENCHMARK_WINDOWS, strict=True):
        start_date = end_date - timedelta(days=days)
        start = next(((d, value) for d, value in rows if d >= start_date), None)
        if start is None or start[1] == 0:
            values[name] = None
        else:
            values[name] = round((rows[-1][1] / start[1] - 1) * 100, 2)

    return {
        "source": source,
        "label": label or "Category median",
        "returns": values,
        "as_of": end_date.isoformat(),
    }
