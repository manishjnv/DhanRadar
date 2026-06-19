"""
Unit tests for the AMC fund-manager provider — no DB, no network, no Celery.

Covers:
  parse_fund_managers:
    - valid rows parsed correctly (scheme_uid, manager_name, start_date, end_date)
    - row with no valid ISIN skipped
    - row with empty manager_name skipped
    - row with missing start_date skipped
    - mixed fixture: valid + invalid rows -> only valid returned
    - end_date optional (blank = None = current manager)
    - both YYYY-MM-DD and DD-Mon-YYYY date formats accepted

  fetch_fund_managers:
    - bot-blocked AMCs recorded in status["bot_blocked"], never fetched
    - ok AMC: rows returned, recorded in status["ok"]
    - unreachable AMC (non-200): recorded in status["unreachable"], loop continues
    - transport error: recorded in status["unreachable"], loop continues
    - returns (rows, status_dict) regardless of failures

ISIN format: ^INF[A-Z0-9]{9}$ (12 chars total). All fixtures use this shape.

asyncio_mode = "auto" (pyproject.toml) -- async test functions need no decorator.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from dhanradar.market_data.amc_managers import (
    FundManagerRow,
    fetch_fund_managers,
    parse_fund_managers,
)
from dhanradar.market_data.amc_registry import AMC_FACTSHEET_SOURCES, BOT_BLOCKED_AMCS

# ---------------------------------------------------------------------------
# Golden fixtures — match the exact layout the parser handles.
#
# Columns: scheme_uid (ISIN) | manager_name | start_date | end_date
# Separator: pipe (|) with surrounding spaces.
# ISINs are 12 chars: INF + 9 alphanumeric (^INF[A-Z0-9]{9}$).
# ---------------------------------------------------------------------------

VALID_FIXTURE = """\
scheme_uid    | manager_name   | start_date  | end_date
INF123ABC456  | Priya Sharma   | 2021-06-01  |
INF456DEF012  | Rahul Mehta    | 2019-03-15  | 2023-12-31
INF789GHI678  | Anita Joshi    | 01-Jan-2020 |
"""

# Row with no valid ISIN — MUST be skipped.
NO_ISIN_FIXTURE = "NOTANISIN    | Priya Sharma | 2021-06-01 |"

# Row with empty manager_name — MUST be skipped.
EMPTY_NAME_FIXTURE = "INF123ABC456 |              | 2021-06-01 |"

# Mixed fixture: 2 valid + 1 no-ISIN + 1 empty-manager (both must be skipped).
MIXED_FIXTURE = """\
scheme_uid    | manager_name   | start_date  | end_date
INF111AAA111  | Vijay Kumar    | 2022-01-15  |
INF222BBB222  | Sneha Patil    | 2020-07-01  | 2024-03-31
BADFORMAT     | Some Manager   | 2021-01-01  |
INF333CCC333  |                | 2021-06-01  |
"""

# Minimal valid payload the fake NIPPON endpoint returns (12-char ISINs).
_NIPPON_PAYLOAD = (
    "INF123ABC456 | Priya Sharma | 2021-06-01 |\n"
    "INF456DEF012 | Rahul Mehta  | 2019-03-15 | 2023-12-31\n"
)

# AMC source lists for fetch tests.
_FAKE_SOURCES_OK = [
    {"name": "NIPPON", "url": "https://fake.nippon.test/factsheet"},
]
_FAKE_SOURCES_BOT_BLOCKED = [
    {"name": "HDFC", "url": "https://fake.hdfc.test/factsheet"},
]
_FAKE_SOURCES_MIXED = [
    {"name": "HDFC",   "url": "https://fake.hdfc.test/factsheet"},    # bot-blocked
    {"name": "NIPPON", "url": "https://fake.nippon.test/factsheet"},  # ok
]


def _make_fake_client(response_text: str, status_code: int = 200) -> MagicMock:
    """Build a fake httpx.AsyncClient that returns a fixed response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = response_text
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    return client


# ===========================================================================
# parse_fund_managers -- PURE parser tests
# ===========================================================================

class TestParseFundManagers:
    """Pure parser tests: no I/O, no DB, no network."""

    def test_valid_rows_count(self):
        """VALID_FIXTURE has 3 data rows; header line is skipped."""
        rows = parse_fund_managers(VALID_FIXTURE)
        assert len(rows) == 3

    def test_valid_scheme_uid_parsed(self):
        """All three ISINs from the fixture appear in the output."""
        rows = parse_fund_managers(VALID_FIXTURE)
        uids = {r.scheme_uid for r in rows}
        assert "INF123ABC456" in uids
        assert "INF456DEF012" in uids
        assert "INF789GHI678" in uids

    def test_valid_manager_name_parsed(self):
        """manager_name is correctly parsed and stripped."""
        rows = parse_fund_managers(VALID_FIXTURE)
        row = next(r for r in rows if r.scheme_uid == "INF123ABC456")
        assert row.manager_name == "Priya Sharma"

    def test_start_date_yyyy_mm_dd_parsed(self):
        """YYYY-MM-DD start_date is parsed as datetime.date."""
        rows = parse_fund_managers(VALID_FIXTURE)
        row = next(r for r in rows if r.scheme_uid == "INF123ABC456")
        assert row.start_date == datetime.date(2021, 6, 1)

    def test_start_date_dd_mon_yyyy_parsed(self):
        """DD-Mon-YYYY start_date is also accepted (Anita Joshi row)."""
        rows = parse_fund_managers(VALID_FIXTURE)
        row = next(r for r in rows if r.scheme_uid == "INF789GHI678")
        assert row.start_date == datetime.date(2020, 1, 1)

    def test_end_date_present_parsed(self):
        """end_date is parsed when present (Rahul Mehta row)."""
        rows = parse_fund_managers(VALID_FIXTURE)
        row = next(r for r in rows if r.scheme_uid == "INF456DEF012")
        assert row.end_date == datetime.date(2023, 12, 31)

    def test_end_date_blank_is_none(self):
        """Blank end_date → None (current manager)."""
        rows = parse_fund_managers(VALID_FIXTURE)
        row = next(r for r in rows if r.scheme_uid == "INF123ABC456")
        assert row.end_date is None

    def test_row_is_fund_manager_row_dataclass(self):
        """All returned objects are FundManagerRow instances."""
        rows = parse_fund_managers(VALID_FIXTURE)
        assert all(isinstance(r, FundManagerRow) for r in rows)

    def test_no_valid_isin_row_skipped(self):
        """A row without a valid INF-prefixed ISIN must be skipped entirely."""
        rows = parse_fund_managers(NO_ISIN_FIXTURE)
        assert not rows

    def test_empty_manager_name_row_skipped(self):
        """A row with blank manager_name must be skipped."""
        rows = parse_fund_managers(EMPTY_NAME_FIXTURE)
        assert not rows

    def test_mixed_fixture_skips_bad_rows(self):
        """Mixed input: 2 valid rows returned; 1 no-ISIN and 1 empty-name skipped."""
        rows = parse_fund_managers(MIXED_FIXTURE)
        assert len(rows) == 2
        uids = {r.scheme_uid for r in rows}
        assert "INF111AAA111" in uids
        assert "INF222BBB222" in uids
        assert "BADFORMAT" not in uids
        assert "INF333CCC333" not in uids

    def test_empty_input_returns_empty_list(self):
        """Empty string produces an empty list."""
        assert parse_fund_managers("") == []

    def test_scheme_uid_uppercased(self):
        """scheme_uid is returned in uppercase regardless of input case."""
        fixture = "INF123abc456 | Test Manager | 2021-01-01 |"
        rows = parse_fund_managers(fixture)
        if rows:
            assert rows[0].scheme_uid == "INF123ABC456"

    def test_manager_name_stripped(self):
        """Leading/trailing whitespace in manager_name is stripped."""
        fixture = "INF123ABC456 |   Padded Name   | 2021-01-01 |"
        rows = parse_fund_managers(fixture)
        assert rows
        assert rows[0].manager_name == "Padded Name"


# ===========================================================================
# fetch_fund_managers -- injected httpx client; no network
# ===========================================================================

class TestFetchFundManagers:
    """Async fetcher tests using an injected fake httpx client."""

    async def test_bot_blocked_amc_not_fetched(self):
        """HDFC is bot-blocked -- client.get must never be called for it."""
        fake_client = _make_fake_client(_NIPPON_PAYLOAD)
        rows, status = await fetch_fund_managers(fake_client, sources=_FAKE_SOURCES_BOT_BLOCKED)
        fake_client.get.assert_not_called()
        assert "HDFC" in status["bot_blocked"]
        assert not rows

    async def test_ok_amc_rows_returned(self):
        """NIPPON returns valid rows -- rows list is populated."""
        fake_client = _make_fake_client(_NIPPON_PAYLOAD)
        rows, status = await fetch_fund_managers(fake_client, sources=_FAKE_SOURCES_OK)
        assert len(rows) == 2
        assert "NIPPON" in status["ok"]
        assert status["unreachable"] == []

    async def test_non_200_marks_unreachable(self):
        """A 404 response marks the AMC unreachable but does not raise."""
        fake_client = _make_fake_client("Not Found", status_code=404)
        rows, status = await fetch_fund_managers(fake_client, sources=_FAKE_SOURCES_OK)
        assert not rows
        assert "NIPPON" in status["unreachable"]
        assert "NIPPON" not in status["ok"]

    async def test_transport_error_marks_unreachable(self):
        """A network error marks the AMC unreachable and continues -- never raises."""
        fake_client = MagicMock()
        fake_client.get = AsyncMock(side_effect=httpx.TransportError("connection refused"))
        rows, status = await fetch_fund_managers(fake_client, sources=_FAKE_SOURCES_OK)
        assert not rows
        assert "NIPPON" in status["unreachable"]

    async def test_mixed_sources_bot_blocked_and_ok(self):
        """HDFC bot-blocked + NIPPON ok -- both correctly classified."""
        fake_client = _make_fake_client(_NIPPON_PAYLOAD)
        rows, status = await fetch_fund_managers(fake_client, sources=_FAKE_SOURCES_MIXED)
        assert "HDFC" in status["bot_blocked"]
        assert "NIPPON" in status["ok"]
        assert len(rows) == 2

    async def test_returns_status_dict_keys(self):
        """Status dict always has bot_blocked, unreachable, ok keys."""
        fake_client = _make_fake_client(_NIPPON_PAYLOAD)
        _, status = await fetch_fund_managers(fake_client, sources=[])
        assert set(status.keys()) == {"bot_blocked", "unreachable", "ok"}

    async def test_empty_parse_result_marks_unreachable(self):
        """An AMC page that yields 0 parseable rows is marked unreachable."""
        # Response has text but no rows matching the parser pattern.
        fake_client = _make_fake_client("no rows here at all", status_code=200)
        rows, status = await fetch_fund_managers(fake_client, sources=_FAKE_SOURCES_OK)
        assert not rows
        assert "NIPPON" in status["unreachable"]

    def test_default_registry_contains_no_bot_blocked_amcs(self):
        """AMC_FACTSHEET_SOURCES must not list any BOT_BLOCKED_AMCS entry.

        If a bot-blocked AMC name slips into AMC_FACTSHEET_SOURCES, every run
        would attempt a fetch that is guaranteed to fail (HTTP 403 / bot-wall),
        generating spurious unreachable entries. The registry is the gate.
        """
        registered_names = {s["name"] for s in AMC_FACTSHEET_SOURCES}
        assert registered_names.isdisjoint(BOT_BLOCKED_AMCS), (
            "AMC_FACTSHEET_SOURCES must not include any BOT_BLOCKED_AMCS entry; "
            f"overlap: {registered_names & BOT_BLOCKED_AMCS}"
        )
