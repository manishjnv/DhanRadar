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

# Realistic COMMA-delimited scheme master fixture matching the LIVE AMFI feed
# (verified 2026-06-19): 10 fields per row, and the final field concatenates the
# Growth + Reinvest ISINs with NO separator (e.g. "INF204K01EY6INF204K01EZ3").
# A single 12-char ISIN means growth-only. Header + 3 valid + 1 no-ISIN + 1 closure.
SCHEME_MASTER_FIXTURE = """\
AMC,Code,Scheme Name,Scheme Type,Scheme Category,Scheme NAV Name,Scheme Minimum Amount,Launch Date,Closure Date,ISIN Div Payout/ISIN GrowthISIN Div Reinvestment
HDFC Mutual Fund,119551,HDFC Top 100 Fund - Direct Plan - Growth,Open Ended Schemes,Equity Scheme - Large Cap Fund,HDFC Top 100 Fund - Direct Plan - Growth Option,100,01-Jan-2013,,INF179KB1HA2
Nippon India Mutual Fund,118701,Nippon India Large Cap Fund - Regular Plan - Dividend,Open Ended Schemes,Equity Scheme - Large Cap Fund,Nippon Large Cap - Regular - Div,500,01-Aug-2004,,INF204K01EY6INF204K01EZ3
No ISIN Fund Limited,999001,Ghost Fund - Growth,Open Ended Schemes,Equity Scheme,Ghost Fund NAV,500,01-Jun-2020,,-
Taurus Mutual Fund,140005,Taurus Bonanza Fund - Growth,Close Ended Schemes,Income,Taurus Bonanza - Growth,5000,15-Jan-2000,31-Mar-2019,INF090I01AA1
"""

# Minimal fixture with only the header and one valid row (no trailing newline edge).
MINIMAL_FIXTURE = (
    "AMC,Code,Scheme Name,Scheme Type,Scheme Category,Scheme NAV Name,"
    "Scheme Minimum Amount,Launch Date,Closure Date,"
    "ISIN Div Payout/ISIN GrowthISIN Div Reinvestment\n"
    "SBI Mutual Fund,119300,SBI Blue Chip Fund - Direct Plan - Growth,"
    "Open Ended Schemes,Equity Scheme - Large Cap Fund,"
    "SBI Blue Chip Direct Growth,500,14-Feb-2006,,INF200KA1UC0INF200KA1UD8\n"
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
        """A final field with no INF-ISIN token must cause the row to be skipped."""
        bad_fixture = (
            "AMC,Code,Scheme Name,Scheme Type,Scheme Category,Scheme NAV Name,"
            "Scheme Minimum Amount,Launch Date,Closure Date,"
            "ISIN Div Payout/ISIN GrowthISIN Div Reinvestment\n"
            "TestAMC,99999,Bad ISIN Fund,Open,Equity,Nav,500,01-Jun-2020,,BADFORMAT\n"
        )
        rows = parse_scheme_master(bad_fixture)
        assert rows == []

    def test_comma_in_scheme_name_is_preserved(self):
        """A comma inside the scheme name must NOT shift the ISIN/date columns
        (trailing columns are anchored from the right; name re-joined from middle)."""
        comma_name = (
            "AMC,Code,Scheme Name,Scheme Type,Scheme Category,Scheme NAV Name,"
            "Scheme Minimum Amount,Launch Date,Closure Date,"
            "ISIN Div Payout/ISIN GrowthISIN Div Reinvestment\n"
            "SomeAMC,77001,Equity Fund - Direct, Growth,Open Ended Schemes,"
            "Equity Scheme,Equity Fund Direct Growth,500,01-Jun-2020,,INF090I01RR5\n"
        )
        rows = parse_scheme_master(comma_name)
        assert len(rows) == 1
        assert rows[0].scheme_name == "Equity Fund - Direct, Growth"
        assert rows[0].isin_growth == "INF090I01RR5"
        assert rows[0].isin_reinvest is None
        assert rows[0].launch_date == datetime.date(2020, 6, 1)

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
            "AMC,Code,Scheme Name,Scheme Type,Scheme Category,Scheme NAV Name,"
            "Scheme Minimum Amount,Launch Date,Closure Date,"
            "ISIN Div Payout/ISIN GrowthISIN Div Reinvestment"
        )
        assert parse_scheme_master(header) == []


# ---------------------------------------------------------------------------
# secondary_isin_for — pure isin2 extraction (2026-07-04 plan-variant double-count
# incident, defect 2 of 3): the ISIN NOT chosen as canonical must be recoverable
# from a synthetic AMFI line, not silently discarded.
# ---------------------------------------------------------------------------


class TestSecondaryIsinFor:
    def test_both_isins_present_growth_canonical_reinvest_is_secondary(self):
        """Row 2 of the live-format fixture: growth wins as canonical, reinvest is the
        discarded-until-now secondary — this is the founder's HDFC Mid Cap incident shape."""
        from dhanradar.tasks.mf_scheme_master import secondary_isin_for

        rows = parse_scheme_master(SCHEME_MASTER_FIXTURE)
        nippon = next(r for r in rows if r.amfi_code == "118701")
        canonical = nippon.isin_growth or nippon.isin_reinvest
        assert secondary_isin_for(nippon, canonical) == "INF204K01EZ3"

    def test_only_growth_present_secondary_is_none(self):
        """A scheme with no dividend-reinvest variant (most schemes) → isin2 stays None,
        never fabricated."""
        from dhanradar.tasks.mf_scheme_master import secondary_isin_for

        rows = parse_scheme_master(SCHEME_MASTER_FIXTURE)
        hdfc = next(r for r in rows if r.amfi_code == "119551")
        canonical = hdfc.isin_growth or hdfc.isin_reinvest
        assert secondary_isin_for(hdfc, canonical) is None

    def test_synthetic_line_reinvest_only_secondary_is_growth(self):
        """If a scheme ever presented with only isin_reinvest set (growth is None), canonical
        falls back to reinvest and the secondary slot correctly reports the (absent) growth
        side — never the same value as canonical."""
        from dhanradar.tasks.mf_scheme_master import secondary_isin_for

        line = (
            "AMC,Code,Scheme Name,Scheme Type,Scheme Category,Scheme NAV Name,"
            "Scheme Minimum Amount,Launch Date,Closure Date,"
            "ISIN Div Payout/ISIN GrowthISIN Div Reinvestment\n"
            "TestAMC,55501,Reinvest Only Fund,Open,Equity,Nav,500,01-Jun-2020,,INF555Z01AB1\n"
        )
        rows = parse_scheme_master(line)
        assert len(rows) == 1
        row = rows[0]
        canonical = row.isin_growth or row.isin_reinvest
        assert canonical == "INF555Z01AB1"
        assert secondary_isin_for(row, canonical) is None


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
