"""B98 — stale/suspended-NAV holdings must not silently skew value-weighted risk/allocation/
concentration aggregates (ADR-0039 parity: the hero summary already excludes them from
`value_priced_pct`'s live-nav coverage; this extends the SAME classifier/exclusion to the
risk-center and allocation/concentration read paths).

Pure, DB-free — exercises `_priced_holdings`/`_priced_value_pct` (the shared ADR-0039 helpers,
`dhanradar/mf/portfolio_read.py`) plus `allocation_payload`/`concentration_payload`, which are the
two read paths named in the blocker. `load_portfolio_risk`'s async DB path reuses the identical
`_priced_holdings` filter (see its `weighted()` closure) — covered end-to-end by the existing
`tests/integration/test_c3_portfolio_risk.py`; CI should add a suspended-holding case there.
"""

from __future__ import annotations

from dhanradar.mf.portfolio_read import (
    EnrichedHolding,
    PortfolioReadModel,
    _priced_holdings,
    _priced_value_pct,
    _value_buckets,
    allocation_payload,
    concentration_payload,
)


def _holding(**kw) -> EnrichedHolding:
    d = dict(
        isin="INF1",
        scheme_name="X Fund",
        category="Flexi Cap Fund",
        amc="X AMC",
        folio_number="1",
        units=10.0,
        invested=1000.0,
        current_nav=100.0,
        current_value=1000.0,
        label=None,
        confidence_band=None,
        as_of="2026-09-01",
        data_state="ledger_backed",
        value_basis="live_nav",
    )
    d.update(kw)
    return EnrichedHolding(**d)


def _rm(holdings: list[EnrichedHolding]) -> PortfolioReadModel:
    total_value = sum(h.current_value for h in holdings)
    total_invested = sum(h.invested for h in holdings)
    return PortfolioReadModel(
        holdings=holdings,
        total_invested=total_invested,
        total_value=total_value,
        xirr_pct=None,
        as_of="2026-09-01",
    )


# ---------------------------------------------------------------------------
# Regression guard: an all-fresh (all live_nav) portfolio is untouched
# ---------------------------------------------------------------------------


def test_fresh_only_allocation_and_concentration_unchanged():
    fresh_a = _holding(isin="INF1", amc="AMC A", category="Flexi Cap", current_value=6000.0)
    fresh_b = _holding(isin="INF2", amc="AMC B", category="Debt", current_value=4000.0)
    rm = _rm([fresh_a, fresh_b])

    alloc = allocation_payload(rm, "p1", by="category")
    assert alloc["value_priced_pct"] is None  # 100% priced -> no caveat, byte-identical to pre-B98
    assert alloc["total_value"] == 10000.0
    assert {b["bucket"]: b["weight_pct"] for b in alloc["buckets"]} == {
        "Flexi Cap": 60.0,
        "Debt": 40.0,
    }

    conc = concentration_payload(rm, "p1")
    assert conc["value_priced_pct"] is None
    assert conc["top_fund"] == {"name": "X Fund", "weight_pct": 60.0}
    assert conc["top_amc"] == {"name": "AMC A", "weight_pct": 60.0}
    assert conc["band"] == "very_high"  # 60% top weight, 2 funds


# ---------------------------------------------------------------------------
# One suspended/segregated (stale-NAV) holding is excluded from the weighted split
# ---------------------------------------------------------------------------


def test_stale_nav_holding_excluded_from_allocation_and_concentration():
    fresh = _holding(isin="INF1", amc="AMC A", category="Flexi Cap", current_value=8000.0)
    suspended = _holding(
        isin="INF2",
        amc="AMC B",
        category="Debt",
        current_value=2000.0,  # frozen stale-NAV price — still counted in total_value/money truth
        data_state="unpriced",
        value_basis="stale_nav",
    )
    rm = _rm([fresh, suspended])
    assert rm.total_value == 10000.0  # money truth includes the suspended holding

    alloc = allocation_payload(rm, "p1", by="category")
    assert alloc["total_value"] == 10000.0  # unchanged — money truth
    assert alloc["value_priced_pct"] == 80  # honest coverage hint
    assert [b["bucket"] for b in alloc["buckets"]] == ["Flexi Cap"]  # suspended holding excluded
    assert alloc["buckets"][0]["weight_pct"] == 100.0  # renormalized over priced-only holdings

    conc = concentration_payload(rm, "p1")
    assert conc["value_priced_pct"] == 80
    assert conc["top_fund"] == {"name": "X Fund", "weight_pct": 100.0}
    assert conc["top_amc"] == {"name": "AMC A", "weight_pct": 100.0}
    assert conc["by_amc"] == [{"name": "AMC A", "weight_pct": 100.0}]  # AMC B excluded


def test_priced_holdings_and_priced_value_pct():
    fresh = _holding(isin="INF1", current_value=7000.0)
    cost_fallback = _holding(
        isin="INF2", current_value=3000.0, data_state="unpriced", value_basis="cost_fallback"
    )
    rm = _rm([fresh, cost_fallback])
    assert [h.isin for h in _priced_holdings(rm)] == ["INF1"]
    assert _priced_value_pct(rm) == 70


# ---------------------------------------------------------------------------
# Edge: ALL holdings stale -> honest empty/insufficient state, no division by zero
# ---------------------------------------------------------------------------


def test_all_holdings_stale_no_division_by_zero():
    suspended_a = _holding(
        isin="INF1",
        amc="AMC A",
        category="Debt",
        current_value=5000.0,
        data_state="unpriced",
        value_basis="stale_nav",
    )
    suspended_b = _holding(
        isin="INF2",
        amc="AMC B",
        category="Debt",
        current_value=5000.0,
        data_state="unpriced",
        value_basis="cost_fallback",
    )
    rm = _rm([suspended_a, suspended_b])

    assert _priced_holdings(rm) == []
    assert _priced_value_pct(rm) == 0  # 0% priced, not a crash

    alloc = allocation_payload(rm, "p1", by="category")
    assert alloc["buckets"] == []  # honest empty, not a wrong weight
    assert alloc["value_priced_pct"] == 0
    assert alloc["total_value"] == 10000.0  # money truth still reported

    conc = concentration_payload(rm, "p1")
    assert conc["top_fund"] is None
    assert conc["top_amc"] is None
    assert conc["band"] is None  # honest None, no ZeroDivisionError
    assert conc["by_amc"] == []


def test_zero_total_value_portfolio_no_division_by_zero():
    rm = _rm([])
    assert _value_buckets(rm, "category") == []
    assert _priced_value_pct(rm) is None
    assert allocation_payload(rm, "p1")["buckets"] == []
    assert concentration_payload(rm, "p1")["band"] is None
