"""Scheme-level dedup for /mf/search (founder 2026-08-22).

Repro: searching "mid" returned five rows of the same scheme — the
direct/regular × growth/idcw ISIN variants. One row per scheme, preferring
the direct-plan growth variant; schemes without a direct variant still appear.
"""

from __future__ import annotations

from collections import namedtuple

from dhanradar.mf.router import _dedupe_search_rows

Row = namedtuple(
    "Row",
    "isin scheme_name fund_name_short amc_name sebi_category plan_type option_type idcw_frequency",
)


def _row(isin: str, short: str, plan: str | None, option: str | None) -> Row:
    return Row(isin, f"{short} scheme", short, "AMC", "Mid Cap", plan, option, None)


def test_variants_collapse_to_direct_growth() -> None:
    rows = [
        _row("I1", "Sahara Midcap", "regular", "growth"),
        _row("I2", "Sahara Midcap", "direct", "idcw"),
        _row("I3", "Sahara Midcap", "direct", "growth"),
        _row("I4", "Sahara Midcap", "regular", "idcw"),
    ]
    out = _dedupe_search_rows(rows, 10)
    assert [r.isin for r in out] == ["I3"]


def test_relevance_order_preserved_and_limit_applied() -> None:
    rows = [
        _row("A1", "Alpha Midcap", "direct", "growth"),
        _row("B1", "Beta Midcap", "direct", "growth"),
        _row("A2", "Alpha Midcap", "direct", "idcw"),
        _row("C1", "Gamma Midcap", "direct", "growth"),
    ]
    out = _dedupe_search_rows(rows, 2)
    assert [r.isin for r in out] == ["A1", "B1"]


def test_known_regular_rows_are_dropped_entirely() -> None:
    rows = [_row("R1", "Legacy Fund", "regular", "idcw")]
    assert _dedupe_search_rows(rows, 10) == []


def test_unknown_plan_type_kept_but_loses_to_direct() -> None:
    rows = [
        _row("U1", "Sahara Midcap", None, "growth"),
        _row("D1", "Sahara Midcap", "direct", "growth"),
    ]
    out = _dedupe_search_rows(rows, 10)
    assert [r.isin for r in out] == ["D1"]


def test_null_fund_name_short_falls_back_to_isin_identity() -> None:
    rows = [
        Row("X1", "Some scheme", None, "AMC", "Mid Cap", "direct", "growth", None),
        Row("X2", "Other scheme", None, "AMC", "Mid Cap", None, "growth", None),
    ]
    out = _dedupe_search_rows(rows, 10)
    # Distinct ISINs with no short name are distinct schemes — never merged.
    assert [r.isin for r in out] == ["X1", "X2"]
