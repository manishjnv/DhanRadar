"""
Unit tests for the manual disclosure inbox's shared intake helpers
(dhanradar/mf/manual_ingest.py) — pure logic only, no DB/Redis/network.

`intake_file()` itself (dedup + persist + enqueue) needs a real DB session
(TaskSessionLocal) and is covered as an integration test instead —
tests/integration/test_manual_ingest_intake.py.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date

from openpyxl import Workbook

from dhanradar.mf.manual_ingest import (
    ALLOWED_EXTENSIONS,
    MAX_BYTES,
    MAX_ZIP_MEMBERS,
    MAX_ZIP_TOTAL_BYTES,
    detect_amc,
    detect_amc_and_parse,
    expand_zip,
    sha256_bytes,
    stored_path_for,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_allowed_extensions_is_xls_xlsx_pdf():
    """Contract §2 — PDFs are accepted + archived (never parsed) this wave."""
    assert set(ALLOWED_EXTENSIONS) == {".xls", ".xlsx", ".pdf"}


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


# ---------------------------------------------------------------------------
# detect_amc_and_parse — amc_hint fallback (contract §3: per-AMC subfolders)
# ---------------------------------------------------------------------------


def test_detect_amc_and_parse_uses_hint_when_filename_and_scheme_undetectable():
    """Neither filename nor scheme name names a known AMC — the subfolder hint
    is the LAST-resort fallback."""
    data = _build_disclosure_xlsx("XYZ Multi Cap Fund")
    amc_name, _period, _rows = detect_amc_and_parse(data, "disclosure.xlsx", amc_hint="HDFC")
    assert amc_name == "HDFC"


def test_detect_amc_and_parse_filename_wins_over_hint():
    """Filename/content detection runs FIRST — a hint from the wrong subfolder
    must never override a real filename match."""
    data = _build_disclosure_xlsx("HDFC Flexi Cap Fund")
    amc_name, _period, _rows = detect_amc_and_parse(
        data, "HDFC_May2026_Portfolio.xlsx", amc_hint="SBI"
    )
    assert amc_name == "HDFC"


def test_detect_amc_and_parse_ignores_unknown_hint():
    """An unrecognized folder name (not in the known AMC keyword set) is
    ignored — amc_name stays None, never a guessed value."""
    data = _build_disclosure_xlsx("XYZ Multi Cap Fund")
    amc_name, _period, _rows = detect_amc_and_parse(
        data, "disclosure.xlsx", amc_hint="SomeUnknownFundHouse"
    )
    assert amc_name is None


# ---------------------------------------------------------------------------
# expand_zip — zip-bomb / abuse guards (contract §1)
# ---------------------------------------------------------------------------


def _zip_bytes(members: dict[str, bytes], *, dirs: list[str] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in dirs or []:
            zf.writestr(name + "/", "")
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_expand_zip_happy_path_multi_member():
    data = _zip_bytes(
        {
            "HDFC_June2026.xlsx": b"member-a-bytes",
            "SBI_June2026.xls": b"member-b-bytes",
            "notice.pdf": b"%PDF-1.4 fake",
        }
    )
    result = expand_zip(data, "bundle.zip")
    assert result.skipped == []
    names = {name for name, _data in result.eligible}
    assert names == {"HDFC_June2026.xlsx", "SBI_June2026.xls", "notice.pdf"}
    by_name = dict(result.eligible)
    assert by_name["HDFC_June2026.xlsx"] == b"member-a-bytes"


def test_expand_zip_skips_directories():
    data = _zip_bytes({"a.xlsx": b"bytes"}, dirs=["some_dir"])
    result = expand_zip(data, "bundle.zip")
    assert len(result.eligible) == 1
    assert result.skipped == []


def test_expand_zip_rejects_encrypted_zip_via_flag_bit(monkeypatch):
    """Stdlib zipfile can't WRITE a real encrypted zip (`writestr` always resets
    flag_bits), so fake the PKWARE traditional-encryption bit (bit 0 of
    ZipInfo.flag_bits — the same signal a real encrypted member carries) by
    patching infolist() to return it set, exactly what expand_zip() reads."""
    data = _zip_bytes({"secret.xlsx": b"irrelevant-if-encrypted"})

    real_infolist = zipfile.ZipFile.infolist

    def _fake_infolist(self):
        infos = real_infolist(self)
        for info in infos:
            info.flag_bits |= 0x1
        return infos

    monkeypatch.setattr(zipfile.ZipFile, "infolist", _fake_infolist)

    result = expand_zip(data, "bundle.zip")
    assert result.eligible == []
    assert result.skipped == [("bundle.zip", "encrypted_zip")]


def test_expand_zip_rejects_too_many_members():
    members = {f"file_{i}.xlsx": b"x" for i in range(MAX_ZIP_MEMBERS + 1)}
    data = _zip_bytes(members)
    result = expand_zip(data, "bundle.zip")
    assert result.eligible == []
    assert result.skipped == [("bundle.zip", "too_many_members")]


def test_expand_zip_skips_oversized_member():
    data = _zip_bytes({"huge.xlsx": b"0" * (MAX_BYTES + 1), "ok.xlsx": b"fine"})
    result = expand_zip(data, "bundle.zip")
    names = {name for name, _data in result.eligible}
    assert names == {"ok.xlsx"}
    assert ("huge.xlsx", "file_too_large") in result.skipped


def test_expand_zip_skips_when_total_uncompressed_exceeds_cap():
    # 5 members, each well under the 25MB per-file cap, but summing past the
    # total cap — each is all-zero bytes so the ACTUAL zip stays tiny (this is
    # the zip-bomb shape the total-cap guard exists for).
    member_size = MAX_ZIP_TOTAL_BYTES // 5 + (1024 * 1024)  # 5x this > total cap
    members = {f"member_{i}.xlsx": b"0" * member_size for i in range(5)}
    data = _zip_bytes(members)
    result = expand_zip(data, "bundle.zip")
    assert 0 < len(result.eligible) < 5  # some fit the budget, the rest don't
    reasons = {reason for _name, reason in result.skipped}
    assert "zip_total_size_exceeded" in reasons


def test_expand_zip_skips_nested_zip_never_recursed():
    inner = _zip_bytes({"HDFC.xlsx": b"inner-bytes"})
    data = _zip_bytes({"inner.zip": inner, "outer.xlsx": b"outer-bytes"})
    result = expand_zip(data, "bundle.zip")
    names = {name for name, _data in result.eligible}
    assert names == {"outer.xlsx"}
    assert ("inner.zip", "nested_zip") in result.skipped


def test_expand_zip_rejects_corrupt_zip():
    result = expand_zip(b"not-a-real-zip-file-at-all", "bundle.zip")
    assert result.eligible == []
    assert result.skipped == [("bundle.zip", "corrupt_zip")]


def test_expand_zip_skips_unsupported_extension_member():
    data = _zip_bytes({"readme.txt": b"hello", "ok.xlsx": b"fine"})
    result = expand_zip(data, "bundle.zip")
    names = {name for name, _data in result.eligible}
    assert names == {"ok.xlsx"}
    assert ("readme.txt", "unsupported_extension:.txt") in result.skipped
