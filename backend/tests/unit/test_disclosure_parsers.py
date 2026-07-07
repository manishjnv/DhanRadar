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
