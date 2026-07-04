"""
Unit tests for dhanradar.market_data.amfi.

All tests are offline — no network calls.  Async fetcher tests use an
injected fake httpx.AsyncClient so the fetchers never hit the wire.

asyncio_mode = "auto" (pyproject.toml) — async test functions need no
decorator.
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from dhanradar.market_data.amfi import (
    fetch_nav_history,
    fetch_navall,
    parse_nav_history,
    parse_navall,
    parse_navall_with_category,
    stream_nav_history,
)
from dhanradar.market_data.exceptions import ProviderError

# ---------------------------------------------------------------------------
# Golden fixtures — NAVAll.txt (6-field)
# ---------------------------------------------------------------------------

NAVALL_FIXTURE = """\
Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

Open Ended Schemes(Debt Scheme - Banking and PSU Fund)

Taurus Mutual Fund

139619;INF090I01239;INF090I01247;Taurus Short Term Income Fund - Regular Plan - Growth;42.5678;02-Jun-2026
140020;INF090I01239;-;Taurus Ultra Short Term Bond Fund - Regular Plan - Growth;15.1234;02-Jun-2026
140021;INF090I01255;INF090I01263;Taurus Banking & PSU Debt Fund - Growth;28.9000;02-Jun-2026
140099;INF090I01271;INF090I01289;Taurus Bad NAV Fund;N.A.;02-Jun-2026
"""

# ---------------------------------------------------------------------------
# Golden fixtures — DownloadNAVHistoryReport_Po.aspx (8-field)
# ---------------------------------------------------------------------------

NAV_HISTORY_FIXTURE = """\
Scheme Code;Scheme Name;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Repurchase Price;Sale Price;Date

Open Ended Schemes(Equity Scheme - Large Cap Fund)

HDFC Mutual Fund

100016;HDFC Top 100 Fund - Growth Option;INF179K01BB4;-;1052.3456;1052.3456;1052.3456;01-Jun-2026
100017;HDFC Large Cap Fund - Growth;INF179K01CC5;INF179K01DD6;987.6543;987.6543;987.6543;01-Jun-2026
100018;HDFC Bad NAV History Fund;INF179K01EE7;INF179K01FF8;N.A.;0.0;0.0;01-Jun-2026
"""


# ===========================================================================
# parse_navall tests
# ===========================================================================

class TestParseNavall:
    def test_returns_only_valid_data_rows(self):
        rows = parse_navall(NAVALL_FIXTURE)
        # 4 data-looking lines: 3 valid + 1 N.A. NAV → 3 rows
        assert len(rows) == 3

    def test_first_row_fields(self):
        rows = parse_navall(NAVALL_FIXTURE)
        row = rows[0]
        assert row.amfi_code == "139619"
        assert row.isin_growth == "INF090I01239"
        assert row.isin_reinvest == "INF090I01247"
        assert row.scheme_name == "Taurus Short Term Income Fund - Regular Plan - Growth"
        assert row.nav == pytest.approx(42.5678)
        assert row.nav_date == datetime.date(2026, 6, 2)

    def test_dash_isin_reinvest_becomes_none(self):
        rows = parse_navall(NAVALL_FIXTURE)
        # second row has "-" for reinvest
        row = rows[1]
        assert row.amfi_code == "140020"
        assert row.isin_reinvest is None
        assert row.isin_growth == "INF090I01239"

    def test_both_isins_present(self):
        rows = parse_navall(NAVALL_FIXTURE)
        row = rows[2]
        assert row.isin_growth == "INF090I01255"
        assert row.isin_reinvest == "INF090I01263"

    def test_na_nav_row_is_skipped(self):
        rows = parse_navall(NAVALL_FIXTURE)
        codes = [r.amfi_code for r in rows]
        assert "140099" not in codes

    def test_blank_lines_skipped(self):
        rows = parse_navall(NAVALL_FIXTURE)
        # No NavRow should have blank amfi_code
        assert all(r.amfi_code != "" for r in rows)

    def test_category_header_line_skipped(self):
        # Category header like "Open Ended Schemes(...)" doesn't split into 6 parts
        rows = parse_navall(NAVALL_FIXTURE)
        assert all("Open Ended" not in r.scheme_name for r in rows)

    def test_amc_name_line_skipped(self):
        rows = parse_navall(NAVALL_FIXTURE)
        assert all("Taurus Mutual Fund" != r.scheme_name for r in rows)

    def test_header_row_skipped_even_if_six_fields(self):
        # Inject a header line that would split into 6 fields
        header = "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date\n"
        rows = parse_navall(header)
        assert rows == []

    def test_bad_date_row_skipped(self):
        bad = "999001;INF001;INF002;Bad Date Fund;10.0;32-ZZZ-2026\n"
        rows = parse_navall(bad)
        assert rows == []

    def test_bad_nav_row_skipped(self):
        bad = "999002;INF001;INF002;Bad NAV Fund;abc;02-Jun-2026\n"
        rows = parse_navall(bad)
        assert rows == []

    def test_empty_isin_becomes_none(self):
        # Empty second field (two consecutive semicolons)
        line = "999003;;INF002;Empty ISIN Fund;55.0;02-Jun-2026\n"
        rows = parse_navall(line)
        assert len(rows) == 1
        assert rows[0].isin_growth is None
        assert rows[0].isin_reinvest == "INF002"

    def test_nav_row_is_frozen_dataclass(self):
        rows = parse_navall(NAVALL_FIXTURE)
        with pytest.raises((AttributeError, TypeError)):
            rows[0].nav = 999.0  # type: ignore[misc]


# ===========================================================================
# parse_nav_history tests
# ===========================================================================

class TestParseNavHistory:
    def test_returns_only_valid_data_rows(self):
        rows = parse_nav_history(NAV_HISTORY_FIXTURE)
        # 3 data-looking lines: 2 valid + 1 N.A. NAV → 2 rows
        assert len(rows) == 2

    def test_field_mapping_name_at_index_1(self):
        """Scheme Name is [1] in history, NOT [3] as in navall."""
        rows = parse_nav_history(NAV_HISTORY_FIXTURE)
        assert rows[0].scheme_name == "HDFC Top 100 Fund - Growth Option"

    def test_field_mapping_isin_growth_at_index_2(self):
        """ISIN Growth is [2] in history, NOT [1] as in navall."""
        rows = parse_nav_history(NAV_HISTORY_FIXTURE)
        assert rows[0].isin_growth == "INF179K01BB4"

    def test_field_mapping_isin_reinvest_at_index_3(self):
        rows = parse_nav_history(NAV_HISTORY_FIXTURE)
        assert rows[0].isin_reinvest is None   # "-"
        assert rows[1].isin_reinvest == "INF179K01DD6"

    def test_repurchase_and_sale_ignored(self):
        """Rows[1] has different Repurchase/Sale — they must not affect NavRow."""
        rows = parse_nav_history(NAV_HISTORY_FIXTURE)
        row = rows[1]
        assert row.nav == pytest.approx(987.6543)
        # No attribute for repurchase/sale
        assert not hasattr(row, "repurchase_price")
        assert not hasattr(row, "sale_price")

    def test_nav_and_date_parsed_correctly(self):
        rows = parse_nav_history(NAV_HISTORY_FIXTURE)
        assert rows[0].nav == pytest.approx(1052.3456)
        assert rows[0].nav_date == datetime.date(2026, 6, 1)

    def test_na_nav_row_skipped(self):
        rows = parse_nav_history(NAV_HISTORY_FIXTURE)
        codes = [r.amfi_code for r in rows]
        assert "100018" not in codes

    def test_header_row_skipped(self):
        header = "Scheme Code;Scheme Name;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Repurchase Price;Sale Price;Date\n"
        rows = parse_nav_history(header)
        assert rows == []

    def test_bad_date_row_skipped(self):
        bad = "999010;Bad Date Fund;INF001;INF002;10.0;10.0;10.0;99-XYZ-2026\n"
        rows = parse_nav_history(bad)
        assert rows == []


# ===========================================================================
# Async fetcher tests — injected fake client (no network)
# ===========================================================================

def _make_fake_response(text: str, status_code: int = 200) -> MagicMock:
    """Return a MagicMock that looks like an httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


def _make_fake_client(text: str, status_code: int = 200) -> MagicMock:
    """
    Return a MagicMock async client whose .get(...) is an AsyncMock
    returning the fake response.
    """
    client = MagicMock()
    client.get = AsyncMock(return_value=_make_fake_response(text, status_code))
    return client


class TestFetchNavall:
    async def test_parses_injected_response(self):
        fake_client = _make_fake_client(NAVALL_FIXTURE)
        rows = await fetch_navall(client=fake_client)
        assert len(rows) == 3
        assert rows[0].amfi_code == "139619"

    async def test_raises_provider_error_on_non_200(self):
        fake_client = _make_fake_client("error body", status_code=503)
        with pytest.raises(ProviderError) as exc_info:
            await fetch_navall(client=fake_client)
        assert exc_info.value.provider == "amfi_nav"
        assert "503" in str(exc_info.value)

    async def test_get_called_with_navall_url(self):
        from dhanradar.market_data.amfi import NAVALL_URL

        fake_client = _make_fake_client(NAVALL_FIXTURE)
        await fetch_navall(client=fake_client)
        call_args = fake_client.get.call_args
        assert call_args[0][0] == NAVALL_URL or call_args.args[0] == NAVALL_URL

    async def test_raises_provider_error_on_transport_error(self):
        import httpx

        fake_client = MagicMock()
        fake_client.get = AsyncMock(side_effect=httpx.TransportError("connection refused"))
        with pytest.raises(ProviderError) as exc_info:
            await fetch_navall(client=fake_client)
        assert exc_info.value.provider == "amfi_nav"


class TestFetchNavHistory:
    async def test_parses_injected_response(self):
        fake_client = _make_fake_client(NAV_HISTORY_FIXTURE)
        frmdt = datetime.date(2026, 4, 1)
        todt = datetime.date(2026, 6, 30)
        rows = await fetch_nav_history(frmdt, todt, client=fake_client)
        assert len(rows) == 2
        assert rows[0].amfi_code == "100016"

    async def test_date_params_formatted_as_dd_mmm_yyyy(self):
        """
        The critical contract: frmdt and todt must be passed as query params
        in "DD-Mmm-YYYY" format (e.g. "01-Apr-2026"), not ISO "2026-04-01".
        """
        fake_client = _make_fake_client(NAV_HISTORY_FIXTURE)
        frmdt = datetime.date(2026, 4, 1)
        todt = datetime.date(2026, 6, 30)
        await fetch_nav_history(frmdt, todt, client=fake_client)

        call_kwargs: dict[str, Any] = fake_client.get.call_args.kwargs
        params = call_kwargs.get("params", {})
        assert params["frmdt"] == "01-Apr-2026"
        assert params["todt"] == "30-Jun-2026"

    async def test_raises_provider_error_on_non_200(self):
        fake_client = _make_fake_client("bad", status_code=403)
        with pytest.raises(ProviderError) as exc_info:
            await fetch_nav_history(
                datetime.date(2026, 1, 1), datetime.date(2026, 3, 31), client=fake_client
            )
        assert exc_info.value.provider == "amfi_history"
        assert "403" in str(exc_info.value)

    async def test_raises_provider_error_on_transport_error(self):
        import httpx

        fake_client = MagicMock()
        fake_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        with pytest.raises(ProviderError) as exc_info:
            await fetch_nav_history(
                datetime.date(2026, 1, 1), datetime.date(2026, 3, 31), client=fake_client
            )
        assert exc_info.value.provider == "amfi_history"

    async def test_get_called_with_history_url(self):
        from dhanradar.market_data.amfi import NAV_HISTORY_URL

        fake_client = _make_fake_client(NAV_HISTORY_FIXTURE)
        await fetch_nav_history(
            datetime.date(2026, 4, 1), datetime.date(2026, 6, 30), client=fake_client
        )
        call_args = fake_client.get.call_args
        url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
        assert url == NAV_HISTORY_URL


# ===========================================================================
# stream_nav_history — memory-flat variant (B-OOM nav_backfill fix)
#
# Fakes `httpx.AsyncClient.stream()` — a context manager yielding a response
# with `.status_code` + async `.aiter_lines()` — never `.get()`. No network.
# ===========================================================================

class _FakeStreamResponse:
    """Mimics the object yielded by `async with client.stream(...) as resp`."""

    def __init__(self, text: str, status_code: int = 200):
        self.status_code = status_code
        self._lines = text.splitlines()

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamCtx:
    def __init__(self, resp: _FakeStreamResponse):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *exc):
        return False


class _FakeStreamErrorCtx:
    """Raises on __aenter__ — mimics a connect-time transport failure."""

    def __init__(self, exc: Exception):
        self._exc = exc

    async def __aenter__(self):
        raise self._exc

    async def __aexit__(self, *exc):
        return False


class _FakeStreamClient:
    def __init__(self, text: str, status_code: int = 200):
        self._resp = _FakeStreamResponse(text, status_code)
        self.stream_calls: list[tuple] = []

    def stream(self, method, url, **kwargs):
        self.stream_calls.append((method, url, kwargs))
        return _FakeStreamCtx(self._resp)


class _FakeStreamErrorClient:
    def __init__(self, exc: Exception):
        self._exc = exc

    def stream(self, method, url, **kwargs):
        return _FakeStreamErrorCtx(self._exc)


async def _collect(gen):
    return [row async for row in gen]


class TestStreamNavHistory:
    async def test_yields_only_valid_rows(self):
        """Same skip rules as parse_nav_history: header/blank/N.A. lines skipped."""
        fake_client = _FakeStreamClient(NAV_HISTORY_FIXTURE)
        rows = await _collect(
            stream_nav_history(
                datetime.date(2026, 4, 1), datetime.date(2026, 6, 30), client=fake_client
            )
        )
        assert len(rows) == 2
        assert rows[0].amfi_code == "100016"
        assert rows[1].amfi_code == "100017"

    async def test_matches_parse_nav_history_for_same_fixture(self):
        """Regression guard: the shared per-line parser must produce IDENTICAL
        output whether consumed whole-text (parse_nav_history) or streamed
        line-by-line (stream_nav_history) — same rule, two entry points."""
        whole = parse_nav_history(NAV_HISTORY_FIXTURE)
        fake_client = _FakeStreamClient(NAV_HISTORY_FIXTURE)
        streamed = await _collect(
            stream_nav_history(
                datetime.date(2026, 4, 1), datetime.date(2026, 6, 30), client=fake_client
            )
        )
        assert streamed == whole

    async def test_date_params_formatted_as_dd_mmm_yyyy(self):
        from dhanradar.market_data.amfi import NAV_HISTORY_URL

        fake_client = _FakeStreamClient(NAV_HISTORY_FIXTURE)
        await _collect(
            stream_nav_history(
                datetime.date(2026, 4, 1), datetime.date(2026, 6, 30), client=fake_client
            )
        )
        _method, url, kwargs = fake_client.stream_calls[0]
        assert url == NAV_HISTORY_URL
        assert kwargs["params"]["frmdt"] == "01-Apr-2026"
        assert kwargs["params"]["todt"] == "30-Jun-2026"

    async def test_raises_provider_error_on_non_200(self):
        fake_client = _FakeStreamClient("bad body", status_code=503)
        with pytest.raises(ProviderError) as exc_info:
            await _collect(
                stream_nav_history(
                    datetime.date(2026, 1, 1), datetime.date(2026, 3, 31), client=fake_client
                )
            )
        assert exc_info.value.provider == "amfi_history"
        assert "503" in str(exc_info.value)

    async def test_raises_provider_error_on_transport_error(self):
        import httpx

        fake_client = _FakeStreamErrorClient(httpx.TimeoutException("timed out"))
        with pytest.raises(ProviderError) as exc_info:
            await _collect(
                stream_nav_history(
                    datetime.date(2026, 1, 1), datetime.date(2026, 3, 31), client=fake_client
                )
            )
        assert exc_info.value.provider == "amfi_history"


# ===========================================================================
# parse_navall_with_category — section-header carry-forward (B66-f1)
# ===========================================================================

# Reproduces the live-feed structure that caused the carry-forward bug: an
# AMC-name line that contains parentheses — "IL&FS Mutual Fund (IDF)" — sitting
# inside a "Close Ended Schemes(Income)" section. The old parser treated the
# AMC line as a header and mis-tagged every following fund "IDF".
NAVALL_CATEGORY_FIXTURE = """\
Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - Large Cap Fund)

HDFC Mutual Fund

100016;INF179K01BB4;-;HDFC Top 100 Fund - Growth;1052.3456;02-Jun-2026

Close Ended Schemes(Income)

IL&FS Mutual Fund (IDF)

500001;INF999X01AA1;-;IL&FS Infrastructure Debt Fund - Series 1 - Growth;11.2345;02-Jun-2026

Nippon India Mutual Fund

500002;INF204K01XX1;-;Nippon India Fixed Horizon Fund XXXIII - Series 2 - Growth;13.4567;02-Jun-2026
"""


class TestParseNavallWithCategory:
    def test_section_header_sets_category(self):
        rows = parse_navall_with_category(NAVALL_CATEGORY_FIXTURE)
        by_isin = {r.isin_growth: r for r in rows}
        assert by_isin["INF179K01BB4"].category == "Equity Scheme - Large Cap Fund"

    def test_amc_name_line_with_parens_does_not_become_category(self):
        # The crux of B66-f1: "IL&FS Mutual Fund (IDF)" must NOT set category="IDF".
        rows = parse_navall_with_category(NAVALL_CATEGORY_FIXTURE)
        assert all(r.category != "IDF" for r in rows), [r.category for r in rows]

    def test_funds_after_amc_paren_line_keep_section_category(self):
        # Both the IL&FS scheme AND the next AMC's funds inherit the real section
        # category ("Income"), not the poisoned "IDF".
        rows = parse_navall_with_category(NAVALL_CATEGORY_FIXTURE)
        by_isin = {r.isin_growth: r for r in rows}
        assert by_isin["INF999X01AA1"].category == "Income"
        assert by_isin["INF204K01XX1"].category == "Income"

    def test_interval_and_close_ended_headers_recognized(self):
        feed = (
            "Interval Fund Schemes(Income)\n\n"
            "Some AMC\n\n"
            "600001;INF600X01AA1;-;Some Interval Income Plan - Growth;10.1;02-Jun-2026\n"
        )
        rows = parse_navall_with_category(feed)
        assert rows[0].category == "Income"

    def test_schemes_prefix_required_even_without_amc_paren(self):
        # A stray non-header line with parens whose prefix is not "...Schemes"
        # never sets the category.
        feed = (
            "Random Note (see circular)\n\n"
            "700001;INF700X01AA1;-;Pre-header Fund - Growth;9.9;02-Jun-2026\n"
        )
        rows = parse_navall_with_category(feed)
        assert rows[0].category is None

    def test_space_before_paren_header_still_recognized(self):
        # Defensive (adversarial finding 4): a header with a space before "("
        # — "Open Ended Schemes (Income)" — must still be recognized; the prefix
        # `.strip()` handles the trailing space before the "Schemes" anchor.
        feed = (
            "Open Ended Schemes (Equity Scheme - Value Fund)\n\n"
            "Some AMC\n\n"
            "800001;INF800X01AA1;-;Some Value Fund - Growth;10.0;02-Jun-2026\n"
        )
        rows = parse_navall_with_category(feed)
        assert rows[0].category == "Equity Scheme - Value Fund"
