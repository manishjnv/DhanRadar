"""
Unit tests for dhanradar.mf.snapshot — portfolio-snapshot math (Phase 5).

Pure unit tests — no Redis/DB, no I/O; all inputs are injected in-process.
Covers: XIRR golden-set, XIRR None cases, category allocation, overlap matrix,
and the build_snapshot end-to-end aggregation.
"""

from __future__ import annotations

import datetime

import pytest

from dhanradar.mf.snapshot import (
    CashFlow,
    Holding,
    build_snapshot,
    category_allocation,
    overlap_matrix,
    xirr,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s)


def _holding(
    isin: str,
    invested: float,
    current: float,
    category: str = "Equity",
    cashflows: list[CashFlow] | None = None,
) -> Holding:
    return Holding(
        isin=isin,
        units=100.0,
        invested_amount=invested,
        current_value=current,
        category=category,
        cashflows=cashflows or [],
    )


# ---------------------------------------------------------------------------
# XIRR — golden-set: -100 000 on 2024-01-01, +112 000 on 2025-01-01
# Exact 365-day round-trip → rate = (112000/100000)^(365/365) − 1 = 12 %
# ---------------------------------------------------------------------------

def test_xirr_single_round_trip_approx_12pct():
    flows = [
        CashFlow(when=_date("2024-01-01"), amount=-100_000.0),
        CashFlow(when=_date("2025-01-01"), amount=112_000.0),
    ]
    result = xirr(flows)
    assert result is not None
    assert abs(result - 12.0) < 0.1, f"Expected ≈12.0 %, got {result}"


def test_xirr_multi_flow_positive_result():
    # SIP-style: 3 monthly investments + final value
    flows = [
        CashFlow(when=_date("2023-01-01"), amount=-10_000.0),
        CashFlow(when=_date("2023-04-01"), amount=-10_000.0),
        CashFlow(when=_date("2023-07-01"), amount=-10_000.0),
        CashFlow(when=_date("2024-01-01"), amount=35_000.0),
    ]
    result = xirr(flows)
    assert result is not None
    assert result > 0.0, "Expected a positive return"


# ---------------------------------------------------------------------------
# XIRR — None cases
# ---------------------------------------------------------------------------

def test_xirr_none_when_fewer_than_two_flows():
    assert xirr([]) is None
    assert xirr([CashFlow(_date("2024-01-01"), -50_000.0)]) is None


def test_xirr_none_when_all_same_sign_negative():
    flows = [
        CashFlow(_date("2024-01-01"), -10_000.0),
        CashFlow(_date("2024-06-01"), -20_000.0),
    ]
    assert xirr(flows) is None


def test_xirr_none_when_all_same_sign_positive():
    flows = [
        CashFlow(_date("2024-01-01"), 10_000.0),
        CashFlow(_date("2024-06-01"), 20_000.0),
    ]
    assert xirr(flows) is None


# ---------------------------------------------------------------------------
# Category allocation
# ---------------------------------------------------------------------------

def test_category_allocation_two_categories():
    holdings = [
        _holding("ISIN1", 50_000, 60_000, category="Equity"),
        _holding("ISIN2", 30_000, 30_000, category="Debt"),
        _holding("ISIN3", 20_000, 10_000, category="Equity"),
    ]
    alloc = category_allocation(holdings)
    # Total CV = 100 000; Equity = 70 000 (70%); Debt = 30 000 (30%)
    assert abs(alloc["Equity"] - 70.0) < 0.01
    assert abs(alloc["Debt"] - 30.0) < 0.01
    total = sum(alloc.values())
    assert abs(total - 100.0) < 0.01, f"Allocation must sum to ~100, got {total}"


def test_category_allocation_three_categories():
    holdings = [
        _holding("A", 0, 40_000, category="Equity"),
        _holding("B", 0, 30_000, category="Hybrid"),
        _holding("C", 0, 30_000, category="Debt"),
    ]
    alloc = category_allocation(holdings)
    assert set(alloc.keys()) == {"Equity", "Hybrid", "Debt"}
    total = sum(alloc.values())
    assert abs(total - 100.0) < 0.01


def test_category_allocation_empty_holdings():
    assert category_allocation([]) == {}


def test_category_allocation_zero_total_cv():
    holdings = [
        _holding("X", 10_000, 0.0, category="Equity"),
    ]
    assert category_allocation(holdings) == {}


# ---------------------------------------------------------------------------
# Overlap matrix
# ---------------------------------------------------------------------------

def test_overlap_matrix_none_constituents_returns_empty():
    holdings = [_holding("ISIN1", 0, 0), _holding("ISIN2", 0, 0)]
    assert overlap_matrix(holdings, None) == {}


def test_overlap_matrix_empty_constituents_dict_returns_empty():
    holdings = [_holding("ISIN1", 0, 0), _holding("ISIN2", 0, 0)]
    assert overlap_matrix(holdings, {}) == {}


def test_overlap_matrix_two_funds_with_shared_stocks():
    # Fund A: Reliance 50%, Infosys 30%, TCS 20%
    # Fund B: Infosys 40%, TCS 25%, HDFC 35%
    # Overlap(A,B) = min(30,40) + min(20,25) = 30 + 20 = 50
    constituents = {
        "ISIN_A": {"Reliance": 50.0, "Infosys": 30.0, "TCS": 20.0},
        "ISIN_B": {"Infosys": 40.0, "TCS": 25.0, "HDFC": 35.0},
    }
    holdings = [_holding("ISIN_A", 0, 0), _holding("ISIN_B", 0, 0)]
    matrix = overlap_matrix(holdings, constituents)

    assert "ISIN_A" in matrix
    assert "ISIN_B" in matrix
    # Symmetric
    assert abs(matrix["ISIN_A"]["ISIN_B"] - 50.0) < 0.01
    assert abs(matrix["ISIN_B"]["ISIN_A"] - 50.0) < 0.01
    # Diagonal omitted
    assert "ISIN_A" not in matrix.get("ISIN_A", {})
    assert "ISIN_B" not in matrix.get("ISIN_B", {})


def test_overlap_matrix_no_shared_stocks():
    constituents = {
        "ISIN_X": {"StockA": 100.0},
        "ISIN_Y": {"StockB": 100.0},
    }
    holdings = [_holding("ISIN_X", 0, 0), _holding("ISIN_Y", 0, 0)]
    matrix = overlap_matrix(holdings, constituents)
    assert matrix["ISIN_X"]["ISIN_Y"] == 0.0
    assert matrix["ISIN_Y"]["ISIN_X"] == 0.0


def test_overlap_matrix_three_funds():
    constituents = {
        "F1": {"S1": 60.0, "S2": 40.0},
        "F2": {"S2": 50.0, "S3": 50.0},
        "F3": {"S1": 30.0, "S3": 70.0},
    }
    holdings = [_holding("F1", 0, 0), _holding("F2", 0, 0), _holding("F3", 0, 0)]
    matrix = overlap_matrix(holdings, constituents)

    # F1 vs F2: shared S2 → min(40, 50) = 40
    assert abs(matrix["F1"]["F2"] - 40.0) < 0.01
    # F1 vs F3: shared S1 → min(60, 30) = 30
    assert abs(matrix["F1"]["F3"] - 30.0) < 0.01
    # F2 vs F3: shared S3 → min(50, 70) = 50
    assert abs(matrix["F2"]["F3"] - 50.0) < 0.01
    # Symmetric
    assert matrix["F2"]["F1"] == matrix["F1"]["F2"]
    assert matrix["F3"]["F1"] == matrix["F1"]["F3"]


# ---------------------------------------------------------------------------
# build_snapshot — end-to-end
# ---------------------------------------------------------------------------

def test_build_snapshot_totals():
    h1 = _holding("F1", 50_000, 60_000, category="Equity",
                   cashflows=[
                       CashFlow(_date("2024-01-01"), -50_000.0),
                       CashFlow(_date("2025-01-01"), 60_000.0),
                   ])
    h2 = _holding("F2", 30_000, 35_000, category="Debt",
                   cashflows=[
                       CashFlow(_date("2024-03-01"), -30_000.0),
                       CashFlow(_date("2025-01-01"), 35_000.0),
                   ])

    snap = build_snapshot([h1, h2])

    assert snap.total_invested == pytest.approx(80_000.0)
    assert snap.current_value == pytest.approx(95_000.0)
    # XIRR should be computable and positive (both funds gained)
    assert snap.xirr_pct is not None
    assert snap.xirr_pct > 0.0


def test_build_snapshot_allocation_sums_to_100():
    h1 = _holding("F1", 40_000, 40_000, category="Equity")
    h2 = _holding("F2", 60_000, 60_000, category="Debt")
    snap = build_snapshot([h1, h2])
    total = sum(snap.category_allocation.values())
    assert abs(total - 100.0) < 0.01


def test_build_snapshot_with_overlap():
    constituents = {
        "F1": {"S1": 70.0, "S2": 30.0},
        "F2": {"S1": 50.0, "S3": 50.0},
    }
    h1 = _holding("F1", 10_000, 12_000, cashflows=[
        CashFlow(_date("2024-01-01"), -10_000.0),
        CashFlow(_date("2025-01-01"), 12_000.0),
    ])
    h2 = _holding("F2", 10_000, 11_000, cashflows=[
        CashFlow(_date("2024-01-01"), -10_000.0),
        CashFlow(_date("2025-01-01"), 11_000.0),
    ])
    snap = build_snapshot([h1, h2], constituents=constituents)
    # Overlap F1/F2: min(70,50) = 50
    assert abs(snap.overlap_matrix["F1"]["F2"] - 50.0) < 0.01


def test_build_snapshot_no_constituents_empty_overlap():
    h1 = _holding("F1", 10_000, 12_000)
    h2 = _holding("F2", 10_000, 11_000)
    snap = build_snapshot([h1, h2])
    assert snap.overlap_matrix == {}


def test_build_snapshot_xirr_none_no_cashflows():
    # Holdings with no cash flows → XIRR is None (< 2 total flows)
    h1 = _holding("F1", 10_000, 12_000)
    snap = build_snapshot([h1])
    assert snap.xirr_pct is None
