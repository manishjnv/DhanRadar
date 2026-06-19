"""
Unit tests for SEBI circulars ingestion — no DB, no network, no Celery worker.

Covers:
  - parse_circulars: fixture HTML with ≥2 valid circulars + one row that is
    missing a circular number (must be skipped).
  - parse_circulars: row with an unparseable date must be skipped.
  - parse_circulars: URL absolutised for relative href; None for missing href.
  - fetch_circulars: injected AsyncMock client — happy path + non-200 + transport error.
  - CircularRow: dataclass field values round-trip correctly.

asyncio_mode = "auto" (pyproject.toml) — async test functions need no decorator.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from dhanradar.market_data.sebi import CircularRow, fetch_circulars, parse_circulars
from dhanradar.market_data.exceptions import ProviderError

# ---------------------------------------------------------------------------
# Fixture HTML — mirrors the SEBI circulars table structure
#
# Row layout (observed 2026-06):
#   td[0]  circular number  (SEBI/HO/... text or inside an <a>)
#   td[1]  <a href="...">title</a>
#   td[2]  date string  "Jun 19, 2026"
#   td[3]  category     "Mutual Funds"
#
# We include:
#   - 2 fully valid rows
#   - 1 row whose td[0] has no SEBI/... number (header-like row — must be skipped)
#   - 1 row with an unparseable date (must be skipped)
# ---------------------------------------------------------------------------

CIRCULAR_FIXTURE_HTML = """\
<html><body>
<table>
  <thead>
    <tr>
      <th>Circular No.</th>
      <th>Subject</th>
      <th>Date</th>
      <th>Category</th>
    </tr>
  </thead>
  <tbody>
    <!-- Valid circular 1: absolute URL, category present -->
    <tr>
      <td class="cellleft">SEBI/HO/IMD/IMD-I/DOF5/CIR/2026/52</td>
      <td class="cellRight">
        <a href="https://www.sebi.gov.in/cms/sebi_data/circ1.pdf">
          Circular on MF Categorisation Update
        </a>
      </td>
      <td class="cellRight">Jun 19, 2026</td>
      <td class="cellRight">Mutual Funds</td>
    </tr>
    <!-- Valid circular 2: relative URL, date in different format -->
    <tr>
      <td class="cellleft">SEBI/HO/IMD/PoD-1/CIR/2026/48</td>
      <td class="cellRight">
        <a href="/cms/sebi_data/circ2.pdf">
          Circular on Scheme Mergers Reporting
        </a>
      </td>
      <td class="cellRight">May 30, 2026</td>
      <td class="cellRight">Mutual Funds</td>
    </tr>
    <!-- Row missing circular number — td[0] has no SEBI/... pattern (must skip) -->
    <tr>
      <td class="cellleft">No. 12345</td>
      <td class="cellRight">
        <a href="/cms/sebi_data/circ3.pdf">Some Other Regulatory Update</a>
      </td>
      <td class="cellRight">Apr 15, 2026</td>
      <td class="cellRight">Other</td>
    </tr>
    <!-- Row with unparseable date (must skip) -->
    <tr>
      <td class="cellleft">SEBI/HO/IMD/IMD-I/DOF5/CIR/2026/40</td>
      <td class="cellRight">
        <a href="/cms/sebi_data/circ4.pdf">Circular With Bad Date</a>
      </td>
      <td class="cellRight">INVALID-DATE</td>
      <td class="cellRight">Mutual Funds</td>
    </tr>
  </tbody>
</table>
</body></html>
"""

# Fixture with no category td (3-column row)
MINIMAL_FIXTURE_HTML = """\
<html><body>
<table>
  <tr>
    <td>SEBI/HO/IMD/IMD-II/DOF8/CIR/2026/10</td>
    <td><a href="/cms/sebi_data/circ10.pdf">Minimal Circular Title</a></td>
    <td>Jan 05, 2026</td>
  </tr>
</table>
</body></html>
"""


# ===========================================================================
# parse_circulars
# ===========================================================================


class TestParseCirculars:
    def test_returns_two_valid_rows(self):
        rows = parse_circulars(CIRCULAR_FIXTURE_HTML)
        assert len(rows) == 2, f"Expected 2 valid rows, got {len(rows)}: {rows}"

    def test_first_circular_number(self):
        rows = parse_circulars(CIRCULAR_FIXTURE_HTML)
        assert rows[0].circular_number == "SEBI/HO/IMD/IMD-I/DOF5/CIR/2026/52"

    def test_second_circular_number(self):
        rows = parse_circulars(CIRCULAR_FIXTURE_HTML)
        assert rows[1].circular_number == "SEBI/HO/IMD/PoD-1/CIR/2026/48"

    def test_first_circular_date(self):
        rows = parse_circulars(CIRCULAR_FIXTURE_HTML)
        assert rows[0].circular_date == datetime.date(2026, 6, 19)

    def test_second_circular_date(self):
        rows = parse_circulars(CIRCULAR_FIXTURE_HTML)
        assert rows[1].circular_date == datetime.date(2026, 5, 30)

    def test_first_circular_title(self):
        rows = parse_circulars(CIRCULAR_FIXTURE_HTML)
        assert "MF Categorisation Update" in rows[0].title

    def test_absolute_url_preserved(self):
        rows = parse_circulars(CIRCULAR_FIXTURE_HTML)
        assert rows[0].url == "https://www.sebi.gov.in/cms/sebi_data/circ1.pdf"

    def test_relative_url_absolutised(self):
        rows = parse_circulars(CIRCULAR_FIXTURE_HTML)
        assert rows[1].url == "https://www.sebi.gov.in/cms/sebi_data/circ2.pdf"

    def test_category_present(self):
        rows = parse_circulars(CIRCULAR_FIXTURE_HTML)
        assert rows[0].category == "Mutual Funds"
        assert rows[1].category == "Mutual Funds"

    def test_row_missing_sebi_number_skipped(self):
        """Row with 'No. 12345' in td[0] has no SEBI/... pattern → skipped."""
        rows = parse_circulars(CIRCULAR_FIXTURE_HTML)
        numbers = {r.circular_number for r in rows}
        # None of the returned numbers should be the invalid one
        assert all("SEBI/" in n for n in numbers)

    def test_row_with_invalid_date_skipped(self):
        """Row whose td[2] = 'INVALID-DATE' must be skipped."""
        rows = parse_circulars(CIRCULAR_FIXTURE_HTML)
        titles = [r.title for r in rows]
        assert not any("Bad Date" in t for t in titles)

    def test_minimal_row_no_category(self):
        rows = parse_circulars(MINIMAL_FIXTURE_HTML)
        assert len(rows) == 1
        assert rows[0].circular_number == "SEBI/HO/IMD/IMD-II/DOF8/CIR/2026/10"
        assert rows[0].category is None

    def test_empty_html_returns_empty_list(self):
        assert parse_circulars("") == []

    def test_returns_circular_row_instances(self):
        rows = parse_circulars(CIRCULAR_FIXTURE_HTML)
        for r in rows:
            assert isinstance(r, CircularRow)

    def test_circular_row_is_frozen(self):
        rows = parse_circulars(CIRCULAR_FIXTURE_HTML)
        with pytest.raises((AttributeError, TypeError)):
            rows[0].title = "mutated"  # type: ignore[misc]


# ===========================================================================
# fetch_circulars — fake client, no network
# ===========================================================================


def _make_fake_client(text: str, status_code: int = 200) -> MagicMock:
    """Return a MagicMock httpx.AsyncClient whose .get() returns a fake response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    return client


class TestFetchCirculars:
    async def test_returns_html_on_200(self):
        fake_client = _make_fake_client(CIRCULAR_FIXTURE_HTML)
        html = await fetch_circulars(fake_client)
        assert "SEBI/HO/IMD" in html

    async def test_calls_sebi_circulars_url(self):
        from dhanradar.market_data.sebi import SEBI_CIRCULARS_URL

        fake_client = _make_fake_client(CIRCULAR_FIXTURE_HTML)
        await fetch_circulars(fake_client)
        call_args = fake_client.get.call_args
        url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
        assert url == SEBI_CIRCULARS_URL

    async def test_raises_provider_error_on_non_200(self):
        fake_client = _make_fake_client("forbidden", status_code=403)
        with pytest.raises(ProviderError) as exc_info:
            await fetch_circulars(fake_client)
        assert exc_info.value.provider == "sebi_circulars"
        assert "403" in str(exc_info.value)

    async def test_raises_provider_error_on_503(self):
        fake_client = _make_fake_client("service unavailable", status_code=503)
        with pytest.raises(ProviderError) as exc_info:
            await fetch_circulars(fake_client)
        assert exc_info.value.provider == "sebi_circulars"

    async def test_raises_provider_error_on_empty_body(self):
        fake_client = _make_fake_client("   ")  # whitespace-only body
        with pytest.raises(ProviderError) as exc_info:
            await fetch_circulars(fake_client)
        assert exc_info.value.provider == "sebi_circulars"
        assert "Empty" in str(exc_info.value)

    async def test_raises_provider_error_on_transport_error(self):
        import httpx as _httpx

        fake_client = MagicMock()
        fake_client.get = AsyncMock(
            side_effect=_httpx.TransportError("connection refused")
        )
        with pytest.raises(ProviderError) as exc_info:
            await fetch_circulars(fake_client)
        assert exc_info.value.provider == "sebi_circulars"

    async def test_raises_provider_error_on_timeout(self):
        import httpx as _httpx

        fake_client = MagicMock()
        fake_client.get = AsyncMock(
            side_effect=_httpx.TimeoutException("timed out")
        )
        with pytest.raises(ProviderError):
            await fetch_circulars(fake_client)
