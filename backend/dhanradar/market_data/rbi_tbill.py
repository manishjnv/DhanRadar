"""
DhanRadar — RBI 91-Day T-Bill auction result provider (Phase 6, Block 0.8).

Fetches the published 91-day Treasury Bill cut-off yield from RBI press
releases (https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx) — the
ONLY working, free, official source for India's sovereign risk-free rate
found for this block (RBI DBIE is dead — see market_data/rbi.py; FBIL's
public site is a JS SPA with no discoverable data API).

SOURCE SELECTION (from DhanRadar_Implementation_Plan.md §Block 0.8):
  RBI holds 91-day T-bill auctions WEEKLY (typically Wednesday). Results are
  published same day via a press release titled "91-Day, 182-Day and 364-Day
  T-Bill Auction Result: Cut-off". This module extracts ONLY the 91-Day
  yield — the de facto sovereign risk-free rate used in Sharpe/Sortino
  denominators.

TWO-STAGE HTML FETCH — NOT a PDF parse (live-verified 2026-07-06):
  1. The press-release LISTING page (`BS_PressReleaseDisplay.aspx`) is plain,
     un-JS-rendered HTML and lists each release's own detail-page link
     (`BS_PressReleaseDisplay.aspx?prid=<n>`).
  2. The detail page ALSO renders the full press release body inline as
     plain HTML — including a clean table with the 91/182/364-Day cut-off
     price and "(YTM: X.XXXX%)" yield for each tenor. No PDF is needed.
  IMPORTANT: the PDF attached to each release (served from the DIFFERENT
  subdomain `rbidocs.rbi.org.in`) IS bot-protected — live-verified 2026-07-06,
  a plain GET returns an interstitial CAPTCHA challenge page ("What code is
  in the image?"), not the PDF bytes. DhanRadar does not attempt to solve or
  bypass CAPTCHAs (Admin.md §12 Q3) — this module deliberately never touches
  rbidocs.rbi.org.in at all; both fetches stay on www.rbi.org.in, which is
  NOT behind this challenge.

FAIL-CLOSED RULES:
  1. Listing page: must find at least one `<a class='link2' href=...>` whose
     text matches "T-Bill Auction Result: Cut-off"; take the FIRST such
     match (the listing is reverse-chronological, so first = latest).
  2. Detail page: must find the "Date : <heading>" line AND a table row
     whose label cell matches "Cut-off Price...Yield at Cut-Off Price" AND
     a header row confirming column order is 91-Day, 182-Day, 364-Day
     (guards against RBI ever reordering the table — if the header order
     doesn't match this exact 91/182/364 sequence, refuse rather than
     silently reading the wrong column). The FIRST "YTM: X.XXXX%" match in
     that row is the 91-Day yield (by confirmed column position).
  3. Any missing piece (no title match, no detail-page date, no matching
     header order, no YTM figures) raises ProviderError — never a guessed
     number.
  4. Value validation: the extracted yield is validated against sane bounds
     (3.0–10.0%, mf/risk.py _TBILL_MIN_SANE_PCT/_TBILL_MAX_SANE_PCT) BEFORE
     upsert by the calling task — this module does no validation, only
     extraction.

COMPLIANCE:
  - No advisory verbs (enum or copy).
  - The T-bill yield is a numeric PUBLISHED FACT (not a DhanRadar score);
    non-neg #2 (no-numeric-in-DOM) does NOT restrict storing it. It only
    feeds resolve_risk_free_rate's internal Sharpe/Sortino denominator —
    never shown raw on a public surface.
  - No forecast or interpolation — only the published cut-off yield is stored.

Pure module: no DB, no Redis, no Celery, no auth/billing/scoring imports.
All network calls are injectable (accept httpx.AsyncClient parameter) so unit
tests can mock the transport.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

import httpx

from dhanradar.market_data.exceptions import ProviderError
from dhanradar.market_data.rbi import MacroRow  # Reuse the existing dataclass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# RBI press release listing + detail pages — BOTH on www.rbi.org.in (plain
# HTML, NOT JS-rendered, NOT behind the rbidocs.rbi.org.in CAPTCHA challenge;
# both live-verified reachable 2026-07-06 via a plain GET).
_RBI_PRESS_RELEASE_LIST_URL = "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx"
_RBI_PRESS_RELEASE_DETAIL_URL = (
    "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid={prid}"
)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Press release title substring (case-sensitive; matches the exact title RBI
# has used consistently: "91-Day, 182-Day and 364-Day T-Bill Auction Result:
# Cut-off"). We match the shorter stable suffix so a minor RBI wording tweak
# to the tenor-list prefix doesn't break this.
_TBILL_TITLE_PATTERN = "T-Bill Auction Result: Cut-off"

# Extract (prid, title) pairs from the listing page. VERIFIED against the
# live page (2026-07-06, raw HTML fetch — NOT the browser-rendered text
# view): RBI's markup uses an UNQUOTED href for these title links, e.g.
#   <a class='link2' href=BS_PressReleaseDisplay.aspx?prid=63061>91-Day, ...
#   T-Bill Auction Result: Cut-off</a>
# A double- or single-quoted href pattern here would NEVER match.
_LISTING_LINK_RE = re.compile(
    r"<a class='link2' href=BS_PressReleaseDisplay\.aspx\?prid=(\d+)>([^<]+)</a>",
    re.IGNORECASE,
)

# Date heading on the DETAIL page — VERIFIED (2026-07-06): rendered as
#   <td align="right" class="tableheader"><b> Date : Jul 01, 2026</b></td>
# (note: unlike the listing page's malformed `<b>...<b>` date row, the detail
# page's heading DOES close its <b> tag properly).
_DETAIL_DATE_RE = re.compile(
    r'class="tableheader"><b>\s*Date\s*:\s*([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\s*</b>',
    re.IGNORECASE,
)

# Header row confirming column order — VERIFIED (2026-07-06):
#   <td class="head">T-Bill</td><td class="head">91-Day</td>
#   <td class="head">182-Day</td><td class="head">364-Day</td>
# Requiring this exact order match before trusting positional YTM extraction
# means a future RBI table-layout change fails closed instead of silently
# reading the wrong tenor's yield into "91-Day".
_HEADER_ORDER_RE = re.compile(
    r'class="head">T-Bill</td>\s*<td[^>]*class="head">91-Day</td>\s*'
    r'<td[^>]*class="head">182-Day</td>\s*<td[^>]*class="head">364-Day</td>',
    re.IGNORECASE,
)

# The cut-off/yield row — VERIFIED (2026-07-06):
#   <td>Cut-off Price (₹) and Implicit Yield at Cut-Off Price</td>
#   <td align="right" valign="top">98.7075 <br> (YTM: 5.2521%)</td>  <- 91-Day
#   <td align="right" valign="top">97.3448<br> (YTM: 5.4702%)</td>  <- 182-Day
#   <td align="right" valign="top">94.6542<br> (YTM: 5.6632%)</td>  <- 364-Day
# Captures everything from the row label to the row's closing </tr> so the
# three YTM values can be extracted IN ORDER; the first is 91-Day (only
# trusted after _HEADER_ORDER_RE has confirmed that column ordering above).
_CUTOFF_ROW_RE = re.compile(
    r"Cut-off Price.{0,80}?Yield at Cut-Off Price</td>(.*?)</tr>",
    re.IGNORECASE | re.DOTALL,
)
# Deliberately lenient value token (`\S+`, not `[\d.]+`): this MUST still match
# and occupy a slot even when a tenor's value is malformed/non-numeric, so a
# corrupted 91-Day figure can never be silently skipped in favour of the
# 182-Day one shifting into position 0. Numeric validity is checked AFTER
# positional extraction (see fetch_tbill_yield), not by this regex.
_YTM_RE = re.compile(r"YTM:\s*(\S+?)\s*%", re.IGNORECASE)
_EXPECTED_TENOR_COUNT = 3  # 91-Day, 182-Day, 364-Day — one YTM each, in that order.


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fetch_tbill_yield(client: httpx.AsyncClient) -> MacroRow:
    """Fetch the latest 91-day T-bill yield from RBI press releases.

    Returns a MacroRow(indicator_key="tbill_91d_yield_pct", ...) suitable for
    direct upsert into mf.macro_indicators (same table as the existing RBI
    DBIE macro rows, different indicator_key).

    Raises:
        ProviderError: when the listing/detail page is unreachable, the
                       expected title/date/table shape is not found on
                       either page, or no parseable 91-day yield exists.
    """
    listing_html = await _get_html(client, _RBI_PRESS_RELEASE_LIST_URL, "listing")

    prid = _find_latest_tbill_prid(listing_html)
    if prid is None:
        raise ProviderError(
            "rbi_tbill",
            f"no '{_TBILL_TITLE_PATTERN}' press release found on the listing page",
        )

    detail_url = _RBI_PRESS_RELEASE_DETAIL_URL.format(prid=prid)
    detail_html = await _get_html(client, detail_url, f"detail (prid={prid})")

    auction_date = _extract_date(detail_html)
    if auction_date is None:
        raise ProviderError("rbi_tbill", f"no parseable 'Date : ...' heading on {detail_url}")

    if not _HEADER_ORDER_RE.search(detail_html):
        # Fail-closed: RBI's table column order must be 91/182/364-Day exactly
        # as observed, or positional YTM extraction below is not trustworthy.
        raise ProviderError(
            "rbi_tbill", f"tenor column header order not 91/182/364-Day on {detail_url}"
        )

    row_match = _CUTOFF_ROW_RE.search(detail_html)
    if row_match is None:
        raise ProviderError(
            "rbi_tbill",
            f"'Cut-off Price...Yield at Cut-Off Price' row not found on {detail_url}",
        )

    ytm_values = _YTM_RE.findall(row_match.group(1))
    if len(ytm_values) != _EXPECTED_TENOR_COUNT:
        # Fail-closed: exactly 3 tenor slots (91/182/364-Day) must be present
        # in order — a missing/malformed slot would otherwise silently shift
        # a LATER tenor's value into the "91-Day" position (e.g. a corrupted
        # 91-Day figure making the 182-Day figure look like it's first).
        raise ProviderError(
            "rbi_tbill",
            f"expected {_EXPECTED_TENOR_COUNT} 'YTM: ...%' slots (91/182/364-Day) in the "
            f"cut-off row, found {len(ytm_values)} on {detail_url}",
        )

    # First slot = 91-Day column (guaranteed by _HEADER_ORDER_RE above + the
    # exact-3-slots check just above).
    yield_str = ytm_values[0]
    try:
        yield_pct = float(yield_str)
    except ValueError as exc:
        raise ProviderError(
            "rbi_tbill", f"91-day yield value {yield_str!r} is not a valid float: {exc}"
        ) from exc

    logger.info(
        "rbi_tbill: extracted 91-day yield %.4f%% (auction date %s, prid=%s)",
        yield_pct,
        auction_date,
        prid,
    )

    return MacroRow(
        indicator_key="tbill_91d_yield_pct",
        indicator_value=yield_pct,
        unit="percent",
        as_of_date=auction_date,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_html(client: httpx.AsyncClient, url: str, label: str) -> str:
    """GET `url` and return response text, wrapping any failure as ProviderError."""
    try:
        resp = await client.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.text
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        raise ProviderError("rbi_tbill", f"{label} page unreachable ({url}): {exc}") from exc


def _find_latest_tbill_prid(listing_html: str) -> str | None:
    """Scan the listing page for the FIRST (= most recent, reverse-chronological
    listing) title containing `_TBILL_TITLE_PATTERN`, returning its `prid`."""
    for prid, title in _LISTING_LINK_RE.findall(listing_html):
        if _TBILL_TITLE_PATTERN in title:
            return prid
    return None


def _extract_date(detail_html: str) -> date | None:
    m = _DETAIL_DATE_RE.search(detail_html)
    if m is None:
        return None
    try:
        return datetime.strptime(m.group(1), "%b %d, %Y").date()
    except ValueError:
        return None
