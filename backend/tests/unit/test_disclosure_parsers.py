"""
Unit tests for mf/disclosure_parsers.py — pure parsers for the non-portfolio
manual-ingest file classes. Synthetic workbooks reproduce the REAL layouts
observed in the founder's first batch (2026-07-07): the SEBI AAUM annexure
(AXIS/SBI shape), ICICI's annual riskometer sheet, and BOTH scheme-performance
layouts (ICICI repeating blocks; SBI per-scheme sheets with explicit labels).

Every negative case asserts the fail-closed outcome (empty result), never a
guess — a wrong AAUM/riskometer/benchmark on a fund page is worse than none.
"""

from __future__ import annotations

import io
from datetime import date

from openpyxl import Workbook

from dhanradar.mf.disclosure_parsers import (
    RISKOMETER_BANDS,
    classify_file_class,
    parse_aaum_annexure,
    parse_riskometer_annual,
    parse_scheme_master_details,
    parse_scheme_performance,
)


def _xlsx(builder) -> bytes:
    wb = Workbook()
    builder(wb)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# classify_file_class — real filenames from the founder's batch
# ---------------------------------------------------------------------------


def test_classify_real_filenames():
    assert classify_file_class("AXISAverage_Assets_Under_Management_May_2026.xlsx") == "aaum"
    assert classify_file_class("Monthly AAUM_May 2026_09062026_062604_PM.xlsx") == "aaum"
    assert classify_file_class("SBI-monthly-average-asset-under-management-may-2026.xls") == "aaum"
    assert (
        classify_file_class("HDFCMF AMC- Monthly AAUM Disclosure Report - May 2026.xls") == "aaum"
    )
    assert (
        classify_file_class("ICICIAnnual Disclosure of Scheme Riskometer_FY 2025-26.xlsx")
        == "riskometer"
    )
    assert classify_file_class("Risk o meter Summary_June 09, 2026.pdf") == "riskometer"
    assert classify_file_class("ICICIScheme Performance Disclosure.xlsx") == "performance"
    assert classify_file_class("sbimf-scheme-performance---may-2026.xlsx") == "performance"
    # Portfolio disclosures must stay on the constituents path.
    assert classify_file_class("KOTAKConsolidatedSEBIPortfolioMay2026.xlsx") == "portfolio"
    assert classify_file_class("HDFC Flexi Cap Fund - 30-June-2026.xlsx") == "portfolio"


# ---------------------------------------------------------------------------
# parse_aaum_annexure — SEBI Annexure I shape (verified vs AXIS/SBI/EDEL/HDFC)
# ---------------------------------------------------------------------------


def _build_aaum(units_note: str = "") -> bytes:
    def build(wb: Workbook) -> None:
        ws = wb.active
        ws.title = "AAUM disclosure"
        ws.append([])
        ws.append(
            [
                "Sl. No.",
                "Scheme Category/ Scheme Name",
                f"Axis Mutual Fund : Net AAUM as on  2026-05-31 {units_note}",
                None,
                "GRAND TOTAL",
            ]
        )
        ws.append([None, None, "Through Direct Plan", None, None])
        ws.append(["A)", "INCOME / DEBT ORIENTED SCHEMES", None, None, None])
        ws.append([None, "AXIS LIQUID FUND", 100.0, 200.0, 59127.66])
        ws.append([None, "SUB-TOTAL(a)", 100.0, 200.0, 59127.66])
        ws.append([None, "AXIS GILT FUND", 1.0, 2.0, 104.08])
        ws.append([None, "GRAND TOTAL", None, None, 59231.74])

    return _xlsx(build)


def test_aaum_extracts_grand_total_per_scheme_and_period():
    period, pairs = parse_aaum_annexure(_build_aaum(), ".xlsx")
    assert period == date(2026, 5, 1)  # from the header "as on 2026-05-31"
    assert ("AXIS LIQUID FUND", 59127.66) in pairs
    assert ("AXIS GILT FUND", 104.08) in pairs
    # SUB-TOTAL / GRAND TOTAL / category-header rows are never schemes.
    names = {n for n, _v in pairs}
    assert not any("total" in n.lower() for n in names)
    assert "INCOME / DEBT ORIENTED SCHEMES" not in names


def test_aaum_lakh_units_scaled_to_crore():
    _period, pairs = parse_aaum_annexure(_build_aaum(units_note="(Rs. in Lakhs)"), ".xlsx")
    liquid = dict(pairs)["AXIS LIQUID FUND"]
    assert liquid == round(59127.66 * 0.01, 2)


def test_aaum_unrecognized_layout_fails_closed():
    def build(wb: Workbook) -> None:
        ws = wb.active
        ws.append(["Some", "Other", "Sheet"])
        ws.append(["AXIS LIQUID FUND", 59127.66])

    period, pairs = parse_aaum_annexure(_xlsx(build), ".xlsx")
    assert period is None
    assert pairs == []


# ---------------------------------------------------------------------------
# parse_riskometer_annual — ICICI annual disclosure shape
# ---------------------------------------------------------------------------


def _build_riskometer() -> bytes:
    def build(wb: Workbook) -> None:
        ws = wb.active
        ws.append(
            [
                "SR No.",
                "Scheme name",
                "Risk-o-meter level as on March 31, 2025",
                "Risk-o-meter level as on March 31, 2026",
                "Number of changes",
            ]
        )
        ws.append(["1", "BHARAT 22 ETF", "Very High", "Very High", "0"])
        ws.append(["2", "ICICI Prudential Savings Fund", "Moderate", "Moderately High", "2"])
        ws.append(["3#", "ICICI Prudential New Fund", "NA", "NA", "0"])  # skipped
        ws.append(["4", "ICICI Prudential Odd Fund", "Low", "Somewhat Risky", "1"])  # invalid band

    return _xlsx(build)


def test_riskometer_takes_latest_column_and_validates_bands():
    pairs = parse_riskometer_annual(_build_riskometer(), ".xlsx")
    d = dict(pairs)
    assert d["BHARAT 22 ETF"] == "Very High"
    # LATEST column (FY-end 2026) wins — not the 2025 value.
    assert d["ICICI Prudential Savings Fund"] == "Moderately High"
    # 'NA' and non-regulatory band words are skipped verbatim — never coerced.
    assert "ICICI Prudential New Fund" not in d
    assert "ICICI Prudential Odd Fund" not in d
    assert set(d.values()) <= set(RISKOMETER_BANDS)


# ---------------------------------------------------------------------------
# parse_scheme_performance — both real layouts
# ---------------------------------------------------------------------------


def _build_icici_performance() -> bytes:
    def build(wb: Workbook) -> None:
        ws = wb.active
        ws.title = "Scheme Performance"
        ws.append([None, "ICICI Prudential Multicap Fund", "ICICI Prudential Multicap Fund"])
        ws.append(["Particulars", "1 Year", "3 Year"])
        ws.append([None, "CAGR (%)", "CAGR (%)"])  # repeated header — must NOT become a scheme
        ws.append(["Scheme", "6.90", "19.67"])
        ws.append(["NIFTY 500 Multicap 50:25:25 TRI (Benchmark)", "1.43", "16.43"])
        ws.append([])
        ws.append([None, "ICICI Prudential Liquid Fund", "ICICI Prudential Liquid Fund"])
        ws.append(["Particulars", "1 Year", "3 Year"])
        ws.append(["Scheme", "7.10", "6.50"])
        ws.append(["CRISIL Liquid Debt A-I Index (Benchmark)", "7.00", "6.40"])

    return _xlsx(build)


def test_performance_icici_block_layout():
    pairs = parse_scheme_performance(_build_icici_performance(), ".xlsx")
    d = dict(pairs)
    assert d["ICICI Prudential Multicap Fund"] == "NIFTY 500 Multicap 50:25:25 TRI"
    assert d["ICICI Prudential Liquid Fund"] == "CRISIL Liquid Debt A-I Index"
    # The repeated 'CAGR (%)' header row must never be captured as a scheme.
    assert not any("cagr" in name.lower() for name in d)
    assert d["ICICI Prudential Multicap Fund"] == "NIFTY 500 Multicap 50:25:25 TRI"
    assert d["ICICI Prudential Liquid Fund"] == "CRISIL Liquid Debt A-I Index"
    # The repeated 'CAGR (%)' header row must never be captured as a scheme.


def _build_kotak_benchmark_table() -> bytes:
    """Trimmed reproduction of Kotak's real annual riskometer file (2026-07-08):
    a plain table with a literal 'Scheme name' + 'Benchmark Name (Tier 1)'
    header — the risk-o-meter LEVEL column is genuinely blank in every real
    row (a change-COUNT disclosure, not a current-level one), but the
    benchmark column is fully populated."""

    def build(wb: Workbook) -> None:
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(["", "Disclosure of Scheme wise change in Risk-o-meter", "", "", "", ""])
        ws.append(
            [
                "Sl No.",
                "Scheme name",
                "Scheme Risk-o-meter level",
                "Changes",
                "Benchmark Name (Tier 1)",
                "Benchmark Risk-o-meter",
            ]
        )
        ws.append(["1", "Kotak Contra Fund", None, "0", "Nifty 500 TRI", None])
        ws.append(["2", "Kotak Active Momentum Fund^", None, "2", "Nifty 500 TRI", None])

    return _xlsx(build)


def test_performance_kotak_table_layout_from_a_riskometer_named_file():
    """The Kotak table shape lives inside a file classified 'riskometer' by
    filename, but its own risk-level column is blank — this parser must
    still extract the benchmark data from the SAME bytes."""
    pairs = parse_scheme_performance(_build_kotak_benchmark_table(), ".xlsx")
    d = dict(pairs)
    assert d["Kotak Contra Fund"] == "Nifty 500 TRI"
    # A trailing footnote marker ("^") must be stripped — never part of the real name.
    assert d["Kotak Active Momentum Fund"] == "Nifty 500 TRI"
    assert "Kotak Active Momentum Fund^" not in d


def test_riskometer_annual_returns_empty_when_level_column_blank():
    """Confirms the riskometer parser itself correctly returns no bands for
    this file (never fabricates one) — the benchmark data above is recovered
    by a SEPARATE parser on the same bytes, not by relaxing this one."""
    assert parse_riskometer_annual(_build_kotak_benchmark_table(), ".xlsx") == []


def _build_sbi_performance() -> bytes:
    def build(wb: Workbook) -> None:
        ws = wb.active
        ws.title = "SMEEF"
        ws.append([None, "SBI Mutual Fund", "007"])
        ws.append([None, "SCHEME NAME :", "SBI ESG Exclusionary Strategy Fund"])
        ws.append([None, "Scheme Performace", "2026-05-31"])
        ws.append([None, "Scheme Name", "CAGR\n%"])  # table header — must not steal the name
        ws.append([None, "Regular Plan", None])
        ws.append([None, "SBI ESG Exclusionary Strategy Fund", "-2.58"])
        ws.append([None, "Scheme Benchmark: NIFTY100 ESG TRI", "0.47"])
        ws.append([None, "Additional Benchmark: BSE Sensex TRI", "-7.23"])  # ignored

    return _xlsx(build)


def test_performance_sbi_sheet_layout_primary_benchmark_only():
    pairs = parse_scheme_performance(_build_sbi_performance(), ".xlsx")
    assert pairs == [("SBI ESG Exclusionary Strategy Fund", "NIFTY100 ESG TRI")]


def test_performance_unrecognized_layout_fails_closed():
    def build(wb: Workbook) -> None:
        ws = wb.active
        ws.append(["Random", "Data"])

    assert parse_scheme_performance(_xlsx(build), ".xlsx") == []


# ---------------------------------------------------------------------------
# parse_scheme_master_details — SBI's "Fund Details" HTML page (2026-07-08)
# ---------------------------------------------------------------------------


def _build_scheme_master_html(
    *, co_manager: bool = False, salutation_no_period: bool = False
) -> bytes:
    """Trimmed synthetic reproduction of the REAL label/value HTML shape
    (single scheme, no real customer data) — mirrors the exact tag nesting
    (a nested <table> inside the 'Options Names' value) that a naive
    <td>...</td> regex would mis-pair, which is why the real parser flattens
    tags to text instead of trying to walk the DOM."""
    if co_manager:
        manager_block = (
            "<tr><td>Fund Manager</td><td><table border=1>"
            "<tr><td>Mr. Ardhendu Bhattacharya (Co-Fund Manager)</td></tr>"
            "<tr><td>Ms. Nidhi Chawla</td></tr></table></td></tr>"
            "<tr><td>Fund Manager Type</td><td><table border=1>"
            "<tr><td>Mr. Ardhendu Bhattacharya (Co-Fund Manager):Primary Debt</td></tr>"
            "<tr><td>Ms. Nidhi Chawla:Primary Equity</td></tr></table></td></tr>"
            "<tr><td>Fund Manager From Date</td><td><table border=1>"
            "<tr><td>Mr. Ardhendu Bhattacharya (Co-Fund Manager):15-Sep-2025</td></tr>"
            "<tr><td>Ms. Nidhi Chawla:15-Sep-2025</td></tr></table></td></tr>"
        )
    else:
        salutation = "Ms" if salutation_no_period else "Ms."
        manager_block = (
            f"<tr><td>Fund Manager</td><td><table border=1><tr><td>{salutation} Ranjana Gupta</td></tr>"
            "</table></td></tr>"
            f"<tr><td>Fund Manager Type</td><td><table border=1><tr><td>{salutation} Ranjana Gupta:</td></tr>"
            "</table></td></tr>"
            "<tr><td>Fund Manager From Date</td><td><table border=1>"
            f"<tr><td>{salutation} Ranjana Gupta:27-Dec-2024</td></tr></table></td></tr>"
        )

    return (
        "\r\n<html><head></head><body>"
        "<div><h2>Fund Details For SBI Test Overnight Fund </h2></div>"
        "<table border=1 align='center'>"
        "<tr><td>Fund Name</td><td>SBI Test Overnight Fund</td></tr>"
        "<tr><td>Options Names</td><td><table border=1>"
        "<tr><td>Regular Plan - Growth</td></tr><tr><td>Direct Plan - Growth</td></tr>"
        "</table></td></tr>"
        "<tr><td>Fund Type</td><td>An open ended debt scheme investing in overnight securities</td></tr>"
        "<tr><td>Riskometer At Launch</td><td>Low</td></tr>"
        "<tr><td>Riskometer As on Date</td><td>LOW</td></tr>"
        "<tr><td>Category as per SEBI categorization Circular</td><td>DEBT</td></tr>"
        "<tr><td>Benchmark(Tier 1)</td><td>NIFTY 1D Rate Index</td></tr>"
        "<tr><td>Benchmark(Tier 2)</td><td>NA</td></tr>"
        f"{manager_block}"
        "<tr><td>Annual Expense (Stated Maximum)</td><td>Regular Plan: 0.13 Direct Plan : 0.07</td></tr>"
        "<tr><td>Exit Load ( If Applicable)</td><td>NIL</td></tr>"
        "<tr><td>Custodian</td><td>Test Custodian Ltd</td></tr>"
        "</table></body></html>"
    ).encode()


def test_classify_scheme_master_by_content_not_filename():
    """A per-scheme filename indistinguishable from a real portfolio
    disclosure (e.g. 'SBI Test Overnight Fund.xls') must classify as
    scheme_master when the BYTES are the Fund Details HTML page — filename
    keywords alone can't tell these apart."""
    data = _build_scheme_master_html()
    assert classify_file_class("SBI Test Overnight Fund.xls", data) == "scheme_master"
    # Without content, filename-only classification is unaffected (existing behavior).
    assert classify_file_class("SBI Test Overnight Fund.xls") == "portfolio"


def test_scheme_master_extracts_all_fields():
    parsed = parse_scheme_master_details(_build_scheme_master_html())
    assert parsed["scheme_name"] == "SBI Test Overnight Fund"
    assert parsed["risk_band"] == "Low"
    assert parsed["benchmark_tier1"] == "NIFTY 1D Rate Index"
    assert parsed["ter_pct"] == 0.13
    assert parsed["manager_pairs"] == [("Ms. Ranjana Gupta", date(2024, 12, 27))]


def test_scheme_master_salutation_without_trailing_period():
    """A real sample used 'Ms Ranjana Gupta' (no period after 'Ms') — the
    manager/date pairing regex must still match."""
    parsed = parse_scheme_master_details(_build_scheme_master_html(salutation_no_period=True))
    assert parsed["manager_pairs"] == [("Ms Ranjana Gupta", date(2024, 12, 27))]


def test_scheme_master_co_manager_designation_not_mistaken_for_next_label():
    """A co-manager designation like '(Co-Fund Manager)' literally contains
    the substring 'Fund Manager' — a naive whole-list boundary re-scan wrongly
    matches it as the next section start, truncating the real value. Both
    managers' own distinct start dates must survive intact."""
    parsed = parse_scheme_master_details(_build_scheme_master_html(co_manager=True))
    assert parsed["manager_pairs"] == [
        ("Mr. Ardhendu Bhattacharya (Co-Fund Manager)", date(2025, 9, 15)),
        ("Ms. Nidhi Chawla", date(2025, 9, 15)),
    ]


def test_scheme_master_missing_fund_name_fails_closed():
    data = b"<html><body><h2>Fund Details For nothing useful</h2><p>no table here</p></body></html>"
    assert parse_scheme_master_details(data) == {}


def test_scheme_master_unavailable_benchmark_is_none_not_literal_na():
    data = _build_scheme_master_html().replace(b"NIFTY 1D Rate Index", b"NA")
    parsed = parse_scheme_master_details(data)
    assert parsed["benchmark_tier1"] is None
