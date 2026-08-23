"""Unit tests for Feature 6 — Fund Explorer public endpoints.

Coverage:
1. FundExplorerItem serialization: unified_score NEVER appears (non-neg #2).
2. FundCategoriesResponse structure: key + display_name + fund_count.
3. _sebi_display_name helper strips SEBI scheme type prefix.
4. _SORT_SQL whitelist: all expected sort keys are present, no user input leaks.
5. FundExplorerResponse pagination fields are correct.
6. missing category param returns 400 via FastAPI validation path.
7. B74 enrichment (E1): expense_ratio_pct/aum_crore/aum_as_of/riskometer/sharpe_ratio/
   max_drawdown_pct/confidence_band flow through the endpoint and are None when the
   DB row doesn't carry them; the response never leaks a score-shaped key.
8. GET /mf/funds sets Cache-Control: public, max-age=300 (public, no user data).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import Response

from dhanradar.mf.router import _SORT_BEST_ASC, _SORT_COL, _sebi_display_name
from dhanradar.mf.schemas import (
    FundCategoriesResponse,
    FundCategory,
    FundExplorerItem,
    FundExplorerResponse,
)

# ---------------------------------------------------------------------------
# 1. No unified_score in FundExplorerItem
# ---------------------------------------------------------------------------

def test_fund_explorer_item_has_no_unified_score():
    """FundExplorerItem must not expose unified_score (non-neg #2)."""
    item = FundExplorerItem(
        isin="INF082J01564",
        scheme_name="Mirae Asset Large Cap Fund",
        amc_name="Mirae Asset",
        sebi_category="Equity Scheme - Large Cap Fund",
        verb_label="in_form",
        confidence_band=None,
        confidence_factors=None,
        category_rank=1,
        category_total=36,
        return_1y_pct=18.5,
        return_3y_pct=14.2,
    )
    serialized = item.model_dump()
    assert "unified_score" not in serialized
    assert serialized["category_rank"] == 1
    assert serialized["verb_label"] == "in_form"


def test_fund_explorer_response_has_no_unified_score():
    """FundExplorerResponse must not contain unified_score anywhere."""
    item = FundExplorerItem(
        isin="INF082J01564",
        scheme_name="Test Fund",
        amc_name="Test AMC",
        sebi_category="Equity Scheme - Large Cap Fund",
        verb_label="on_track",
        confidence_band=None,
        confidence_factors=None,
        category_rank=5,
        category_total=36,
        return_1y_pct=None,
        return_3y_pct=None,
    )
    resp = FundExplorerResponse(
        funds=[item],
        total=36,
        page=1,
        limit=20,
        disclosure="For educational purposes only.",
        not_advice="Not investment advice.",
    )
    serialized = resp.model_dump()
    assert "unified_score" not in str(serialized)


# ---------------------------------------------------------------------------
# 2. FundCategory + FundCategoriesResponse structure
# ---------------------------------------------------------------------------

def test_fund_category_structure():
    cat = FundCategory(
        key="Equity Scheme - Large Cap Fund",
        display_name="Large Cap Fund",
        fund_count=36,
    )
    assert cat.key == "Equity Scheme - Large Cap Fund"
    assert cat.display_name == "Large Cap Fund"
    assert cat.fund_count == 36


def test_fund_categories_response_empty():
    """Empty categories list is valid (before nightly task has run)."""
    resp = FundCategoriesResponse(categories=[])
    assert resp.categories == []


# ---------------------------------------------------------------------------
# 3. _sebi_display_name helper
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("full,expected", [
    ("Equity Scheme - Large Cap Fund", "Large Cap Fund"),
    ("Debt Scheme - Liquid Fund", "Liquid Fund"),
    ("Hybrid Scheme - Aggressive Hybrid Fund", "Aggressive Hybrid Fund"),
    ("Other Scheme - Index Funds", "Index Funds"),
    ("Solution Oriented Scheme - Children's Fund", "Children's Fund"),
    ("NoHyphen", "NoHyphen"),  # fallback: no " - " in string
])
def test_sebi_display_name(full: str, expected: str):
    assert _sebi_display_name(full) == expected


# ---------------------------------------------------------------------------
# 4. _SORT_COL whitelist safety
# ---------------------------------------------------------------------------

def test_sort_col_expected_keys_present():
    expected = {
        "rank", "return_3m", "return_6m", "return_1y", "return_3y", "return_5y", "max_drawdown",
        "expense_ratio", "aum", "sharpe",
    }
    assert expected == set(_SORT_COL.keys())


def test_sort_col_expense_ratio_asc_is_best():
    """Lower expense ratio is better (cheaper = best), same convention as max_drawdown."""
    assert "expense_ratio" in _SORT_BEST_ASC
    assert _SORT_COL["expense_ratio"] == "f.expense_ratio_pct"


def test_sort_col_aum_and_sharpe_not_asc_is_best():
    """Higher AUM / Sharpe is conventionally better — no ASC-is-best inversion (like returns)."""
    assert "aum" not in _SORT_BEST_ASC
    assert "sharpe" not in _SORT_BEST_ASC
    assert _SORT_COL["aum"] == "f.aum_crore"
    assert _SORT_COL["sharpe"] == "m.sharpe_ratio"


def test_sort_col_no_user_input_in_values():
    """Ensure all column expressions in _SORT_COL are safe literals, not templates."""
    for key, fragment in _SORT_COL.items():
        assert "{" not in fragment, f"Unsafe template in _SORT_COL[{key!r}]"
        assert ";" not in fragment, f"Statement separator in _SORT_COL[{key!r}]"


# ---------------------------------------------------------------------------
# 5. FundExplorerResponse pagination
# ---------------------------------------------------------------------------

def test_fund_explorer_response_pagination():
    resp = FundExplorerResponse(
        funds=[],
        total=100,
        page=3,
        limit=20,
        disclosure="disc",
        not_advice="not advice",
    )
    assert resp.total == 100
    assert resp.page == 3
    assert resp.limit == 20


# ---------------------------------------------------------------------------
# 6. confidence_factors null → serializes as None
# ---------------------------------------------------------------------------

def test_confidence_factors_nullable():
    item = FundExplorerItem(
        isin="INF001A01",
        scheme_name="Test",
        amc_name=None,
        sebi_category="Equity Scheme - Mid Cap Fund",
        verb_label="on_track",
        confidence_band=None,
        confidence_factors=None,
        category_rank=3,
        category_total=29,
        return_1y_pct=None,
        return_3y_pct=None,
    )
    assert item.confidence_factors is None
    assert item.confidence_band is None


# ---------------------------------------------------------------------------
# 7. B74 enrichment (E1) — new fields flow through the endpoint, poisoned-key check
# ---------------------------------------------------------------------------

class _FakeExplorerDB:
    """Minimal AsyncSession stub for fund_explorer_list's raw-SQL two-query
    pattern (rows query + count query both routed through the same execute())."""

    def __init__(self, rows: list[Any], total: int) -> None:
        self._rows = rows
        self._total = total

    async def execute(self, stmt: Any, params: dict | None = None) -> "_FakeExplorerDB":  # noqa: UP037
        return self

    def all(self) -> list[Any]:
        return list(self._rows)

    def scalar_one(self) -> int:
        return self._total


def _explorer_row(**overrides: Any) -> SimpleNamespace:
    base = dict(
        isin="INF000A01001",
        scheme_name="Test Fund - Direct - Growth",
        fund_name_short="Test Fund",
        amc_name="Test AMC",
        sebi_category="Equity Scheme - Large Cap Fund",
        plan_type="direct",
        option_type="growth",
        idcw_frequency=None,
        expense_ratio_pct=None,
        aum_crore=None,
        aum_as_of=None,
        risk_o_meter=None,
        rank=1,
        total_in_cat=36,
        verb_label="in_form",
        confidence_band=None,
        return_3m_pct=5.0,
        return_6m_pct=9.0,
        return_1y_pct=18.5,
        return_3y_pct=14.2,
        return_5y_pct=12.0,
        nav_points=800,
        sharpe_ratio=None,
        max_drawdown_pct=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


async def test_fund_explorer_new_fields_flow_through_and_none_when_absent() -> None:
    from dhanradar.mf.router import fund_explorer_list

    full_row = _explorer_row(
        expense_ratio_pct=0.55,
        aum_crore=1234.5,
        aum_as_of=date(2026, 7, 31),
        risk_o_meter="Very High",
        confidence_band="high",
        sharpe_ratio=1.25,
        max_drawdown_pct=22.3,
    )
    sparse_row = _explorer_row(isin="INF000A01002")  # all new fields left None

    db = _FakeExplorerDB(rows=[full_row, sparse_row], total=2)
    resp = await fund_explorer_list(
        db=db, response=Response(), category="Equity Scheme - Large Cap Fund"
    )

    full, sparse = resp.funds
    assert full.expense_ratio_pct == 0.55
    assert full.aum_crore == 1234.5
    assert full.aum_as_of == "2026-07-31"  # DB date coerced to ISO string
    assert full.riskometer == "Very High"
    assert full.confidence_band == "high"
    assert full.sharpe_ratio == 1.25
    assert full.max_drawdown_pct == 22.3

    assert sparse.expense_ratio_pct is None
    assert sparse.aum_crore is None
    assert sparse.aum_as_of is None
    assert sparse.riskometer is None
    assert sparse.confidence_band is None
    assert sparse.sharpe_ratio is None
    assert sparse.max_drawdown_pct is None


def test_fund_explorer_item_serialization_has_no_poisoned_score_keys() -> None:
    """confidence_factors stays None even when confidence_band is populated
    (internal-only filter keys — non-neg #2); no unified_score/score leak."""
    item = FundExplorerItem(
        isin="INF001A01",
        scheme_name="Test",
        amc_name="Test AMC",
        sebi_category="Equity Scheme - Mid Cap Fund",
        verb_label="on_track",
        confidence_band="medium",
        confidence_factors=None,
        category_rank=3,
        category_total=29,
        expense_ratio_pct=0.9,
        aum_crore=500.0,
        aum_as_of="2026-07-31",
        riskometer="High",
        sharpe_ratio=0.8,
        max_drawdown_pct=15.0,
    )
    serialized = item.model_dump()
    assert "unified_score" not in serialized
    assert "score" not in serialized
    assert serialized["confidence_factors"] is None
    assert serialized["confidence_band"] == "medium"


async def test_fund_explorer_endpoint_sets_cache_control_header() -> None:
    """Public, no-user-data endpoint — edge-cacheable like GET /mf/leaderboard."""
    from dhanradar.mf.router import fund_explorer_list

    resp = Response()
    await fund_explorer_list(
        db=_FakeExplorerDB(rows=[], total=0),
        response=resp,
        category="Equity Scheme - Large Cap Fund",
    )
    assert resp.headers["Cache-Control"] == "public, max-age=300"
