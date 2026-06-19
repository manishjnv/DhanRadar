"""
Unit tests for AMFI Scheme Master provider — no DB, no network, no Celery worker.

Covers:
  - parse_scheme_master: ISIN preference (growth before reinvest), date parsing,
    invalid-ISIN rows skipped, closure_date parsed, amc_name / scheme_type /
    scheme_category populated.
  - fetch_scheme_master: injected fake AsyncClient — 200 returns text, non-200
    raises ProviderError, empty body raises ProviderError, transport error raises
    ProviderError.

asyncio_mode = "auto" (pyproject.toml) — async test functions need no decorator.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from dhanradar.market_data.amfi_scheme_master import (
    SCHEME_MASTER_URL,
    SchemeMasterRow,
    fetch_scheme_master,
    parse_scheme_master,
)
from dhanradar.market_data.exceptions import ProviderError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Realistic semicolon-delimited scheme master fixture (11 fields per row).
# Header row + 3 data rows + 1 no-ISIN row + 1 closure_date row.
SCHEME_MASTER_FIXTURE = """\
AMC;Code;Scheme Name;Scheme Type;Scheme Category;Scheme NAV Name;Scheme Minimum Amount;Launch Date;Closure Date;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment
HDFC Mutual Fund;119551;HDFC Top 100 Fund - Direct Plan - Growth;Open Ended Schemes;Equity Scheme - Large Cap Fund;HDFC Top 100 Fund - Direct Plan - Growth Option;100;01-Jan-2013;;INF179KB1HA2;-
Nippon India Mutual Fund;118701;Nippon India Large Cap Fund - Regular Plan - Dividend;Open Ended Schemes;Equity Scheme - Large Cap Fund;Nippon Large Cap - Regular - Div;500;01-Aug-2004;;INF204K01EY6;INF204K01EZ3
No ISIN Fund Limited;999001;Ghost Fund - Growth;Open Ended Schemes;Equity Scheme;Ghost Fund NAV;500;01-Jun-2020;;-;-
Taurus Mutual Fund;140005;Taurus Bonanza Fund - Growth;Close Ended Schemes;Income;Taurus Bonanza - Growth;5000;15-Jan-2000;31-Mar-2019;INF090I01AA1;-
"""

# Minimal fixture with only the header and one valid row (no trailing newline edge).
MINIMAL_FIXTURE = (
    "AMC;Code;Scheme Name;Scheme Type;Scheme Category;Scheme NAV Name;"
    "Scheme Minimum Amount;Launch Date;Closure Date;"
    "ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment\n"
    "SBI Mutual Fund;119300;SBI Blue Chip Fund - Direct Plan - Growth;"
    "Open Ended Schemes;Equity Scheme - Large Cap Fund;"
    "SBI Blue Chip Direct Growth;500;14-Feb-2006;;INF200KA1UC0;INF200KA1UD8\n"
)


# ---------------------------------------------------------------------------
# parse_scheme_master — pure tests, no network/DB
# ---------------------------------------------------------------------------


class TestParseSchemeMaster:
    def test_header_row_skipped(self):
        rows = parse_scheme_master(SCHEME_MASTER_FIXTURE)
        # No row should have 'AMC' or 'Code' as amfi_code
        assert all(r.amfi_code != "Code" for r in rows)

    def test_blank_lines_skipped(self):
        text = "\n\n" + MINIMAL_FIXTURE + "\n\n"
        rows = parse_scheme_master(text)
        assert len(rows) == 1

    def test_no_isin_row_skipped(self):
        """Row with both ISIN fields as '-' must be excluded from output."""
        rows = parse_scheme_master(SCHEME_MASTER_FIXTURE)
        amfi_codes = [r.amfi_code for r in rows]
        assert "999001" not in amfi_codes

    def test_returns_three_valid_rows(self):
        """Fixture has 3 rows with valid ISINs (1 no-ISIN row skipped)."""
        rows = parse_scheme_master(SCHEME_MASTER_FIXTURE)
        assert len(rows) == 3

    def test_growth_isin_preferred_when_both_present(self):
        """Row 2: isin_growth=INF204K01EY6, isin_reinvest=INF204K01EZ3 → growth wins."""
        rows = parse_scheme_master(SCHEME_MASTER_FIXTURE)
        nippon = next(r for r in rows if r.amfi_code == "118701")
        assert nippon.isin_growth == "INF204K01EY6"
        assert nippon.isin_reinvest == "INF204K01EZ3"

    def test_growth_isin_only_when_reinvest_missing(self):
        """Row 1 (HDFC): isin_reinvest is '-' → isin_reinvest=None."""
        rows = parse_scheme_master(SCHEME_MASTER_FIXTURE)
        hdfc = next(r for r in rows if r.amfi_code == "119551")
        assert hdfc.isin_growth == "INF179KB1HA2"
        assert hdfc.isin_reinvest is None

    def test_closure_date_parsed(self):
        """Taurus row has closure_date 31-Mar-2019."""
        rows = parse_scheme_master(SCHEME_MASTER_FIXTURE)
        taurus = next(r for r in rows if r.amfi_code == "140005")
        assert taurus.closure_date == datetime.date(2019, 3, 31)

    def test_launch_date_parsed(self):
        rows = parse_scheme_master(SCHEME_MASTER_FIXTURE)
        hdfc = next(r for r in rows if r.amfi_code == "119551")
        assert hdfc.launch_date == datetime.date(2013, 1, 1)

    def test_empty_closure_date_is_none(self):
        rows = parse_scheme_master(SCHEME_MASTER_FIXTURE)
        hdfc = next(r for r in rows if r.amfi_code == "119551")
        assert hdfc.closure_date is None

    def test_scheme_category_populated(self):
        rows = parse_scheme_master(SCHEME_MASTER_FIXTURE)
        hdfc = next(r for r in rows if r.amfi_code == "119551")
        assert hdfc.scheme_category == "Equity Scheme - Large Cap Fund"

    def test_scheme_type_populated(self):
        rows = parse_scheme_master(SCHEME_MASTER_FIXTURE)
        hdfc = next(r for r in rows if r.amfi_code == "119551")
        assert hdfc.scheme_type == "Open Ended Schemes"

    def test_amc_name_populated(self):
        rows = parse_scheme_master(SCHEME_MASTER_FIXTURE)
        hdfc = next(r for r in rows if r.amfi_code == "119551")
        assert hdfc.amc_name == "HDFC Mutual Fund"

    def test_scheme_name_populated(self):
        rows = parse_scheme_master(SCHEME_MASTER_FIXTURE)
        hdfc = next(r for r in rows if r.amfi_code == "119551")
        assert hdfc.scheme_name == "HDFC Top 100 Fund - Direct Plan - Growth"

    def test_invalid_isin_format_skipped(self):
        """An ISIN that doesn't match ^INF[A-Z0-9]{9}$ must cause row skip."""
        bad_fixture = (
            "AMC;Code;Scheme Name;Scheme Type;Scheme Category;Scheme NAV Name;"
            "Scheme Minimum Amount;Launch Date;Closure Date;"
            "ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment\n"
            "TestAMC;99999;Bad ISIN Fund;Open;Equity;Nav;500;01-Jun-2020;;"
            "BADFORMAT;-\n"
        )
        rows = parse_scheme_master(bad_fixture)
        assert rows == []

    def test_reinvest_isin_used_when_growth_invalid(self):
        """When isin_growth is '-' but isin_reinvest is valid, reinvest is used."""
        reinvest_only = (
            "AMC;Code;Scheme Name;Scheme Type;Scheme Category;Scheme NAV Name;"
            "Scheme Minimum Amount;Launch Date;Closure Date;"
            "ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment\n"
            "SomeAMC;77001;Reinvest Only Fund;Open;Equity;Nav;500;01-Jun-2020;;"
            "-;INF090I01RR5\n"
        )
        rows = parse_scheme_master(reinvest_only)
        assert len(rows) == 1
        assert rows[0].isin_growth is None
        assert rows[0].isin_reinvest == "INF090I01RR5"

    def test_returns_scheme_master_row_instances(self):
        rows = parse_scheme_master(MINIMAL_FIXTURE)
        assert all(isinstance(r, SchemeMasterRow) for r in rows)

    def test_both_isins_populated_when_both_valid(self):
        rows = parse_scheme_master(MINIMAL_FIXTURE)
        # SBI row: growth=INF200KA1UC0, reinvest=INF200KA1UD8
        assert rows[0].isin_growth == "INF200KA1UC0"
        assert rows[0].isin_reinvest == "INF200KA1UD8"

    def test_empty_text_returns_empty_list(self):
        assert parse_scheme_master("") == []

    def test_only_header_returns_empty_list(self):
        header = (
            "AMC;Code;Scheme Name;Scheme Type;Scheme Category;Scheme NAV Name;"
            "Scheme Minimum Amount;Launch Date;Closure Date;"
            "ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment"
        )
        assert parse_scheme_master(header) == []


# ---------------------------------------------------------------------------
# fetch_scheme_master — fake client, no network
# ---------------------------------------------------------------------------


def _make_fake_client(text: str, status_code: int = 200) -> MagicMock:
    """Return a MagicMock httpx.AsyncClient that returns the given response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    return client


class TestFetchSchemeMaster:
    async def test_returns_text_on_200(self):
        client = _make_fake_client(MINIMAL_FIXTURE)
        result = await fetch_scheme_master(client)
        assert result == MINIMAL_FIXTURE

    async def test_calls_correct_url(self):
        client = _make_fake_client(MINIMAL_FIXTURE)
        await fetch_scheme_master(client)
        call_args = client.get.call_args
        url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
        assert url == SCHEME_MASTER_URL

    async def test_raises_provider_error_on_non_200(self):
        client = _make_fake_client("error page", status_code=503)
        with pytest.raises(ProviderError) as exc_info:
            await fetch_scheme_master(client)
        assert exc_info.value.provider == "amfi_scheme_master"
        assert "503" in str(exc_info.value)

    async def test_raises_provider_error_on_404(self):
        client = _make_fake_client("not found", status_code=404)
        with pytest.raises(ProviderError):
            await fetch_scheme_master(client)

    async def test_raises_provider_error_on_empty_body(self):
        client = _make_fake_client("")
        with pytest.raises(ProviderError) as exc_info:
            await fetch_scheme_master(client)
        assert "Empty" in str(exc_info.value) or "empty" in str(exc_info.value).lower()

    async def test_raises_provider_error_on_whitespace_only_body(self):
        client = _make_fake_client("   \n  ")
        with pytest.raises(ProviderError):
            await fetch_scheme_master(client)

    async def test_raises_provider_error_on_timeout(self):
        import httpx as _httpx

        client = MagicMock()
        client.get = AsyncMock(side_effect=_httpx.TimeoutException("timeout"))
        with pytest.raises(ProviderError):
            await fetch_scheme_master(client)

    async def test_raises_provider_error_on_transport_error(self):
        import httpx as _httpx

        client = MagicMock()
        client.get = AsyncMock(side_effect=_httpx.TransportError("refused"))
        with pytest.raises(ProviderError):
            await fetch_scheme_master(client)
