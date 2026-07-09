"""
Unit tests for the SBI Fund-Details PDF parser (mf/disclosure_parsers.py,
2026-07-10). The flat-text fixture is VERBATIM pypdf-extracted text from the
founder's real "SBI Automotive Opportunities Fund.pdf" (whitespace-normalized
exactly as _flatten_pdf produces) — 52 such PDFs sat 'archived' while
carrying CURRENT riskometer/TER/benchmark/manager/exit-load.
"""

from __future__ import annotations

from datetime import date

from dhanradar.mf.disclosure_parsers import (
    _parse_exit_load_text,
    _scheme_master_from_flat,
    looks_like_scheme_master_pdf,
)

_REAL_FLAT = (
    "Fund Details For SBI Automotive Opportunities Fund "
    "Fund Name SBI Automotive Opportunities Fund "
    "Options Names Direct Plan - Growth Direct Plan - IDCW Regular Plan - Growth "
    "Regular Plan - IDCW "
    "Fund Type An open-ended equity scheme following automotive & allied business "
    "activities theme "
    "Riskometer At Launch VERY HIGH "
    "Riskometer As on Date VERY HIGH "
    "Category as per SEBI categorization Circular EQUITY "
    "Face Value 10.0000 "
    "NFO Open Date 17-May-2024 NFO Close Date 31-May-2024 Allotment Date 05-Jun-2024 "
    "Reopen Date Maturity Date "
    "Benchmark(Tier 1) Nifty Auto Tri "
    "Benchmark(Tier 2) NA "
    "Fund Manager Mr. Tanmaya Desai "
    "Fund Manager Type Mr. Tanmaya Desai:Primary Equity "
    "Fund Manager From Date Mr. Tanmaya Desai:05-Jun-2024 "
    "Annual Expense (Stated Maximum) Direct Plan - 0.65 "
    "Exit Load ( If Applicable) For exit within 30 days from the date of allotment - 1%. "
    "For exit after 30 days from the date of allotment - Nil. "
    "Custodian SBI-SG Global Securities Services"
)


def test_real_pdf_text_parses_every_field():
    parsed = _scheme_master_from_flat(_REAL_FLAT)
    assert parsed["scheme_name"] == "SBI Automotive Opportunities Fund"
    assert parsed["risk_band"] == "Very High"  # canonicalized regulatory band
    assert parsed["benchmark_tier1"] == "Nifty Auto Tri"
    assert parsed["ter_pct"] == 0.65
    assert parsed["manager_pairs"] == [("Mr. Tanmaya Desai", date(2024, 6, 5))]
    assert parsed["exit_load_pct"] == 1.0
    assert parsed["exit_load_days"] == 30


def test_exit_load_text_variants():
    assert _parse_exit_load_text(
        "( If Applicable) For exit within 30 days from the date of allotment - 1%. "
        "For exit after 30 days from the date of allotment - Nil."
    ) == (1.0, 30)
    assert _parse_exit_load_text("NIL") == (0.0, None)  # a real fact, kept
    assert _parse_exit_load_text("") == (None, None)  # unstated → never guessed
    assert _parse_exit_load_text("1% within 12 months") == (1.0, 360)


def test_pdf_sniff_rejects_non_pdf_bytes():
    assert not looks_like_scheme_master_pdf(b"PK\x03\x04 xlsx bytes")
    assert not looks_like_scheme_master_pdf(b"<html>fund details for x</html>")
    assert not looks_like_scheme_master_pdf(b"%PDF-1.7 truncated garbage")
