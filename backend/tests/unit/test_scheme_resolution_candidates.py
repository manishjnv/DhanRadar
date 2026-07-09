"""
Unit tests for the 2026-07-10 scheme-resolution hardening (tasks/mf.py +
mf/manual_ingest.py) — all pure logic, no DB.

Every fixture string below is REAL evidence pulled from prod on 2026-07-10:
failing `mf.manual_ingest_files.original_filename` values, scheme banners
extracted by the live parser from the founder's actual store files, and
`mf.mf_funds.scheme_name` master rows. No invented names.

The MUST-NOT-match set is the point (a wrong ISIN writes another fund's
holdings): "SBI Magnum Multicap Fund" must NEVER produce a candidate that
could hit master's "SBI Multicap Fund" (a different fund — 2022 NFO); a
house banner ("SBI MUTUAL FUND") must never become a resolution query;
closed-ended Series/FMP names must classify as not-in-master, not retry.
"""

from __future__ import annotations

import io
from datetime import date

from openpyxl import Workbook

from dhanradar.mf.manual_ingest import (
    detect_amc,
    detect_period_from_filename,
    looks_closed_ended,
)
from dhanradar.tasks.mf import (
    _amc_scheme_prefixes,
    _parse_sebi_xlsx,
    _prefix_where_clause,
    _resolution_candidates,
)

# ---------------------------------------------------------------------------
# looks_closed_ended — real failing filenames (positives) vs live open-ended
# schemes (negatives).
# ---------------------------------------------------------------------------


def test_closed_ended_positive_real_failing_filenames():
    for name in (
        "SBI Debt Fund Series C - 1.xlsx",
        "close_ended_schemes\\SBI Dual Advantage Fund Series  – XIII.xlsx",
        "SBI Tax Advantage Fund - Series I.xlsx",
        "HDFC FMP 1269D March 2023 - 30-June-2026.xlsx",
        "SBI Fixed Maturity Plan (FMP) - Series 89",
        "SBI Long Term Advantage Fund – Series V.xlsx",
    ):
        assert looks_closed_ended(name), name


def test_closed_ended_negative_open_ended_schemes():
    for name in (
        "SBI Bluchip Fund.xlsx",
        "ICICI Prudential BSE 500 ETF.xlsx",
        "SBI Multi Asset Allocation Fund.xls",
        "SBI Magnum Children's Benefit Plan.xlsx",  # "Plan" alone is not a marker
        "Aditya Birla Sun Life Frontline Equity Fund",
        "HDFC Flexi Cap Fund",
    ):
        assert not looks_closed_ended(name), name


# ---------------------------------------------------------------------------
# BHARAT 22 ETF — ICICI-managed CPSE scheme with no "ICICI" in filename,
# banner, OR master name (INF109KB15Y7). Real inbox failure 2026-07-10.
# ---------------------------------------------------------------------------


def test_bharat22_detects_as_icici_pru():
    assert detect_amc("BHARAT 22 ETF.xlsx") == "ICICI_PRU"
    assert detect_amc("BHARAT 22 ETF") == "ICICI_PRU"  # scheme-banner fallback


def test_icici_prefixes_include_bharat22():
    prefixes = _amc_scheme_prefixes("ICICI_PRU")
    assert "ICICI%" in prefixes
    assert "BHARAT 22%" in prefixes


def test_default_prefix_unchanged_for_other_amcs():
    assert _amc_scheme_prefixes("KOTAK") == ["KOTAK%"]
    assert _amc_scheme_prefixes("MIRAE") == ["Mirae Asset%"]


def test_prefix_where_clause_binds_every_prefix():
    sql, binds = _prefix_where_clause(["ICICI%", "BHARAT 22%"])
    assert sql == "(scheme_name ILIKE :p0 OR scheme_name ILIKE :p1)"
    assert binds == {"p0": "ICICI%", "p1": "BHARAT 22%"}


# ---------------------------------------------------------------------------
# detect_period_from_filename — target-maturity names must not become the
# disclosure month (root cause of 244 future-dated prod constituent rows).
# ---------------------------------------------------------------------------


def test_filename_period_rejects_target_maturity_year():
    assert (
        detect_period_from_filename("ICICI Prudential Nifty SDL Sep 2027 Index Fund.xlsx") is None
    )
    assert (
        detect_period_from_filename("ICICI Prudential Nifty G-Sec Dec 2030 Index Fund.xlsx") is None
    )


def test_filename_period_still_reads_real_past_months():
    assert detect_period_from_filename("KotakEquityPortfolioMay2026.xlsx") == date(2026, 5, 1)
    assert detect_period_from_filename("EDEL Notes 31-May-2026_.xlsx") == date(2026, 5, 1)


def test_filename_period_skips_future_match_and_finds_past_one():
    # Maturity month in the scheme name + a real disclosure month later on —
    # the future match is skipped, scanning continues to the plausible one.
    got = detect_period_from_filename("ICICI Nifty SDL Sep 2027 Index Fund May 2026.xlsx")
    assert got == date(2026, 5, 1)


# ---------------------------------------------------------------------------
# _resolution_candidates — rename aliases + "(formerly/earlier known as)".
# ---------------------------------------------------------------------------


def test_candidates_plain_name_is_passthrough():
    # No alias, no clause → exactly the old behavior: one candidate, verbatim.
    assert _resolution_candidates("ICICI Prudential Credit Risk Fund") == [
        "ICICI Prudential Credit Risk Fund"
    ]


def test_candidates_alias_redirects_renamed_scheme():
    # Real banner (SBI historical archive) → verified current master name.
    got = _resolution_candidates("SBI Blue Chip Fund")
    assert got[0] == "SBI Large Cap Fund"
    assert "SBI Blue Chip Fund" in got  # raw form still tried last


def test_candidates_alias_is_case_insensitive():
    assert _resolution_candidates("SBI MAGNUM TAXGAIN SCHEME")[0] == "SBI ELSS Tax Saver Fund"


def test_candidates_earlier_known_as_bracket_form():
    # Real banner, verbatim from the founder's store file (2026-07-10).
    got = _resolution_candidates("SBI Flexicap Fund [earlier known as SBI Magnum Multicap Fund]")
    assert got[0] == "SBI Flexicap Fund"


def test_candidates_formerly_known_as_paren_form():
    # Real SBI "Fund Details" page title, verbatim.
    got = _resolution_candidates(
        "SBI ELSS Tax Saver Fund (formerly known as SBI Long Term Equity Fund)"
    )
    assert got[0] == "SBI ELSS Tax Saver Fund"


def test_candidates_previously_known_as_with_embedded_newline():
    # Real banner, verbatim from the one residual failed file (Mar-2020 SBI
    # Taxgain): "Previously" (not formerly/earlier) + an embedded newline
    # before the paren.
    got = _resolution_candidates(
        "SBI Long Term Equity Fund\n(Previously known as SBI Magnum Taxgain Scheme)"
    )
    assert got[0] == "SBI ELSS Tax Saver Fund"


def test_candidates_never_query_the_wrong_sibling_fund():
    """MUST-NOT-match: master holds BOTH "SBI Flexicap Fund" (renamed Magnum
    Multicap) and "SBI Multicap Fund" (different fund, 2022 NFO). No candidate
    for the old name may be the sibling's name."""
    for banner in (
        "SBI Magnum Multicap Fund",
        "SBI Flexicap Fund [earlier known as SBI Magnum Multicap Fund]",
    ):
        for candidate in _resolution_candidates(banner):
            assert candidate != "SBI Multicap Fund", banner


def test_candidates_children_plan_maps_to_savings_plan_lineage():
    # Old "SBI Magnum Children's Benefit Plan/Fund" is today's Savings Plan —
    # master ALSO holds an Investment Plan (2020 launch) that must not win.
    got = _resolution_candidates("SBI Magnum Children's Benefit Fund")
    assert got[0] == "SBI Children's Fund - Savings Plan"


# ---------------------------------------------------------------------------
# _parse_sebi_xlsx guards — house banner + future as-of clamp. In-memory
# workbooks reproducing the real SBI per-scheme layout.
# ---------------------------------------------------------------------------


def _xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_house_banner_never_becomes_scheme_name():
    # Real SBI Tax Advantage Series layout: letterhead row first, real name in
    # a "SCHEME NAME :" label/value pair. Pre-fix the letterhead won the banner
    # detection and entered fuzzy resolution as a garbage query.
    data = _xlsx(
        [
            ["SBI MUTUAL FUND"],
            ["SCHEME NAME :", "SBI Tax Advantage Fund - Series I"],
            ["PORTFOLIO STATEMENT AS ON :", "2017-06-30"],
            ["Name of the Instrument / Issuer", "ISIN", "Quantity", "Market value", "% to AUM"],
            ["HDFC Bank Ltd.", "INE040A01034", "1000", "230.25", "5.10"],
        ]
    )
    rows = _parse_sebi_xlsx(data, "SBI")
    assert rows, "holding row must still extract"
    assert all(r["scheme_name"] == "SBI Tax Advantage Fund - Series I" for r in rows)


def test_future_as_of_month_is_rejected():
    # Target-maturity banner month (Sep 2027) must never become as_of_month.
    data = _xlsx(
        [
            ["ICICI Prudential Nifty SDL Sep 2027 Index Fund", "Figures as on Sep 30, 2027"],
            ["Company/Issuer/Instrument Name", "ISIN", "Quantity", "Market Value", "% to Nav"],
            ["Government Securities", "IN0020250091", "1000", "119.83", "1.99"],
        ]
    )
    rows = _parse_sebi_xlsx(data, "ICICI_PRU")
    assert all(r["as_of_month"] is None for r in rows)


def test_past_as_of_month_still_parses():
    data = _xlsx(
        [
            ["ICICI Prudential Credit Risk Fund", "Portfolio as on May 31,2026"],
            ["Company/Issuer/Instrument Name", "ISIN", "Quantity", "Market Value", "% to Nav"],
            ["EMBASSY OFFICE PARKS REIT", "INE041025011", "5598091", "23913.37", "3.98"],
        ]
    )
    rows = _parse_sebi_xlsx(data, "ICICI_PRU")
    assert rows
    assert all(r["as_of_month"] == date(2026, 5, 1) for r in rows)
