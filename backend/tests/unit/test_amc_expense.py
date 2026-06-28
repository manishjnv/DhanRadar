"""
Unit tests for the AMC expense-ratio provider — no DB, no network, no Celery.

Covers:
  parse_expense_ratios:
    - valid rows parsed correctly (ISIN, ter_pct, effective_date)
    - row with ter_pct > 10 REJECTED (out-of-range)
    - row with ter_pct <= 0 REJECTED
    - row with no valid ISIN skipped
    - mixed fixture: valid + invalid -> only valid returned

  fetch_expense_ratios:
    - bot-blocked AMCs recorded in status["bot_blocked"], never fetched
    - ok AMC: rows returned, recorded in status["ok"]
    - unreachable AMC (non-200): recorded in status["unreachable"], loop continues
    - transport error: recorded in status["unreachable"], loop continues
    - returns (rows, status_dict) regardless of failures

ISIN format: ^INF[A-Z0-9]{9}$ (12 chars total).  All fixtures use this shape.

asyncio_mode = "auto" (pyproject.toml) -- async test functions need no decorator.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from dhanradar.market_data.amc_expense import (
    ExpenseRatioRow,
    fetch_expense_ratios,
    parse_expense_ratios,
)
from dhanradar.market_data.amc_registry import AMC_FACTSHEET_SOURCES, BOT_BLOCKED_AMCS

# ---------------------------------------------------------------------------
# Golden fixture -- matches the exact layout the parser handles.
#
# Columns: ISIN | TER% | effective_date (YYYY-MM-DD)
# Separator: pipe (|) with surrounding spaces.
# ISINs are 12 chars: INF + 9 alphanumeric (^INF[A-Z0-9]{9}$).
# ---------------------------------------------------------------------------

VALID_FIXTURE = """\
ISIN         | TER%  | effective_date
INF123ABC456 | 0.50  | 2026-06-01
INF456DEF012 | 1.25  | 2026-05-15
INF789GHI678 | 2.00  | 2026-04-01
"""

# Row with ter_pct = 10.50 -- MUST be rejected (> 10).
TER_OUT_OF_RANGE_FIXTURE = "INF123ABC456 | 10.50 | 2026-06-01"

# Row with ter_pct = 0.00 -- MUST be rejected (<= 0).
TER_ZERO_FIXTURE = "INF123ABC456 | 0.00 | 2026-06-01"

# Row with no valid ISIN -- MUST be skipped.
NO_ISIN_FIXTURE = "NOTANISIN    | 0.75  | 2026-06-01"

# Mixed: 2 valid + 1 ter>10 (rejected) + 1 no-ISIN (skipped).
MIXED_FIXTURE = """\
ISIN         | TER%  | effective_date
INF111AAA111 | 0.80  | 2026-06-01
INF222BBB222 | 1.50  | 2026-05-01
INF333CCC333 | 12.00 | 2026-04-01
BADFORMAT    | 0.50  | 2026-06-01
"""

# Minimal valid payload the fake NIPPON endpoint returns (12-char ISINs).
_NIPPON_PAYLOAD = "INF123ABC456 | 0.80 | 2026-06-01\nINF456DEF012 | 1.10 | 2026-05-15\n"

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
# parse_expense_ratios -- PURE parser tests
# ===========================================================================

class TestParseExpenseRatios:
    """Pure parser tests: no I/O, no DB, no network."""

    def test_valid_rows_count(self):
        """VALID_FIXTURE has 3 data rows; header line is skipped."""
        rows = parse_expense_ratios(VALID_FIXTURE)
        assert len(rows) == 3

    def test_valid_isin_parsed(self):
        """All three ISINs from the fixture appear in the output."""
        rows = parse_expense_ratios(VALID_FIXTURE)
        isins = {r.isin for r in rows}
        assert "INF123ABC456" in isins
        assert "INF456DEF012" in isins
        assert "INF789GHI678" in isins

    def test_valid_ter_parsed(self):
        """ter_pct is correctly parsed as a float."""
        rows = parse_expense_ratios(VALID_FIXTURE)
        row = next(r for r in rows if r.isin == "INF123ABC456")
        assert row.ter_pct == pytest.approx(0.50)

    def test_valid_date_parsed(self):
        """effective_date is parsed as a datetime.date."""
        rows = parse_expense_ratios(VALID_FIXTURE)
        row = next(r for r in rows if r.isin == "INF123ABC456")
        assert row.effective_date == datetime.date(2026, 6, 1)

    def test_row_is_expense_ratio_row_dataclass(self):
        """All returned objects are ExpenseRatioRow instances."""
        rows = parse_expense_ratios(VALID_FIXTURE)
        assert all(isinstance(r, ExpenseRatioRow) for r in rows)

    def test_ter_greater_than_10_rejected(self):
        """ter_pct = 10.50 is out-of-range -- must NOT appear in output."""
        rows = parse_expense_ratios(TER_OUT_OF_RANGE_FIXTURE)
        assert not rows

    def test_ter_equal_to_zero_rejected(self):
        """ter_pct = 0.00 is invalid (must be > 0) -- must NOT appear in output."""
        rows = parse_expense_ratios(TER_ZERO_FIXTURE)
        assert not rows

    def test_no_valid_isin_row_skipped(self):
        """A row without a valid INF-prefixed ISIN must be skipped entirely."""
        rows = parse_expense_ratios(NO_ISIN_FIXTURE)
        assert not rows

    def test_mixed_fixture_only_valid_returned(self):
        """Mixed input: 2 valid rows returned; 1 ter>10 and 1 bad-ISIN skipped."""
        rows = parse_expense_ratios(MIXED_FIXTURE)
        assert len(rows) == 2
        isins = {r.isin for r in rows}
        assert "INF111AAA111" in isins
        assert "INF222BBB222" in isins
        assert "INF333CCC333" not in isins

    def test_empty_input_returns_empty_list(self):
        """Empty string produces an empty list."""
        assert not parse_expense_ratios("")

    def test_ter_exactly_10_is_valid(self):
        """ter_pct = 10.00 is the upper boundary -- must be accepted."""
        fixture = "INF999ZZZ999 | 10.00 | 2026-06-01"
        rows = parse_expense_ratios(fixture)
        assert len(rows) == 1
        assert rows[0].ter_pct == pytest.approx(10.0)

    def test_ter_just_above_0_is_valid(self):
        """ter_pct = 0.01 is the minimum valid value -- must be accepted."""
        fixture = "INF999ZZZ999 | 0.01 | 2026-06-01"
        rows = parse_expense_ratios(fixture)
        assert len(rows) == 1
        assert rows[0].ter_pct == pytest.approx(0.01)


# ===========================================================================
# fetch_expense_ratios -- injected httpx client; no network
# ===========================================================================

class TestFetchExpenseRatios:
    """Async fetcher tests using an injected fake httpx client."""

    async def test_bot_blocked_amc_not_fetched(self):
        """HDFC is bot-blocked -- client.get must never be called for it."""
        fake_client = _make_fake_client(_NIPPON_PAYLOAD)
        rows, status = await fetch_expense_ratios(fake_client, sources=_FAKE_SOURCES_BOT_BLOCKED)
        fake_client.get.assert_not_called()
        assert "HDFC" in status["bot_blocked"]
        assert not rows

    async def test_ok_amc_rows_returned(self):
        """NIPPON returns valid rows -- rows list is populated."""
        fake_client = _make_fake_client(_NIPPON_PAYLOAD)
        rows, status = await fetch_expense_ratios(fake_client, sources=_FAKE_SOURCES_OK)
        assert len(rows) == 2
        assert "NIPPON" in status["ok"]
        assert status["unreachable"] == []

    async def test_non_200_marks_unreachable(self):
        """A 404 response marks the AMC unreachable but does not raise."""
        fake_client = _make_fake_client("Not Found", status_code=404)
        rows, status = await fetch_expense_ratios(fake_client, sources=_FAKE_SOURCES_OK)
        assert not rows
        assert "NIPPON" in status["unreachable"]
        assert "NIPPON" not in status["ok"]

    async def test_transport_error_marks_unreachable(self):
        """A network error marks the AMC unreachable and continues -- never raises."""
        fake_client = MagicMock()
        fake_client.get = AsyncMock(side_effect=httpx.TransportError("connection refused"))
        rows, status = await fetch_expense_ratios(fake_client, sources=_FAKE_SOURCES_OK)
        assert not rows
        assert "NIPPON" in status["unreachable"]

    async def test_mixed_sources_bot_blocked_and_ok(self):
        """HDFC bot-blocked + NIPPON ok -- both correctly classified."""
        fake_client = _make_fake_client(_NIPPON_PAYLOAD)
        rows, status = await fetch_expense_ratios(fake_client, sources=_FAKE_SOURCES_MIXED)
        assert "HDFC" in status["bot_blocked"]
        assert "NIPPON" in status["ok"]
        assert len(rows) == 2

    async def test_returns_status_dict_keys(self):
        """Status dict always has bot_blocked, unreachable, ok keys."""
        fake_client = _make_fake_client(_NIPPON_PAYLOAD)
        _, status = await fetch_expense_ratios(fake_client, sources=[])
        assert set(status.keys()) == {"bot_blocked", "unreachable", "ok"}

    def test_default_registry_contains_no_bot_blocked_amcs(self):
        """AMC_FACTSHEET_SOURCES must not list any BOT_BLOCKED_AMCS entry.

        If a bot-blocked AMC name slips into AMC_FACTSHEET_SOURCES, every run
        would attempt a fetch that is guaranteed to fail (HTTP 403 / bot-wall),
        generating spurious unreachable entries.  The registry is the gate.
        """
        registered_names = {s["name"] for s in AMC_FACTSHEET_SOURCES}
        assert registered_names.isdisjoint(BOT_BLOCKED_AMCS), (
            "AMC_FACTSHEET_SOURCES must not include any BOT_BLOCKED_AMCS entry; "
            f"overlap: {registered_names & BOT_BLOCKED_AMCS}"
        )
