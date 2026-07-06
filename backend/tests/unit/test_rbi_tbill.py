"""
Unit tests for RBI 91-day T-bill provider — no DB, no network.

Fixture HTML snippets are trimmed/anonymized copies of the REAL markup shape
live-verified against https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx
and its `?prid=<n>` detail pages on 2026-07-06 (raw HTML, not the browser-
rendered text view) — including RBI's own quirks: unquoted `href=` on the
listing page's title links, single-quoted `href='...'` elsewhere, and the
malformed `<b>DATE<b>` (no closing tag) on the listing page's date rows.
This module never uses the listing page's date row (it reads the reliable,
properly-closed `<b>Date : ...</b>` on the prid detail page instead).

Covers:
  fetch_tbill_yield:
    - happy path: listing HTML with T-Bill link -> detail page fetch ->
      date + header-order + YTM extraction -> MacroRow with
      indicator_key="tbill_91d_yield_pct"
    - listing page HTTP failure -> ProviderError
    - listing page network error -> ProviderError
    - no matching "T-Bill Auction Result: Cut-off" title found -> ProviderError
    - detail page HTTP failure -> ProviderError
    - detail page missing 'Date : ...' heading -> ProviderError
    - detail page tenor header order not 91/182/364-Day -> ProviderError (fail-closed)
    - detail page missing the cut-off/yield row -> ProviderError
    - detail page row has no 'YTM: X.XXXX%' values -> ProviderError (fail-closed)
    - yield value not a valid float -> ProviderError

asyncio_mode = "auto" (pyproject.toml) — async test functions need no decorator.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from dhanradar.market_data.exceptions import ProviderError
from dhanradar.market_data.rbi_tbill import fetch_tbill_yield

# ---------------------------------------------------------------------------
# Fixtures — inline HTML mirroring the REAL live markup shape
# ---------------------------------------------------------------------------

# Listing page: unquoted href on the title link (RBI's real markup), most
# recent entry first (reverse-chronological).
LISTING_HTML_VALID = """
<html><body>
<tr><td class="tableheader" colspan="4" align="left"><b>Jul 03, 2026<b></td></tr>
<tr><td><a class='link2' href=BS_PressReleaseDisplay.aspx?prid=63061>91-Day, 182-Day and 364-Day T-Bill Auction Result: Cut-off</a></td></tr>
<tr><td><a class='link2' href=BS_PressReleaseDisplay.aspx?prid=63060>Result of the 2-day Variable Rate Repo (VRR) auction held on July 01, 2026</a></td></tr>
</body></html>
"""

LISTING_HTML_NO_TBILL = """
<html><body>
<tr><td class="tableheader" colspan="4" align="left"><b>Jul 03, 2026<b></td></tr>
<tr><td><a class='link2' href=BS_PressReleaseDisplay.aspx?prid=63060>Auction of State Government Securities</a></td></tr>
</body></html>
"""

# Detail page: full real shape (date heading, tenor header row, cut-off row).
DETAIL_HTML_VALID = """
<html><body>
<tr><td align="right" class="tableheader"><b> Date : Jul 01, 2026</b></td></tr>
<tr><td align="center" class="tableheader"><b>91-Day, 182-Day and 364-Day T-Bill Auction Result: Cut-off</b></td></tr>
<tr><td width="5%"></td><td width="47%" align="center" class="head">T-Bill</td>
<td width="16%" align="center" class="head">91-Day</td>
<td width="16%" align="center" class="head">182-Day</td>
<td width="16%" align="center" class="head">364-Day</td></tr>
<tr><td align="center">II.</td><td valign="top">Cut-off Price (Rs.) and Implicit Yield at Cut-Off Price</td>
<td align="right" valign="top">98.7075 <br> (YTM: 5.2521%)</td>
<td align="right" valign="top">97.3448<br> (YTM: 5.4702%)</td>
<td align="right" valign="top">94.6542<br> (YTM: 5.6632%)</td></tr>
</body></html>
"""

# Detail page missing the 'Date : ...' heading entirely.
DETAIL_HTML_NO_DATE = DETAIL_HTML_VALID.replace(
    '<tr><td align="right" class="tableheader"><b> Date : Jul 01, 2026</b></td></tr>', ""
)

# Detail page with tenor columns reordered (364/182/91 instead of 91/182/364) —
# must be REJECTED rather than positionally misread.
DETAIL_HTML_BAD_HEADER_ORDER = DETAIL_HTML_VALID.replace(
    """<td width="16%" align="center" class="head">91-Day</td>
<td width="16%" align="center" class="head">182-Day</td>
<td width="16%" align="center" class="head">364-Day</td>""",
    """<td width="16%" align="center" class="head">364-Day</td>
<td width="16%" align="center" class="head">182-Day</td>
<td width="16%" align="center" class="head">91-Day</td>""",
)

# Detail page missing the cut-off/yield row entirely.
DETAIL_HTML_NO_ROW = DETAIL_HTML_VALID.replace(
    """<tr><td align="center">II.</td><td valign="top">Cut-off Price (Rs.) and Implicit Yield at Cut-Off Price</td>
<td align="right" valign="top">98.7075 <br> (YTM: 5.2521%)</td>
<td align="right" valign="top">97.3448<br> (YTM: 5.4702%)</td>
<td align="right" valign="top">94.6542<br> (YTM: 5.6632%)</td></tr>""",
    "",
)

# Detail page with the row present but no 'YTM: X%' values inside it.
DETAIL_HTML_NO_YTM = DETAIL_HTML_VALID.replace(
    """<td align="right" valign="top">98.7075 <br> (YTM: 5.2521%)</td>
<td align="right" valign="top">97.3448<br> (YTM: 5.4702%)</td>
<td align="right" valign="top">94.6542<br> (YTM: 5.6632%)</td>""",
    """<td align="right" valign="top">98.7075</td>
<td align="right" valign="top">97.3448</td>
<td align="right" valign="top">94.6542</td>""",
)

# Detail page with a non-numeric 91-Day YTM value. `_YTM_RE`'s lenient token
# still captures "N/A" as the first of 3 slots (so it is NOT silently skipped
# in favour of the 182-Day value shifting into position 0) — float() on it
# is what actually raises.
DETAIL_HTML_BAD_YIELD = DETAIL_HTML_VALID.replace("YTM: 5.2521%", "YTM: N/A%")


# ---------------------------------------------------------------------------
# Helper: mock httpx.AsyncClient
# ---------------------------------------------------------------------------


def _make_client(
    *,
    listing_status=200,
    listing_html=LISTING_HTML_VALID,
    detail_status=200,
    detail_html=DETAIL_HTML_VALID,
    raise_on_listing=None,
    raise_on_detail=None,
):
    """Build a fake httpx.AsyncClient that returns canned responses for the
    listing page (BS_PressReleaseDisplay.aspx, no query string) and the
    detail page (same path WITH a ?prid= query string)."""

    def _raise_status_error():
        # Real httpx.Response.raise_for_status() raises httpx.HTTPStatusError —
        # _get_html only catches (httpx.HTTPStatusError, httpx.RequestError), so
        # the mock must raise the SAME type or the except clause won't fire.
        import httpx as httpx_module

        req = httpx_module.Request("GET", "https://www.rbi.org.in/x")
        resp = httpx_module.Response(404, request=req)
        raise httpx_module.HTTPStatusError("HTTP error", request=req, response=resp)

    async def _get(url, headers=None, timeout=None, follow_redirects=None):
        resp = MagicMock()
        if "prid=" in url:
            if raise_on_detail:
                raise raise_on_detail
            resp.status_code = detail_status
            resp.raise_for_status = (
                _raise_status_error if detail_status != 200 else (lambda: None)
            )
            resp.text = detail_html
            return resp
        # Listing page.
        if raise_on_listing:
            raise raise_on_listing
        resp.status_code = listing_status
        resp.raise_for_status = (
            _raise_status_error if listing_status != 200 else (lambda: None)
        )
        resp.text = listing_html
        return resp

    client = MagicMock(spec=["get"])
    client.get = AsyncMock(side_effect=_get)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFetchTbillYield:
    async def test_happy_path(self):
        """Valid listing HTML -> detail page fetch -> date + header-order + YTM
        extraction -> MacroRow with the 91-Day (FIRST) yield value."""
        client = _make_client()

        row = await fetch_tbill_yield(client)
        assert row.indicator_key == "tbill_91d_yield_pct"
        assert row.indicator_value == 5.2521
        assert row.unit == "percent"
        assert row.as_of_date == date(2026, 7, 1)

    async def test_listing_page_unreachable(self):
        """Listing page returns HTTP error status -> ProviderError."""
        client = _make_client(listing_status=404)
        with pytest.raises(ProviderError, match="listing page unreachable"):
            await fetch_tbill_yield(client)

    async def test_listing_page_request_error(self):
        """Listing page raises httpx.RequestError -> ProviderError."""
        import httpx as httpx_module

        client = _make_client(raise_on_listing=httpx_module.RequestError("Network failure"))
        with pytest.raises(ProviderError, match="listing page unreachable"):
            await fetch_tbill_yield(client)

    async def test_no_tbill_title_found(self):
        """Listing HTML has no matching T-Bill press release -> ProviderError."""
        client = _make_client(listing_html=LISTING_HTML_NO_TBILL)
        with pytest.raises(ProviderError, match="no .* press release found"):
            await fetch_tbill_yield(client)

    async def test_detail_page_unreachable(self):
        """Detail page returns HTTP error status -> ProviderError."""
        client = _make_client(detail_status=404)
        with pytest.raises(ProviderError, match="detail .* page unreachable"):
            await fetch_tbill_yield(client)

    async def test_detail_page_missing_date_heading(self):
        """Detail page has no 'Date : ...' heading -> ProviderError."""
        client = _make_client(detail_html=DETAIL_HTML_NO_DATE)
        with pytest.raises(ProviderError, match="no parseable 'Date"):
            await fetch_tbill_yield(client)

    async def test_tenor_header_order_mismatch_fails_closed(self):
        """Tenor columns not in the confirmed 91/182/364-Day order -> ProviderError
        (fail-closed: never positionally misread a reordered table)."""
        client = _make_client(detail_html=DETAIL_HTML_BAD_HEADER_ORDER)
        with pytest.raises(ProviderError, match="header order not 91/182/364-Day"):
            await fetch_tbill_yield(client)

    async def test_cutoff_row_missing(self):
        """Detail page has no 'Cut-off Price...Yield at Cut-Off Price' row -> ProviderError."""
        client = _make_client(detail_html=DETAIL_HTML_NO_ROW)
        with pytest.raises(ProviderError, match="row not found"):
            await fetch_tbill_yield(client)

    async def test_no_ytm_values_fails_closed(self):
        """Cut-off row present but no 'YTM: X%' values inside it -> ProviderError
        (fail-closed: never guess a yield from the bare cut-off price)."""
        client = _make_client(detail_html=DETAIL_HTML_NO_YTM)
        with pytest.raises(ProviderError, match="expected 3 'YTM"):
            await fetch_tbill_yield(client)

    async def test_yield_value_not_a_float(self):
        """91-Day YTM slot has a non-numeric value -> ProviderError."""
        client = _make_client(detail_html=DETAIL_HTML_BAD_YIELD)
        with pytest.raises(ProviderError, match="not a valid float"):
            await fetch_tbill_yield(client)

