"""Unit tests for Feature 5 — market-wide category rank.

Coverage:
1. Rank ordering: higher-scored fund gets lower rank number.
2. Deterministic tiebreaker: equal scores → alphabetical ISIN.
3. FundReportItem serialization: unified_score NEVER appears (non-neg #2).
4. assemble_report: category_rank / category_total injected from rank_by_isin.
"""

from __future__ import annotations

from dhanradar.mf.schemas import FundReportItem, PortfolioReport
from dhanradar.mf.service import assemble_report

# ---------------------------------------------------------------------------
# 1. Rank ordering
# ---------------------------------------------------------------------------

def test_rank_ordering_higher_score_gets_lower_rank():
    """Fund with the higher unified_score should be assigned rank 1."""
    # Simulate what _compute_market_ranks_pipeline does before writing to DB.
    scored = [
        ("INE000A01011", 72, "in_form"),
        ("INE000A01022", 45, "on_track"),
    ]
    scored.sort(key=lambda x: (-x[1], x[0]))
    ranks = {isin: rank for rank, (isin, _, _label) in enumerate(scored, start=1)}

    assert ranks["INE000A01011"] == 1  # higher score → rank 1
    assert ranks["INE000A01022"] == 2


# ---------------------------------------------------------------------------
# 2. Deterministic tiebreaker
# ---------------------------------------------------------------------------

def test_tiebreaker_by_isin_alphabetical():
    """Equal unified_scores must be broken alphabetically by ISIN (A < B → rank 1)."""
    scored = [
        ("INE000Z99999", 55, "on_track"),
        ("INE000A00001", 55, "on_track"),
    ]
    scored.sort(key=lambda x: (-x[1], x[0]))
    ranks = {isin: rank for rank, (isin, _, _label) in enumerate(scored, start=1)}

    assert ranks["INE000A00001"] == 1  # alphabetically first → rank 1
    assert ranks["INE000Z99999"] == 2


# ---------------------------------------------------------------------------
# 3. FundReportItem serialization: unified_score must be absent
# ---------------------------------------------------------------------------

def test_fund_report_item_has_no_unified_score():
    """unified_score must never appear in the serialised FundReportItem (non-neg #2)."""
    item = FundReportItem(
        isin="INE000A01011",
        scheme_name="Test Fund",
        folio_number="12345",
        units=100.0,
        invested_amount=10000.0,
        current_value=11000.0,
        verb_label="in_form",
        confidence_band="high",
        contributing_signals=["strong_1y_return"],
        contradicting_signals=[],
        category_rank=1,
        category_total=30,
    )
    payload = item.model_dump()
    assert "unified_score" not in payload, (
        "unified_score must NEVER be serialised — it is a load-bearing non-negotiable (#2)"
    )
    assert payload["category_rank"] == 1
    assert payload["category_total"] == 30


# ---------------------------------------------------------------------------
# 4. assemble_report injects category_rank from rank_by_isin
# ---------------------------------------------------------------------------

def test_assemble_report_injects_category_rank():
    """assemble_report must populate category_rank/category_total from rank_by_isin."""
    funds = [
        {
            "isin": "INE000A01011",
            "scheme_name": "Large Cap Alpha Fund",
            "folio_number": "111",
            "units": 50.0,
            "invested_amount": 5000.0,
            "current_value": 5500.0,
            "verb_label": "in_form",
            "confidence_band": "high",
            "contributing_signals": [],
            "contradicting_signals": [],
            "previous_label": None,
            "confidence_factors": None,
        },
        {
            "isin": "INE000B02022",
            "scheme_name": "Large Cap Beta Fund",
            "folio_number": "222",
            "units": 80.0,
            "invested_amount": 8000.0,
            "current_value": 8200.0,
            "verb_label": "on_track",
            "confidence_band": "medium",
            "contributing_signals": [],
            "contradicting_signals": [],
            "previous_label": None,
            "confidence_factors": None,
        },
    ]
    rank_by_isin = {
        "INE000A01011": {"rank": 1, "total_in_cat": 30},
        "INE000B02022": {"rank": 7, "total_in_cat": 30},
    }

    report: PortfolioReport = assemble_report(
        job_id="job-test-001",
        status="done",
        snapshot={
            "total_invested": 13000.0,
            "current_value": 13700.0,
            "xirr_pct": 12.5,
            "category_allocation": {"Large Cap": 100.0},
            "overlap_matrix": {},
        },
        funds=funds,
        rank_by_isin=rank_by_isin,
    )

    by_isin = {f.isin: f for f in report.funds}
    assert by_isin["INE000A01011"].category_rank == 1
    assert by_isin["INE000A01011"].category_total == 30
    assert by_isin["INE000B02022"].category_rank == 7
    assert by_isin["INE000B02022"].category_total == 30
    # unified_score must not appear anywhere in the serialised report
    report_dict = report.model_dump()
    report_json = str(report_dict)
    assert "unified_score" not in report_json


def test_assemble_report_graceful_when_no_ranks():
    """assemble_report must return category_rank=None when rank_by_isin is empty
    (e.g. before the first nightly compute_market_ranks has run)."""
    funds = [
        {
            "isin": "INE000A01011",
            "scheme_name": "Test Fund",
            "folio_number": "111",
            "units": 50.0,
            "invested_amount": 5000.0,
            "current_value": 5500.0,
            "verb_label": "on_track",
            "confidence_band": "medium",
            "contributing_signals": [],
            "contradicting_signals": [],
            "previous_label": None,
            "confidence_factors": None,
        }
    ]

    report = assemble_report(
        job_id="job-test-002",
        status="done",
        snapshot={
            "total_invested": 5000.0,
            "current_value": 5500.0,
            "xirr_pct": None,
            "category_allocation": {},
            "overlap_matrix": {},
        },
        funds=funds,
        rank_by_isin=None,
    )

    assert report.funds[0].category_rank is None
    assert report.funds[0].category_total is None
