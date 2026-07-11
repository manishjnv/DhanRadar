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
    parse_amfi_aaum,
    parse_riskometer_annual,
    parse_scheme_master_details,
    parse_scheme_performance,
    parse_ter_disclosure,
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
# parse_amfi_aaum — AMFI consolidated scheme-wise quarterly AAUM
# (structure mirrors the real portal download, verified 2026-07-10)
# ---------------------------------------------------------------------------


def _build_amfi_aaum(
    title: str = (
        "Average Assets under Management (AAUM) for the quarter of April - June 2026 (Rs in Lakhs)"
    ),
) -> bytes:
    def build(wb: Workbook) -> None:
        ws = wb.active
        ws.append([title])
        ws.append(
            [
                "AMFI Code",
                "Scheme NAV Name",
                "Excluding Fund of Funds - Domestic but including Fund of Funds - Overseas",
                "Fund Of Funds - Domestic",
            ]
        )
        ws.append(["360 ONE Mutual Fund"])  # AMC section row — never a scheme
        ws.append(["Other Scheme - Other  ETFs"])  # category section row — never a scheme
        ws.append(["154366", "360 ONE MSCI India ETF", "277.38", "0"])
        ws.append([153415, "360 ONE Silver ETF", 4784.48, 0])  # numeric cells too
        ws.append(["Hybrid Scheme - Multi Asset Allocation"])
        # FoF scheme: value sits in the LAST column only
        ws.append([132175, "ABSL Aggressive Hybrid Omni FOF - Regular - IDCW", 0, 449.2])
        ws.append(["999999", "Zero AAUM Scheme", 0, 0])  # zero → skipped, never written

    return _xlsx(build)


def test_amfi_aaum_classified_by_content_not_filename():
    data = _build_amfi_aaum()
    # The portal filename is arbitrary and matches no keyword — content wins.
    assert classify_file_class("average-aum2.xlsx", data) == "amfi_aaum"
    # Without bytes there is nothing to sniff — falls through to 'portfolio'.
    assert classify_file_class("average-aum2.xlsx") == "portfolio"


def test_amfi_aaum_parses_codes_lakhs_and_quarter_period():
    period, triples = parse_amfi_aaum(_build_amfi_aaum(), ".xlsx")
    assert period == date(2026, 6, 1)  # quarter Apr–Jun → END month, day 1
    by_code = {c: (n, v) for c, n, v in triples}
    # 277.38 lakhs → 2.7738 crore (string cell)
    assert by_code["154366"] == ("360 ONE MSCI India ETF", 2.7738)
    # numeric cells parse identically
    assert by_code["153415"][1] == round(4784.48 * 0.01, 4)
    # FoF value comes from the domestic-FoF column
    assert by_code["132175"][1] == round(449.2 * 0.01, 4)
    # AMC / category section rows never parse as schemes; zero-AAUM skipped
    names = {n for _c, n, _v in triples}
    assert "360 ONE Mutual Fund" not in names
    assert "Other Scheme - Other  ETFs" not in names
    assert "999999" not in by_code


def test_amfi_aaum_unstated_units_fail_closed():
    data = _build_amfi_aaum(title="Average Assets under Management (AAUM)")
    period, triples = parse_amfi_aaum(data, ".xlsx")
    assert triples == []  # no 'lakh'/'crore' in the title → never guess 100×
    assert period is None


def test_amfi_aaum_periodless_title_returns_none_period():
    data = _build_amfi_aaum(title="Average Assets under Management (AAUM) (Rs in Lakhs)")
    period, triples = parse_amfi_aaum(data, ".xlsx")
    assert period is None  # caller must NOT fabricate aum_as_of (§8.4)
    assert len(triples) == 3


def test_ter_amfi_consolidated_layout_latest_date_wins():
    """AMFI's all-AMC TER workbook ('TER_Revised': one row per scheme per DAY,
    15 'Regular Plan - …'/'Direct Plan - …' columns) parses via the SAME
    generic detection as the per-AMC layouts — per-plan Total TER only, and
    only the LATEST date's row per scheme survives."""

    def build(wb: Workbook) -> None:
        ws = wb.active
        ws.title = "TER_Revised"
        ws.append(
            [
                "NSDL Scheme Code",
                "Scheme Name",
                "Scheme Type",
                "Scheme Category",
                "TER Date",
                "Regular Plan - Base Expense Ratio (BER) (%)",
                "Regular Plan - Brokerage cost (%)",
                "Regular Plan - Transaction Cost incurred for the purpose of execution of trade (%)",
                "Regular Plan - Statutory Levies (including GST) (%)",
                "Regular Plan - Total TER (%)",
                "Direct Plan - Base Expense Ratio (BER) (%)",
                "Direct Plan - Brokerage cost (%)",
                "Direct Plan - Transaction Cost incurred for the purpose of execution of trade (%)",
                "Direct Plan - Statutory Levies (including GST) (%)",
                "Direct Plan - Total TER (%)",
            ]
        )
        code = "360O/O/H/BHF/23/07/0007"
        # TER Date cells are genuine Excel dates (openpyxl datetime), as in
        # the real portal file — not strings.
        from datetime import datetime as _dt

        for day, reg, direct in (
            (_dt(2026, 7, 1), "1.78", "0.63"),
            (_dt(2026, 7, 8), "1.80", "0.62"),
        ):
            ws.append(
                [
                    code,
                    "360 ONE Balanced Hybrid Fund",
                    "Open Ended",
                    "Hybrid Scheme - Balanced Hybrid ",
                    day,
                    reg,
                    "0.03",
                    "0",
                    "0.38",
                    str(float(reg) + 0.41),
                    "0.46",
                    "0.03",
                    "0",
                    "0.14",
                    direct,
                ]
            )

    rows = parse_ter_disclosure(_xlsx(build), ".xlsx")
    assert len(rows) == 1  # latest date only — never one row per day
    name, ter_date, reg, direct = rows[0]
    assert name == "360 ONE Balanced Hybrid Fund"
    assert ter_date == date(2026, 7, 8)
    assert reg == round(1.80 + 0.41, 4)  # the per-plan TOTAL TER, never the BER
    assert direct == 0.62


def test_amfi_aaum_wrong_layout_fails_closed():
    def build(wb: Workbook) -> None:
        ws = wb.active
        ws.append(["Some", "Other", "Sheet"])
        ws.append(["154366", "A Fund", 100.0])

    period, triples = parse_amfi_aaum(_xlsx(build), ".xlsx")
    assert period is None
    assert triples == []


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


# ---------------------------------------------------------------------------
# parse_ter_disclosure — TER (Total Expense Ratio) disclosure, 2026-07-09
# ---------------------------------------------------------------------------


def test_classify_ter_real_filenames():
    assert classify_file_class("TotalExpenseRatio-2026-2027.xlsx") == "ter"
    assert classify_file_class("SBIcurrent-year-ter.xlsx") == "ter"
    assert classify_file_class("SBIhistorical-ter-march2026.xlsx") == "ter"
    assert classify_file_class("Expense Ratio.xlsx") == "ter"
    assert classify_file_class("HDFCMF_SCHEMES_TER_02-06-2026_1.xls") == "ter"
    # HSBC's real filename uses a plain space to delimit "Ter" (confirmed
    # 2026-07-09) — no underscore/hyphen at all, unlike every other AMC's
    # convention, so it needs the `\bter\b` word-boundary fallback.
    assert (
        classify_file_class(
            "D__Camsonline_www_HSBCFiles_Final_HSBC MF Total Exp TER Report_06072026.xlsx"
        )
        == "ter"
    )
    # "ter" must never match as a bare substring inside an unrelated word.
    assert classify_file_class("water_treatment.xlsx") == "portfolio"
    assert classify_file_class("after_hours_trading.xlsx") == "portfolio"


def test_parse_ter_disclosure_edelweiss_2row_group_title_layout():
    """Edelweiss's real layout: a free-text title banner row, a group-title
    row ("Regular Plan"/"Direct Plan") whose cells sit at arbitrary columns
    (NOT spanning the actual sub-column block), then the real 13-column
    sub-header row ending each plan's block with "Total TER (%)"."""

    def build(wb):
        ws = wb.active
        ws.append(["Total Expense Ratio Of Mutual Fund Scheme:-2026-2027"])
        ws.append([])
        ws.append(["Regular Plan", "Direct Plan"])
        ws.append(
            [
                "Scheme Name",
                "Date",
                "Base Expense Ratio (BER) (%)1",
                "Brokerage cost (%)2",
                "Transaction Cost incurred for the purpose of execution of trade (%)3",
                "Statutory Levies (including GST) (%)4",
                "Total TER (%)",
                "Base Expense Ratio (BER) (%)1",
                "Brokerage cost (%)2",
                "Transaction Cost incurred for the purpose of execution of trade (%)3",
                "Statutory Levies (including GST) (%)4",
                "Total TER (%)",
                "NSDL Scheme Code",
            ]
        )
        ws.append(
            [
                "Edelweiss Aggressive Hybrid Fund",
                "01/04/2026",
                1.63,
                0,
                0,
                0.25,
                1.88,
                0.39,
                0,
                0,
                0.07,
                0.46,
                "EDEL/O/H/AHF/09/04/0007",
            ]
        )
        ws.append(
            [
                "Edelweiss Aggressive Hybrid Fund",
                "01/05/2026",
                1.60,
                0,
                0,
                0.24,
                1.84,
                0.38,
                0,
                0,
                0.07,
                0.45,
                "EDEL/O/H/AHF/09/04/0007",
            ]
        )

    data = _xlsx(build)
    result = parse_ter_disclosure(data, ".xlsx")

    assert result == [("Edelweiss Aggressive Hybrid Fund", date(2026, 5, 1), 1.84, 0.45)]


def test_parse_ter_disclosure_sbi_single_row_prefixed_layout():
    """SBI's layout: ONE header row, every column literally prefixed
    "Regular Plan - " / "Direct Plan - "."""

    def build(wb):
        ws = wb.active
        ws.append(
            [
                "NSDL Scheme Code",
                "Scheme Name",
                "TER Date\n(DD/MM/\nYYYY)",
                "Regular Plan - Base Expense Ratio (BER) (%)",
                "Regular Plan - Brokerage cost (%)",
                "Regular Plan - Transaction Cost incurred for the purpose of execution of trade (%)",
                "Regular Plan - Statutory Levies (including GST) (%)",
                "Regular Plan - Total TER (%)",
                "Direct Plan - Base Expense Ratio (BER) (%)",
                "Direct Plan - Brokerage cost (%)",
                "Direct Plan - Transaction Cost incurred for the purpose of execution of trade (%)",
                "Direct Plan - Statutory Levies (including GST) (%)",
                "Direct Plan - Total TER (%)",
            ]
        )
        ws.append(
            [
                "SBIM/O/E/THE/97/01/0001",
                "SBI ESG Exclusionary Strategy Fund",
                "01/04/2026",
                1.61,
                0,
                0,
                0.28,
                1.89,
                1.1,
                0,
                0,
                0.19,
                1.29,
            ]
        )

    data = _xlsx(build)
    result = parse_ter_disclosure(data, ".xlsx")

    assert result == [("SBI ESG Exclusionary Strategy Fund", date(2026, 4, 1), 1.89, 1.29)]


def test_parse_ter_disclosure_absl_2row_bare_group_title_layout():
    """ABSL's layout: a 2-row header with BARE group titles ("Regular"/
    "Direct", no "Plan" suffix) sitting at their REAL (non-contiguous)
    column offsets — confirmed 2026-07-09 against the real file: "Regular"
    at column 3, "Direct" at column 8, with the sub-label row's cells
    correctly aligned underneath (not at columns 0-9) — and value cells
    stored as numeric-looking STRINGS (not genuine floats)."""

    def build(wb):
        ws = wb.active
        ws.append(
            [
                "NSDL Scheme Code",
                "Name of the scheme",
                "Date",
                "Regular",
                None,
                None,
                None,
                None,
                "Direct",
            ]
        )
        ws.append(
            [
                None,
                None,
                None,
                "Base TER(%)1",
                "Additional Expense as per Regulation 52(6A)(b)( %)2",
                "Additional Expense as per Regulation 52(6A)(c)( %)3",
                "GST (%)4",
                "Total TER (%)",
                "Base TER(%)1",
                "Additional Expense as per Regulation 52(6A)(b)( %)2",
                "Additional Expense as per Regulation 52(6A)(c)( %)3",
                "GST (%)4",
                "Total TER (%)",
            ]
        )
        ws.append(
            [
                "ABSL/O/O/DIN/23/11/0157",
                "ABSL CRISIL IBX GILT JUNE 2027 INDEX FUND",
                "01-JAN-2026",
                "0.56",
                "0",
                "0",
                "0",
                "0.56",
                "0.26",
                "0",
                "0",
                "0",
                "0.26",
            ]
        )

    data = _xlsx(build)
    result = parse_ter_disclosure(data, ".xlsx")

    assert result == [("ABSL CRISIL IBX GILT JUNE 2027 INDEX FUND", date(2026, 1, 1), 0.56, 0.26)]


def test_parse_ter_disclosure_ignores_freetext_title_banner_total_ter_match():
    """HDFC's real file titles its single sheet "Total Expense Ratio (TER)
    for Mutual Fund Schemes" — this ONE-cell banner row contains both
    "total" and "ter" as prose, which must NOT be mistaken for a genuine
    "Total TER" column header (confirmed 2026-07-09: without the >2-non-
    empty-cells guard, this produced a spurious 3rd "total ter" match and
    the whole file failed to parse)."""

    def build(wb):
        ws = wb.active
        ws.append(["Total Expense Ratio (TER) for Mutual Fund Schemes"])
        ws.append(["Regular Plan", "Direct Plan"])
        ws.append(
            [
                "Scheme Name",
                "NSDL Scheme Code",
                "Date (DD/MM/YYYY)",
                "Base Expense Ratio (BER) (%)",
                "Brokerage Cost (%)",
                "Transaction Cost incurred for the purpose of execution of trade (%)",
                "Statutory Levies (Including GST) (%)",
                "Total TER (%)",
                "Base Expense Ratio (BER) (%)",
                "Brokerage Cost (%)",
                "Transaction Cost incurred for the purpose of execution of trade (%)",
                "Statutory Levies (Including GST) (%)",
                "Total TER (%)",
            ]
        )
        ws.append(
            [
                "HDFC Arbitrage Fund",
                "HDFC/O/H/ARB/07/08/0017",
                "01-Jun-2026",
                0.79,
                0.06,
                0.09,
                1.09,
                2.03,
                0.34,
                0.06,
                0.09,
                1.02,
                1.51,
            ]
        )

    data = _xlsx(build)
    result = parse_ter_disclosure(data, ".xlsx")

    assert result == [("HDFC Arbitrage Fund", date(2026, 6, 1), 2.03, 1.51)]


def test_parse_ter_disclosure_unrecognized_layout_returns_empty():
    """A file with no Regular/Direct TER structure at all fails closed —
    never a guess."""

    def build(wb):
        ws = wb.active
        ws.append(["Just some notes about the fund house"])
        ws.append(["Nothing resembling a TER table here"])

    data = _xlsx(build)
    assert parse_ter_disclosure(data, ".xlsx") == []


# ---------------------------------------------------------------------------
# fund_performance (2026-07-10) — AMFI's Crisil-powered per-category export:
# ONLY the two factual columns (benchmark + validated riskometer band) are
# extracted; NAV/return columns are never read (house rule — returns are
# computed in-house from NAV, never ingested).
# ---------------------------------------------------------------------------


def _fund_performance_xlsx(rows_after_header=None) -> bytes:
    import io as _io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Crisil Intelligence"])
    ws.append(["Generated on: 10-Jul-2026 10:47"])
    ws.append([])
    ws.append(["Fund Performance"])
    ws.append(
        [
            "Scheme Name",
            "Benchmark",
            "Riskometer Scheme",
            "Riskometer Benchmark",
            "NAV Date",
            "NAV Regular",
            "NAV Direct",
            "Return 1 Year (%) Regular",
            "Return 1 Year (%) Direct",
            "Return 1 Year (%) Benchmark",
        ]
    )
    for row in rows_after_header or [
        [
            "Aditya Birla Sun Life Large Cap Fund",
            "Nifty 100 TRI",
            "Very High",
            "Very High",
            "2026-07-08",
            510.18,
            567.41,
            -4.95,
            -4.32,
            -3.70,
        ],
        [
            "Axis Large Cap Fund",
            "BSE 100 TRI",
            "VERY HIGH",  # case-insensitive band
            "Very High",
            "2026-07-08",
            58.91,
            68.33,
            -4.0,
            -3.17,
            -3.99,
        ],
        [
            "Broken Row Fund",
            "NA",
            "Not A Real Band",  # nothing factual -> dropped
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ],
    ]:
        ws.append(row)
    buf = _io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestFundPerformance:
    def test_sniff_and_classify(self):
        from dhanradar.mf.disclosure_parsers import classify_file_class

        data = _fund_performance_xlsx()
        # Filename is arbitrary — only the bytes decide.
        assert classify_file_class("Fund-Performance-10-Jul-2026--1047.xlsx", data) == (
            "fund_performance"
        )
        assert classify_file_class("whatever (3).xlsx", data) == "fund_performance"

    def test_parses_factual_columns_only(self):
        from dhanradar.mf.disclosure_parsers import parse_fund_performance

        triples = parse_fund_performance(_fund_performance_xlsx(), ".xlsx")
        assert triples == [
            ("Aditya Birla Sun Life Large Cap Fund", "Nifty 100 TRI", "Very High"),
            ("Axis Large Cap Fund", "BSE 100 TRI", "Very High"),  # band canonicalized
        ]

    def test_invalid_band_and_na_benchmark_fail_closed(self):
        from dhanradar.mf.disclosure_parsers import parse_fund_performance

        triples = parse_fund_performance(
            _fund_performance_xlsx(
                [
                    ["X Fund", "NA", "Extremely High", "", "", "", "", "", "", ""],
                    ["Y Fund", "Nifty 50 TRI", "garbage", "", "", "", "", "", "", ""],
                ]
            ),
            ".xlsx",
        )
        # X: no valid benchmark AND no valid band -> dropped entirely.
        # Y: benchmark kept, band fail-closed None (never guessed).
        assert triples == [("Y Fund", "Nifty 50 TRI", None)]

    def test_non_performance_workbook_is_not_sniffed(self):
        from dhanradar.mf.disclosure_parsers import _looks_like_fund_performance

        assert not _looks_like_fund_performance(b"%PDF junk")
        import io as _io

        from openpyxl import Workbook

        wb = Workbook()
        wb.active.append(["Name of the Instrument", "ISIN", "Quantity"])
        buf = _io.BytesIO()
        wb.save(buf)
        assert not _looks_like_fund_performance(buf.getvalue())


# ---------------------------------------------------------------------------
# factsheet_pdf (2026-07-11) — per-scheme AMC factsheets: the fund MANAGER
# (+ tenure), closing AUM, exit load and min amount. Fixture lines are
# verbatim pypdf-extracted text from the founder's real ICICI files.
# ---------------------------------------------------------------------------

_FACTSHEET_LINES = [
    "Portfolio as on May 31, 2026",
    "ICICI Prudential Flexicap Fund",
    "(An open ended dynamic equity scheme investing across large cap, mid cap & small cap stocks)",
    "Scheme Details",
    "Monthly AAUM as on 31-May-26 : Rs. 21,132.13 crores",
    "Closing AUM as on 31-May-26 : Rs. 21,188.99 crores `",
    "Fund Managers** :",
    "Rajat Chandak",
    "(Managing this fund since July, 2021",
    "& Overall 18 years of experience)",
    "Inception/Allotment date: 17-Jul-21",
    "Application Amount for fresh Subscription :",
    "Rs. 5,000/- (plus in multiple of Re. 1)",
    "Exit load for Redemption / Switch out :-",
    "Lumpsum & SIP / STP / SWP Option",
    "1% of the applicable NAV - If the amount sought to be",
    "redeemed or switched out is invested for a period of upto 12 months",
    "1. Different plans shall have different expense structure. The performance "
    "details provided herein are of ICICI Prudential Flexicap Fund.",
]


class TestFactsheetPdf:
    def test_parses_all_fields_from_real_lines(self, monkeypatch):
        import datetime as _dt

        from dhanradar.mf import disclosure_parsers as dp

        monkeypatch.setattr(dp, "_flatten_pdf_lines", lambda data: _FACTSHEET_LINES)
        parsed = dp.parse_factsheet_pdf(b"%PDF-fake")
        assert parsed["scheme_name"] == "ICICI Prudential Flexicap Fund"
        assert parsed["manager_pairs"] == [("Rajat Chandak", _dt.date(2021, 7, 1))]
        assert parsed["aum_crore"] == 21188.99
        assert parsed["aum_as_of"] == _dt.date(2026, 5, 31)
        assert parsed["min_lumpsum_amount"] == 5000.0
        assert parsed["exit_load_pct"] == 1.0
        assert parsed["exit_load_days"] == 360  # "upto 12 months"

    def test_disclaimer_name_wins_when_page_order_flips(self, monkeypatch):
        # Real evidence 2026-07-11: pypdf emits the disclaimer FIRST for some
        # files of the same layout — the disclaimer's own fund name is the
        # reliable strategy, never the first title-looking line.
        from dhanradar.mf import disclosure_parsers as dp

        flipped = _FACTSHEET_LINES[-1:] + _FACTSHEET_LINES[:-1]
        monkeypatch.setattr(dp, "_flatten_pdf_lines", lambda data: flipped)
        parsed = dp.parse_factsheet_pdf(b"%PDF-fake")
        assert parsed["scheme_name"] == "ICICI Prudential Flexicap Fund"

    def test_fails_closed_without_a_name(self, monkeypatch):
        from dhanradar.mf import disclosure_parsers as dp

        monkeypatch.setattr(dp, "_flatten_pdf_lines", lambda data: ["random", "text"])
        assert dp.parse_factsheet_pdf(b"%PDF-fake") == {}

    def test_sniff_rejects_non_factsheets(self):
        from dhanradar.mf.disclosure_parsers import looks_like_factsheet_pdf

        assert not looks_like_factsheet_pdf(b"PK\x03\x04 xlsx")
        assert not looks_like_factsheet_pdf(b"%PDF-1.7 garbage without markers")
