"""
DhanRadar — SEBI circulars listing fetcher and parser.

Fetches the SEBI MF circulars listing page and parses circular metadata rows.

SEBI may bot-block or change markup at any time.  A fetch failure raises
``ProviderError`` (propagates inside the ingestion_run ctx → records 'failed'
+ unreachable).  The parser is pure and fully unit-testable via a fixture.

Pure module: no DB, no Redis, no Celery, no auth/billing/scoring imports.

SEBI circular listing HTML structure (observed 2026-06):
The page renders a table with rows like::

    <tr>
      <td class="cellleft">SEBI/HO/IMD/IMD-I/DOF5/CIR/2026/52</td>
      <td class="cellRight">
        <a href="/cms/sebi_data/...pdf">Circular Title Text</a>
      </td>
      <td class="cellRight">Jun 19, 2026</td>
      <td class="cellRight">Mutual Funds</td>
    </tr>

Rows missing number, date, or title are silently skipped (never guessed).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser

import httpx

from dhanradar.market_data.exceptions import ProviderError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEBI_CIRCULARS_URL = (
    "https://www.sebi.gov.in/sebiweb/home/HomeAction.do"
    "?doListing=yes&sid=1&ssid=6&smid=0"
)

# SEBI blocks bare urllib/httpx UAs — use a browser UA (same pattern as amfi.py).
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Date formats observed on SEBI listing page.
_DATE_FMTS = ("%b %d, %Y", "%B %d, %Y", "%d-%b-%Y", "%d/%m/%Y")

# Circular number pattern: SEBI/HO/... or SEBI/DDHS/... etc.
_CIRCULAR_NUMBER_RE = re.compile(r"SEBI/[\w/.-]+", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CircularRow:
    """One parsed circular from the SEBI listing."""

    circular_number: str
    circular_date: date
    title: str
    url: str | None
    category: str | None


# ---------------------------------------------------------------------------
# HTML parser
# ---------------------------------------------------------------------------


def _parse_date(raw: str) -> date | None:
    """Try multiple SEBI date formats; return None on failure."""
    s = raw.strip().rstrip(".")
    # Normalise "Jun 19, 2026" → strip extra spaces
    s = re.sub(r"\s+", " ", s)
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


class _CircularTableParser(HTMLParser):
    """Minimal state-machine parser for SEBI circulars HTML.

    Scans for <tr> blocks and collects up to 4 <td> children per row.
    The first td is the circular reference number (text or anchor text).
    The second td contains an <a> whose text is the title and whose href
    is the URL (relative; absolutised by fetch_circulars).
    The third td is the date string.
    The fourth td (optional) is the coarse category.

    Rows that don't match (header rows, empty rows, malformed rows) are
    skipped — never guessed.
    """

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[CircularRow] = []

        # Per-row state
        self._in_tr: bool = False
        self._tds: list[str] = []          # accumulated text per td
        self._current_td: str = ""         # text being accumulated in this td
        self._depth_td: int = 0            # nested depth inside current td
        self._td_href: str | None = None   # href captured from first <a> in td
        self._in_td: bool = False

        # Per-row href (from the title td's <a>)
        self._row_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "tr":
            self._in_tr = True
            self._tds = []
            self._row_href = None
        elif tag == "td" and self._in_tr:
            self._in_td = True
            self._current_td = ""
            self._td_href = None
            self._depth_td = 1
        elif tag == "td" and not self._in_tr:
            pass
        elif self._in_td:
            if tag == "td":
                self._depth_td += 1
            elif tag == "a":
                attr_map = dict(attrs)
                href = attr_map.get("href")
                if href and self._td_href is None:
                    self._td_href = href

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "td" and self._in_td:
            self._depth_td -= 1
            if self._depth_td <= 0:
                text = re.sub(r"\s+", " ", self._current_td).strip()
                self._tds.append(text)
                # Second td carries the title href
                if len(self._tds) == 2 and self._td_href:
                    self._row_href = self._td_href
                self._in_td = False
                self._current_td = ""
        elif tag == "tr" and self._in_tr:
            self._in_tr = False
            self._try_emit_row()

    def handle_data(self, data: str) -> None:
        if self._in_td:
            self._current_td += data

    def _try_emit_row(self) -> None:
        tds = self._tds
        if len(tds) < 3:
            return  # not enough columns — header or spacer row

        raw_num = tds[0]
        raw_title = tds[1]
        raw_date = tds[2]
        raw_cat = tds[3] if len(tds) >= 4 else None

        # Validate circular_number — must match SEBI/... pattern
        num_match = _CIRCULAR_NUMBER_RE.search(raw_num)
        if not num_match:
            return  # header row or malformed

        circular_number = num_match.group(0).strip()
        if not circular_number:
            return

        # Validate title
        title = raw_title.strip()
        if not title:
            return

        # Validate and parse date
        parsed_date = _parse_date(raw_date)
        if parsed_date is None:
            logger.debug(
                "sebi.parse_circulars: skipping row (unparseable date %r)", raw_date
            )
            return

        # Category — store verbatim; None if blank
        category = raw_cat.strip() if raw_cat and raw_cat.strip() else None

        # URL — absolutise if relative
        href = self._row_href
        if href:
            if href.startswith("http"):
                url: str | None = href
            else:
                url = "https://www.sebi.gov.in" + (
                    href if href.startswith("/") else "/" + href
                )
        else:
            url = None

        self.rows.append(
            CircularRow(
                circular_number=circular_number,
                circular_date=parsed_date,
                title=title,
                url=url,
                category=category,
            )
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_circulars(html: str) -> list[CircularRow]:
    """Parse the SEBI circulars listing HTML.

    Pure function — no network, no DB.  Returns all rows whose
    circular_number, circular_date, and title are present and valid.
    Rows missing any of these fields are silently skipped.

    The HTML is expected to contain a table where each ``<tr>`` has:
      - td[0]: circular reference (e.g. ``SEBI/HO/IMD/.../2026/52``)
      - td[1]: ``<a href="...">title text</a>``
      - td[2]: date string (e.g. ``Jun 19, 2026``)
      - td[3]: category (e.g. ``Mutual Funds``) — optional

    Designed to be robust against minor markup changes: only the
    three mandatory fields gate a row; everything else degrades gracefully.
    """
    parser = _CircularTableParser()
    parser.feed(html)
    return parser.rows


async def fetch_circulars(client: httpx.AsyncClient) -> str:
    """Fetch the SEBI MF circulars listing HTML.

    Uses the supplied *client* (connection-pool sharing, test injection).

    Returns the raw HTML string on HTTP 200 with non-empty body.

    Raises ``ProviderError("sebi_circulars", ...)`` on:
      - Non-200 status code
      - Empty response body
      - Transport/timeout errors

    SEBI may bot-block or change the URL at any time.  A ``ProviderError``
    propagates inside the ``ingestion_run`` ctx manager, which records the
    run as 'failed' and marks the source unreachable — the correct behaviour
    for an inaccessible external source.
    """
    headers = {"User-Agent": _USER_AGENT}
    try:
        resp = await client.get(SEBI_CIRCULARS_URL, headers=headers, timeout=_TIMEOUT)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise ProviderError("sebi_circulars", exc) from exc

    if resp.status_code != 200:
        raise ProviderError(
            "sebi_circulars",
            f"HTTP {resp.status_code} from SEBI circulars listing",
        )

    text = resp.text
    if not text or not text.strip():
        raise ProviderError("sebi_circulars", "Empty response body from SEBI")

    return text
