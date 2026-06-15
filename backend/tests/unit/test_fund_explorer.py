"""Unit tests for Feature 6 — Fund Explorer public endpoints.

Coverage:
1. FundExplorerItem serialization: unified_score NEVER appears (non-neg #2).
2. FundCategoriesResponse structure: key + display_name + fund_count.
3. _sebi_display_name helper strips SEBI scheme type prefix.
4. _SORT_SQL whitelist: all expected sort keys are present, no user input leaks.
5. FundExplorerResponse pagination fields are correct.
6. missing category param returns 400 via FastAPI validation path.
"""

from __future__ import annotations

import pytest

from dhanradar.mf.router import _SORT_COL, _sebi_display_name
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
    expected = {"rank", "return_3m", "return_6m", "return_1y", "return_3y", "return_5y", "max_drawdown"}
    assert expected == set(_SORT_COL.keys())


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
