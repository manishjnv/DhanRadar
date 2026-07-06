"""
Unit tests for the UTI JSON-API fund-manager provider — no DB, no network.

Fixtures under tests/fixtures/uti_*.json are REAL response snippets captured
2026-07-06 via live browser network inspection of utimf.com (trimmed, not
invented) -- see amc_managers_uti.py's module docstring for the full capture
context.

Covers:
  parse_uti_scheme_list:
    - real scheme-list snippet -> nids extracted
    - malformed shapes (no "data" key, "data" not a list) -> [] (fail closed)

  parse_uti_scheme_manager_rows:
    - real per-scheme snippet (2 co-managers) -> 2 high-confidence rows
    - date field_from_date is MM-DD-YYYY, NOT DD-MM-YYYY (regression guard —
      this is the exact ambiguity that would silently swap month/day if wrong)
    - missing/placeholder manager name -> row dropped
    - missing scheme title -> row dropped
    - unparseable date -> row dropped

  fetch_uti_fund_managers:
    - scheme-list HTTP failure -> unreachable
    - scheme-list HTTP 200 but bad JSON shape -> format_mismatch (site up, shape wrong)
    - a single bad per-scheme nid call does not abort the others (best-effort)
    - zero usable rows overall -> format_mismatch
    - happy path -> ok
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx

from dhanradar.market_data.amc_managers_uti import (
    _is_plausible_manager_name,
    _parse_mm_dd_yyyy,
    fetch_uti_fund_managers,
    parse_uti_scheme_list,
    parse_uti_scheme_manager_rows,
)

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES_DIR / name).read_text(encoding="utf-8"))


# ===========================================================================
# parse_uti_scheme_list — PURE parser tests
# ===========================================================================


class TestParseUtiSchemeList:
    def test_real_snippet_extracts_nids(self):
        """The real captured 3-scheme snippet yields exactly those 3 nids."""
        payload = _load_fixture("uti_scheme_list_snippet.json")
        nids = parse_uti_scheme_list(payload)
        assert set(nids) == {"567", "569", "2345"}

    def test_missing_data_key_returns_empty(self):
        assert parse_uti_scheme_list({"unexpected": []}) == []

    def test_data_not_a_list_returns_empty(self):
        assert parse_uti_scheme_list({"data": "not-a-list"}) == []

    def test_entry_without_nid_is_skipped(self):
        payload = {"data": [{"field_fund_name": "No Nid Fund"}, {"nid": "1"}]}
        assert parse_uti_scheme_list(payload) == ["1"]


# ===========================================================================
# parse_uti_scheme_manager_rows — PURE parser tests
# ===========================================================================


class TestParseUtiSchemeManagerRows:
    def test_real_snippet_two_comanagers_parsed(self):
        """Real captured nid=567 snippet (2 co-managers) -> 2 high-confidence rows."""
        payload = _load_fixture("uti_scheme_manager_snippet.json")
        rows = parse_uti_scheme_manager_rows(payload)
        assert len(rows) == 2
        names = {r.manager_name for r in rows}
        assert names == {"V. Srivatsa", "Jaydeep Bhowal"}
        assert all(r.scheme_name == "UTI Aggressive Hybrid Fund" for r in rows)

    def test_date_field_is_mm_dd_yyyy_not_dd_mm_yyyy(self):
        """Regression guard: '10-15-2025' has day=15 in the SECOND position,
        which is impossible under DD-MM-YYYY -- confirms the field is
        MM-DD-YYYY (Oct 15 2025), not Nov 10 2025 or any DD-MM reading."""
        payload = _load_fixture("uti_scheme_manager_snippet.json")
        rows = parse_uti_scheme_manager_rows(payload)
        bhowal = next(r for r in rows if r.manager_name == "Jaydeep Bhowal")
        assert bhowal.start_date == datetime.date(2025, 10, 15)
        srivatsa = next(r for r in rows if r.manager_name == "V. Srivatsa")
        assert srivatsa.start_date == datetime.date(2009, 11, 1)

    def test_missing_scheme_title_row_dropped(self):
        payload = {
            "rows": [{"title": "", "field_name_fund": "A Name", "field_from_date": "01-01-2020"}]
        }
        assert parse_uti_scheme_manager_rows(payload) == []

    def test_placeholder_manager_name_row_dropped(self):
        payload = {
            "rows": [
                {"title": "Some Fund", "field_name_fund": "N/A", "field_from_date": "01-01-2020"}
            ]
        }
        assert parse_uti_scheme_manager_rows(payload) == []

    def test_unparseable_date_row_dropped(self):
        payload = {
            "rows": [
                {"title": "Some Fund", "field_name_fund": "A Name", "field_from_date": "not-a-date"}
            ]
        }
        assert parse_uti_scheme_manager_rows(payload) == []

    def test_rows_not_a_list_returns_empty(self):
        assert parse_uti_scheme_manager_rows({"rows": None}) == []

    def test_empty_manager_name_dropped(self):
        payload = {
            "rows": [
                {"title": "Some Fund", "field_name_fund": "  ", "field_from_date": "01-01-2020"}
            ]
        }
        assert parse_uti_scheme_manager_rows(payload) == []


class TestHelpers:
    def test_parse_mm_dd_yyyy_valid(self):
        assert _parse_mm_dd_yyyy("08-17-2023") == datetime.date(2023, 8, 17)

    def test_parse_mm_dd_yyyy_invalid_format(self):
        assert _parse_mm_dd_yyyy("2023-08-17") is None

    def test_is_plausible_manager_name_rejects_placeholders(self):
        assert _is_plausible_manager_name("N/A") is False
        assert _is_plausible_manager_name("") is False
        assert _is_plausible_manager_name("-") is False

    def test_is_plausible_manager_name_accepts_real_name(self):
        assert _is_plausible_manager_name("V. Srivatsa") is True


# ===========================================================================
# fetch_uti_fund_managers — async fetcher, injected httpx client
# ===========================================================================


def _make_client(
    scheme_list_payload,
    manager_payloads: dict[str, dict] | None = None,
    *,
    scheme_list_status: int = 200,
):
    """Build a fake httpx.AsyncClient: first GET (scheme list) returns
    scheme_list_payload; subsequent GETs (per-nid manager detail) look up
    manager_payloads by nid embedded in the URL."""
    manager_payloads = manager_payloads or {}

    async def _get(url, timeout=None):
        resp = MagicMock()
        if "get_investor_scheme_fund" in url:
            resp.status_code = scheme_list_status
            resp.json = MagicMock(return_value=scheme_list_payload)
            return resp
        # /api/scheme_mangaer/{nid}
        nid = url.rsplit("/", 1)[-1]
        resp.status_code = 200
        resp.json = MagicMock(return_value=manager_payloads.get(nid, {"rows": []}))
        return resp

    client = MagicMock()
    client.get = AsyncMock(side_effect=_get)
    return client


class TestFetchUtiFundManagers:
    async def test_happy_path_real_fixtures(self):
        scheme_list = _load_fixture("uti_scheme_list_snippet.json")
        manager_snippet = _load_fixture("uti_scheme_manager_snippet.json")
        client = _make_client(scheme_list, {"567": manager_snippet})
        rows, status = await fetch_uti_fund_managers(client)
        assert len(rows) == 2
        assert status["ok"] == ["UTI"]
        assert status["unreachable"] == []
        assert status["format_mismatch"] == []

    async def test_scheme_list_http_failure_marks_unreachable(self):
        client = _make_client({}, scheme_list_status=500)
        rows, status = await fetch_uti_fund_managers(client)
        assert not rows
        assert status["unreachable"] == ["UTI"]

    async def test_scheme_list_bad_shape_marks_format_mismatch(self):
        client = _make_client({"unexpected": "shape"})
        rows, status = await fetch_uti_fund_managers(client)
        assert not rows
        assert status["format_mismatch"] == ["UTI"]

    async def test_scheme_list_network_error_marks_unreachable(self):
        client = MagicMock()
        client.get = AsyncMock(side_effect=httpx.TransportError("connection refused"))
        rows, status = await fetch_uti_fund_managers(client)
        assert not rows
        assert status["unreachable"] == ["UTI"]

    async def test_one_bad_nid_does_not_abort_others(self):
        scheme_list = {"data": [{"nid": "1"}, {"nid": "2"}]}
        manager_snippet_2 = {
            "rows": [
                {
                    "title": "Fund Two",
                    "field_name_fund": "Manager Two",
                    "field_from_date": "01-01-2020",
                }
            ]
        }

        async def _get(url, timeout=None):
            resp = MagicMock()
            if "get_investor_scheme_fund" in url:
                resp.status_code = 200
                resp.json = MagicMock(return_value=scheme_list)
                return resp
            if url.endswith("/1"):
                raise httpx.TransportError("nid 1 down")
            resp.status_code = 200
            resp.json = MagicMock(return_value=manager_snippet_2)
            return resp

        client = MagicMock()
        client.get = AsyncMock(side_effect=_get)
        rows, status = await fetch_uti_fund_managers(client)
        assert len(rows) == 1
        assert rows[0].manager_name == "Manager Two"
        assert status["ok"] == ["UTI"]

    async def test_zero_usable_rows_marks_format_mismatch(self):
        scheme_list = {"data": [{"nid": "1"}]}
        client = _make_client(scheme_list, {"1": {"rows": []}})
        rows, status = await fetch_uti_fund_managers(client)
        assert not rows
        assert status["format_mismatch"] == ["UTI"]
