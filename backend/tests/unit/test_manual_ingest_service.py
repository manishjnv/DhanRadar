"""
Unit tests for the manual disclosure inbox's shared intake helpers
(dhanradar/mf/manual_ingest.py) — pure logic only, no DB/Redis/network.

`intake_file()` itself (dedup + persist + enqueue) needs a real DB session
(TaskSessionLocal) and is covered as an integration test instead —
tests/integration/test_manual_ingest_intake.py.
"""

from __future__ import annotations

import io
from datetime import date

from openpyxl import Workbook

from dhanradar.mf.manual_ingest import (
    ALLOWED_EXTENSIONS,
    MAX_BYTES,
    detect_amc,
    detect_amc_and_parse,
    sha256_bytes,
    stored_path_for,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_allowed_extensions_is_xls_xlsx_only():
    """Contract §2 — factsheet PDFs are a LATER parser; this wave is .xls/.xlsx only."""
    assert set(ALLOWED_EXTENSIONS) == {".xls", ".xlsx"}


def test_max_bytes_is_25mb():
    assert MAX_BYTES == 25 * 1024 * 1024


# ---------------------------------------------------------------------------
# sha256_bytes
# ---------------------------------------------------------------------------


def test_sha256_bytes_deterministic_and_distinct():
    a = sha256_bytes(b"hello world")
    b = sha256_bytes(b"hello world")
    c = sha256_bytes(b"hello world!")
    assert a == b
    assert a != c
    assert len(a) == 64  # hex digest


# ---------------------------------------------------------------------------
# stored_path_for — uuid-named on disk, extension from original_filename
# ---------------------------------------------------------------------------


def test_stored_path_for_uses_uuid_name_never_original_filename():
    path = stored_path_for("abc-123", "some user supplied name; rm -rf .xlsx")
    assert path.name == "abc-123.xlsx"
    assert "rm -rf" not in str(path)


def test_stored_path_for_xls_extension():
    path = stored_path_for("abc-123", "HDFC_disclosure.xls")
    assert path.suffix == ".xls"


# ---------------------------------------------------------------------------
# detect_amc — keyword matching (filename OR scheme name)
# ---------------------------------------------------------------------------


def test_detect_amc_matches_each_bot_blocked_amc():
    assert detect_amc("HDFC_Portfolio_May2026.xlsx") == "HDFC"
    assert detect_amc("SBI Mutual Fund disclosure") == "SBI"
    assert detect_amc("ICICI Prudential Bluechip Fund") == "ICICI_PRU"
    assert detect_amc("kotak-disclosure-2026-05.xlsx") == "KOTAK"
    assert detect_amc("AXIS Long Term Equity Fund") == "AXIS"


def test_detect_amc_returns_none_when_no_keyword_matches():
    assert detect_amc("generic_disclosure_file.xlsx") is None


# ---------------------------------------------------------------------------
# detect_amc_and_parse — real .xlsx bytes through the EXISTING SEBI parser
# (_parse_sebi_xlsx, dhanradar/tasks/mf.py) — never a second parser.
# ---------------------------------------------------------------------------


def _build_disclosure_xlsx(scheme_name: str) -> bytes:
    """A trimmed but structurally real SEBI-format monthly disclosure: an
    'as on' date header, one scheme-name row, a column header row, two holding
    rows, and a 'Net Assets' total row (the AUM-extraction row, §8.4)."""
    wb = Workbook()
    ws = wb.active
    ws.append(["Portfolio as on 31-May-2026"])
    ws.append([scheme_name])
    ws.append(["Name of Instrument", "ISIN", "% to NAV", "Market Value"])
    ws.append(["HDFC Bank Ltd", "INE040A01034", "5.00", "1234.56"])
    ws.append(["ICICI Bank Ltd", "INE090A01021", "4.50", "1000.00"])
    ws.append(["Net Assets", "", "100.00", "24000.00"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_detect_amc_and_parse_filename_detection():
    data = _build_disclosure_xlsx("HDFC Flexi Cap Fund")
    amc_name, period, rows = detect_amc_and_parse(data, "HDFC_May2026_Portfolio.xlsx")
    assert amc_name == "HDFC"
    assert period == date(2026, 5, 1)
    assert len(rows) == 3  # 2 holdings + 1 total row
    assert any(r["constituent_name"] == "HDFC Bank Ltd" for r in rows)
    total_row = next(r for r in rows if r.get("is_total_row"))
    assert total_row["market_value_cr"] == 240.0  # 24000.00 lakh -> crore


def test_detect_amc_and_parse_falls_back_to_scheme_name_when_filename_uninformative():
    """A generically-named upload ('disclosure.xlsx') still resolves the AMC from
    the parsed scheme name — filename detection is a shortcut, not the only path."""
    data = _build_disclosure_xlsx("HDFC Flexi Cap Fund")
    amc_name, period, rows = detect_amc_and_parse(data, "disclosure.xlsx")
    assert amc_name == "HDFC"
    assert period == date(2026, 5, 1)
    assert len(rows) == 3


def test_detect_amc_and_parse_undetectable_amc_returns_none():
    """Neither the filename nor the scheme name names a known AMC — the caller
    (tasks/manual_ingest.py::parse_manual_disclosure_file) treats this as
    status='unsupported', never a guess."""
    data = _build_disclosure_xlsx("XYZ Multi Cap Fund")
    amc_name, _period, rows = detect_amc_and_parse(data, "disclosure_file.xlsx")
    assert amc_name is None
    assert len(rows) == 3  # still parsed — only AMC detection failed
