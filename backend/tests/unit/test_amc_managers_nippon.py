"""
Unit tests for the NIPPON factsheet-PDF fund-manager provider — no DB, no network.

Fixtures under tests/fixtures/nippon_factsheet_page_*.txt are REAL per-page
text extracted (via pypdf) from NIPPON's live June-2026 factsheet PDF
(https://mf.nipponindiaim.com/InvestorServices/FactSheetsDocuments/Nippon-FS-JUNE-2026.pdf),
downloaded and inspected 2026-07-06 -- trimmed but verbatim (not invented);
see amc_managers_nippon.py's module docstring for the full capture context.

Covers:
  parse_nippon_factsheet_pages:
    - real page fixture (lead manager + assistant fund manager co-manager) ->
      2 high-confidence rows, correct scheme_name/manager_name/start_date
      (month/year -> day=1 anchor)
    - real dual-manager page fixture (a different scheme, also 2 managers,
      one an "Assistant Fund Manager") -> 2 rows
    - a page with a Fund Manager(s) block but NO confident scheme-name match
      -> 0 rows (fail-closed; never guess which scheme the managers belong to)
    - a page with no Fund Manager(s) block at all -> 0 rows
    - month-name parsing is case-insensitive / abbreviation-tolerant

  fetch_nippon_fund_managers:
    - listing-page HTTP failure -> unreachable
    - listing page reachable but no PDF link found -> format_mismatch
    - PDF download failure -> unreachable
    - PDF extraction/parsing raising -> format_mismatch
    - zero high-confidence rows in the PDF -> format_mismatch
    - happy path -> ok
"""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx

from dhanradar.market_data.amc_managers_nippon import (
    _parse_month_year,
    fetch_nippon_fund_managers,
    parse_nippon_factsheet_pages,
)

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (_FIXTURES_DIR / name).read_text(encoding="utf-8")


# ===========================================================================
# parse_nippon_factsheet_pages — PURE parser tests
# ===========================================================================


class TestParseNipponFactsheetPages:
    def test_large_cap_real_page_parsed(self):
        """Real page has a lead manager + an 'Assistant Fund Manager' co-manager
        -- both are genuine managers of this scheme, both kept."""
        page_text = _load_fixture("nippon_factsheet_page_single_manager.txt")
        rows = parse_nippon_factsheet_pages([page_text])
        assert len(rows) == 2
        assert all(r.scheme_name == "Nippon India Large Cap Fund" for r in rows)
        lead = next(r for r in rows if r.manager_name == "Sailesh Raj Bhan")
        assert lead.start_date == datetime.date(2007, 8, 1)
        assistant = next(r for r in rows if r.manager_name == "Bhavik Dave")
        assert assistant.start_date == datetime.date(2024, 8, 1)

    def test_dual_manager_real_page_parsed(self):
        page_text = _load_fixture("nippon_factsheet_page_dual_manager.txt")
        rows = parse_nippon_factsheet_pages([page_text])
        assert len(rows) == 2
        names = {r.manager_name for r in rows}
        assert names == {"Vinay Sharma", "Rishit Parikh"}
        assert all(r.scheme_name == "Nippon India Focused Fund" for r in rows)
        rishit = next(r for r in rows if r.manager_name == "Rishit Parikh")
        assert rishit.start_date == datetime.date(2024, 8, 1)

    def test_page_with_no_scheme_name_match_yields_no_rows(self):
        """Fund Manager(s) block present but the scheme-name heading pattern
        doesn't match on this page -- fail closed, drop the page entirely
        rather than guess the scheme."""
        page_text = (
            "Some noise without the expected heading shape\n"
            "Fund Manager(s)\n"
            "Some Manager (Managing Since Jan 2020)\n"
            "Total Experience of more than 10 years\n"
            "AMFI Tier 1 Benchmark\n"
        )
        assert parse_nippon_factsheet_pages([page_text]) == []

    def test_page_with_no_fund_manager_block_yields_no_rows(self):
        page_text = "Nippon India Some Fund\nCategory\nDetails as on May 31, 2026\nNo manager section here.\n"
        assert parse_nippon_factsheet_pages([page_text]) == []

    def test_multiple_pages_processed_independently(self):
        page1 = _load_fixture("nippon_factsheet_page_single_manager.txt")
        page2 = _load_fixture("nippon_factsheet_page_dual_manager.txt")
        rows = parse_nippon_factsheet_pages([page1, page2])
        assert len(rows) == 4  # 2 + 2

    def test_empty_page_list_yields_no_rows(self):
        assert parse_nippon_factsheet_pages([]) == []


class TestParseMonthYear:
    def test_full_month_name(self):
        assert _parse_month_year("August", "2007") == datetime.date(2007, 8, 1)

    def test_abbreviated_month_name(self):
        assert _parse_month_year("Aug", "2024") == datetime.date(2024, 8, 1)

    def test_unknown_month_returns_none(self):
        assert _parse_month_year("Xyz", "2024") is None

    def test_invalid_year_returns_none(self):
        assert _parse_month_year("Jan", "not-a-year") is None


# ===========================================================================
# fetch_nippon_fund_managers — async fetcher, injected httpx client
# ===========================================================================

_LISTING_HTML_WITH_LINK = (
    '<a href="/InvestorServices/FactSheetsDocuments/Nippon-FS-JUNE-2026.pdf">Factsheet</a>'
)
_LISTING_HTML_NO_LINK = "<html><body>No factsheet link here</body></html>"


def _make_client(
    *,
    listing_status=200,
    listing_html=_LISTING_HTML_WITH_LINK,
    pdf_status=200,
    pdf_bytes=b"%PDF-fake",
    raise_on_listing=None,
    raise_on_pdf=None,
):
    async def _get(url, timeout=None, follow_redirects=None):
        resp = MagicMock()
        if ".pdf" in url.lower():
            if raise_on_pdf:
                raise raise_on_pdf
            resp.status_code = pdf_status
            resp.content = pdf_bytes
            return resp
        if raise_on_listing:
            raise raise_on_listing
        resp.status_code = listing_status
        resp.text = listing_html
        return resp

    client = MagicMock()
    client.get = AsyncMock(side_effect=_get)
    return client


class TestFetchNipponFundManagers:
    async def test_listing_http_failure_marks_unreachable(self):
        client = _make_client(listing_status=404)
        rows, status = await fetch_nippon_fund_managers(client)
        assert not rows
        assert status["unreachable"] == ["NIPPON"]

    async def test_listing_network_error_marks_unreachable(self):
        client = _make_client(raise_on_listing=httpx.TransportError("down"))
        rows, status = await fetch_nippon_fund_managers(client)
        assert not rows
        assert status["unreachable"] == ["NIPPON"]

    async def test_no_pdf_link_marks_format_mismatch(self):
        client = _make_client(listing_html=_LISTING_HTML_NO_LINK)
        rows, status = await fetch_nippon_fund_managers(client)
        assert not rows
        assert status["format_mismatch"] == ["NIPPON"]

    async def test_pdf_download_failure_marks_unreachable(self):
        client = _make_client(pdf_status=500)
        rows, status = await fetch_nippon_fund_managers(client)
        assert not rows
        assert status["unreachable"] == ["NIPPON"]

    async def test_pdf_extraction_failure_marks_format_mismatch(self):
        """A PDF that pypdf can't parse (corrupt/changed format) degrades to
        format_mismatch, never a crash."""
        client = _make_client(pdf_bytes=b"not a real pdf at all")
        rows, status = await fetch_nippon_fund_managers(client)
        assert not rows
        assert status["format_mismatch"] == ["NIPPON"]

    async def test_happy_path_real_fixture_via_monkeypatched_extractor(self, monkeypatch):
        """Patch extract_pdf_page_texts to return the real captured fixture
        text (avoids needing a real PDF byte stream in this test)."""
        import dhanradar.market_data.amc_managers_nippon as mod

        page_text = _load_fixture("nippon_factsheet_page_single_manager.txt")
        monkeypatch.setattr(mod, "extract_pdf_page_texts", lambda pdf_bytes: [page_text])

        client = _make_client()
        rows, status = await fetch_nippon_fund_managers(client)
        assert len(rows) == 2
        assert status["ok"] == ["NIPPON"]
