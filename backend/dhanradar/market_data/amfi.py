"""
DhanRadar — AMFI public NAV feed parser and async fetchers.

Two public AMFI endpoints are supported:

* NAVAll.txt  — daily snapshot of all schemes (6-field, ";" delimited).
* DownloadNAVHistoryReport_Po.aspx — historical NAV per scheme/date range
  (8-field, ";" delimited, different column order).

AMFI caps the history endpoint to ~3 months per request.  Multi-window
backfills are the CALLER's responsibility — ``fetch_nav_history`` takes a
single ``(frmdt, todt)`` window and returns whatever AMFI returns for it.

Pure module: no DB, no Redis, no Celery, no auth/billing/scoring imports.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from dhanradar.market_data.exceptions import ProviderError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NAVALL_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
NAV_HISTORY_URL = (
    "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
)

# AMFI/Cloudflare 403s bare urllib UAs (mirrors the Cloudflare-guard pattern
# used in notifications/channels.py for the Resend outbound call).
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

_DATE_FMT = "%d-%b-%Y"


@dataclass(frozen=True)
class NavRow:
    """One parsed row from either AMFI NAV feed."""

    amfi_code: str
    isin_growth: str | None       # ISIN Div Payout / ISIN Growth; None if "-" or empty
    isin_reinvest: str | None     # ISIN Div Reinvestment; None if "-" or empty
    scheme_name: str
    nav: float
    nav_date: datetime.date
    category: str | None = None   # scheme-type category from NAVAll.txt section header


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _isin_or_none(raw: str) -> str | None:
    """Return stripped ISIN, or None if the field is "-" or blank."""
    s = raw.strip()
    return None if s in ("-", "") else s


def _parse_nav(raw: str) -> float | None:
    """Return float NAV or None if the field is unparseable / N.A. / blank."""
    s = raw.strip()
    if s in ("N.A.", "-", ""):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(raw: str) -> datetime.date | None:
    """Parse "DD-Mmm-YYYY" date or return None on any parse failure."""
    try:
        return datetime.datetime.strptime(raw.strip(), _DATE_FMT).date()
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

_NAVALL_FIELDS = 6
_HISTORY_FIELDS = 8
_SCHEME_CODE_HEADER = "scheme code"


def parse_navall(text: str) -> list[NavRow]:
    """
    Parse the DAILY AMFI feed (NAVAll.txt).

    Expected format — 6 fields, ";" delimiter::

        Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;
        Scheme Name;Net Asset Value;Date

    Lines that do not split into exactly 6 fields are silently skipped
    (header line, blank lines, AMC-name lines, category-header lines).
    Rows with unparseable NAV or date are also skipped.
    """
    rows: list[NavRow] = []
    for line in text.splitlines():
        parts = line.split(";")
        if len(parts) != _NAVALL_FIELDS:
            continue
        # Skip the header row even if it accidentally splits into 6 fields.
        if parts[0].strip().lower() == _SCHEME_CODE_HEADER:
            continue
        nav = _parse_nav(parts[4])
        if nav is None:
            continue
        nav_date = _parse_date(parts[5])
        if nav_date is None:
            continue
        rows.append(
            NavRow(
                amfi_code=parts[0].strip(),
                isin_growth=_isin_or_none(parts[1]),
                isin_reinvest=_isin_or_none(parts[2]),
                scheme_name=parts[3].strip(),
                nav=nav,
                nav_date=nav_date,
            )
        )
    return rows


def parse_navall_with_category(text: str) -> list[NavRow]:
    """
    Parse the DAILY AMFI feed (NAVAll.txt) with scheme-type category tracking.

    Same skip rules as ``parse_navall``.  Additionally, the structured
    scheme-type SECTION headers — non-data lines whose text before "(" ends with
    "Schemes" (e.g. "Open Ended Schemes(Equity Scheme - Large Cap Fund)",
    "Close Ended Schemes(Income)", "Interval Fund Schemes(Income)") — set the
    ``category`` carried on every subsequent ``NavRow`` until the next such
    header.

    An AMC-name line is NOT a category header, even when it contains parentheses
    (e.g. "IL&FS Mutual Fund (IDF)"): only the "…Schemes(…)" prefix anchors a
    real header, so such lines no longer poison the carry-forward (B66-f1).
    Bare AMC-name lines (e.g. "Taurus Mutual Fund") and blank lines also do not
    change the category.  Schemes before any category header receive
    ``category=None``.
    """
    rows: list[NavRow] = []
    current_category: str | None = None
    for line in text.splitlines():
        parts = line.split(";")
        if len(parts) != _NAVALL_FIELDS:
            # Non-data line — check whether it is a scheme-type SECTION header.
            # ONLY the structured section headers carry the category: their text
            # before "(" ends with "Schemes" — e.g.
            #   "Open Ended Schemes(Equity Scheme - Large Cap Fund)"
            #   "Close Ended Schemes(Income)"
            #   "Interval Fund Schemes(Income)"
            # An AMC-NAME line that merely happens to contain parentheses — e.g.
            # "IL&FS Mutual Fund (IDF)" — must NOT be treated as a header, or it
            # poisons current_category for every subsequent fund until the next
            # real header (the B66-f1 carry-forward bug: ~2,572 close-ended FMPs
            # mis-tagged "IDF"). The "Schemes" prefix anchor distinguishes the
            # two reliably; an AMC name never ends in "Schemes" before a paren.
            stripped = line.strip()
            if stripped and "(" in stripped and ")" in stripped:
                open_idx = stripped.index("(")
                close_idx = stripped.rindex(")")
                prefix = stripped[:open_idx].strip()
                if close_idx > open_idx and prefix.lower().endswith("schemes"):
                    current_category = stripped[open_idx + 1 : close_idx].strip()
            # AMC-name lines and blank lines do not change the current category.
            continue
        # Skip the column-header row.
        if parts[0].strip().lower() == _SCHEME_CODE_HEADER:
            continue
        nav = _parse_nav(parts[4])
        if nav is None:
            continue
        nav_date = _parse_date(parts[5])
        if nav_date is None:
            continue
        rows.append(
            NavRow(
                amfi_code=parts[0].strip(),
                isin_growth=_isin_or_none(parts[1]),
                isin_reinvest=_isin_or_none(parts[2]),
                scheme_name=parts[3].strip(),
                nav=nav,
                nav_date=nav_date,
                category=current_category,
            )
        )
    return rows


def _parse_history_line(line: str) -> NavRow | None:
    """
    Parse ONE line of the HISTORICAL AMFI report (DownloadNAVHistoryReport_Po.aspx).

    Expected format — 8 fields, ";" delimiter, DIFFERENT column order
    compared to NAVAll.txt::

        Scheme Code;Scheme Name;ISIN Div Payout/ISIN Growth;
        ISIN Div Reinvestment;Net Asset Value;Repurchase Price;Sale Price;Date

    Field mapping: [0] code, [1] name, [2] ISIN growth, [3] ISIN reinvest,
    [4] NAV, [5] Repurchase (ignored), [6] Sale (ignored), [7] Date.

    Returns ``None`` for lines that do not split into exactly 8 fields, the
    column-header row, or rows with unparseable NAV/date.

    Single source of parsing truth for both ``parse_nav_history`` (whole-text,
    used by ``fetch_nav_history``) and ``stream_nav_history`` (line-by-line,
    memory-flat — used by the multi-year backfill).
    """
    parts = line.split(";")
    if len(parts) != _HISTORY_FIELDS:
        return None
    if parts[0].strip().lower() == _SCHEME_CODE_HEADER:
        return None
    nav = _parse_nav(parts[4])
    if nav is None:
        return None
    nav_date = _parse_date(parts[7])
    if nav_date is None:
        return None
    return NavRow(
        amfi_code=parts[0].strip(),
        isin_growth=_isin_or_none(parts[2]),
        isin_reinvest=_isin_or_none(parts[3]),
        scheme_name=parts[1].strip(),
        nav=nav,
        nav_date=nav_date,
    )


def parse_nav_history(text: str) -> list[NavRow]:
    """
    Parse the HISTORICAL AMFI report (DownloadNAVHistoryReport_Po.aspx).

    Delegates per-line parsing to ``_parse_history_line`` (shared with
    ``stream_nav_history``). Lines that do not split into exactly 8 fields,
    the header row, and rows with unparseable NAV or date are skipped.

    Note: AMFI caps this endpoint to ~3 months per request. For multi-year
    backfills the caller must loop over multiple (frmdt, todt) windows and
    concatenate results — this function and ``fetch_nav_history`` handle
    exactly one window each. ``stream_nav_history`` is the memory-flat
    variant used by the backfill pipeline.
    """
    rows: list[NavRow] = []
    for line in text.splitlines():
        row = _parse_history_line(line)
        if row is not None:
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Async fetchers
# ---------------------------------------------------------------------------

def _fmt_date(d: datetime.date) -> str:
    """Format a date as AMFI expects: "DD-Mmm-YYYY" (e.g. "02-Jun-2026")."""
    return d.strftime(_DATE_FMT)


async def fetch_navall(
    client: httpx.AsyncClient | None = None,
) -> list[NavRow]:
    """
    Fetch and parse the current daily NAV snapshot from AMFI.

    If *client* is supplied it is used as-is (useful for tests and for
    connection-pool sharing).  Otherwise a fresh ``AsyncClient`` is created
    and closed after the request.

    Raises ``ProviderError("amfi_nav", ...)`` on any HTTP or transport error.
    """
    headers = {"User-Agent": _USER_AGENT}
    try:
        if client is not None:
            resp = await client.get(NAVALL_URL, headers=headers, timeout=_TIMEOUT)
        else:
            async with httpx.AsyncClient() as c:
                resp = await c.get(NAVALL_URL, headers=headers, timeout=_TIMEOUT)
        if resp.status_code != 200:
            raise ProviderError(
                "amfi_nav",
                f"HTTP {resp.status_code} from NAVAll.txt",
            )
        return parse_navall(resp.text)
    except ProviderError:
        raise
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise ProviderError("amfi_nav", exc) from exc


async def fetch_navall_rows_with_category(
    client: httpx.AsyncClient | None = None,
) -> list[NavRow]:
    """
    Fetch the daily NAV snapshot from AMFI and parse it with category tracking.

    Mirrors ``fetch_navall`` but uses ``parse_navall_with_category`` so each
    returned ``NavRow`` carries the scheme-type section-header category
    (e.g. "Equity Scheme - Large Cap Fund").

    Raises ``ProviderError("amfi_nav", ...)`` on any HTTP or transport error.
    """
    headers = {"User-Agent": _USER_AGENT}
    try:
        if client is not None:
            resp = await client.get(NAVALL_URL, headers=headers, timeout=_TIMEOUT)
        else:
            async with httpx.AsyncClient() as c:
                resp = await c.get(NAVALL_URL, headers=headers, timeout=_TIMEOUT)
        if resp.status_code != 200:
            raise ProviderError(
                "amfi_nav",
                f"HTTP {resp.status_code} from NAVAll.txt",
            )
        return parse_navall_with_category(resp.text)
    except ProviderError:
        raise
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise ProviderError("amfi_nav", exc) from exc


async def fetch_nav_history(
    frmdt: datetime.date,
    todt: datetime.date,
    client: httpx.AsyncClient | None = None,
) -> list[NavRow]:
    """
    Fetch and parse a single window of historical NAV data from AMFI.

    *frmdt* and *todt* are passed as query params formatted "DD-Mmm-YYYY"
    (e.g. ``frmdt=01-Apr-2026&todt=30-Jun-2026``).

    **Single-window only.**  AMFI caps this endpoint to ~3 months per
    request.  For a multi-year backfill the caller must iterate over
    multiple non-overlapping windows and concatenate the results —
    looping is intentionally NOT done here.

    If *client* is supplied it is reused; otherwise a fresh one is created.

    Raises ``ProviderError("amfi_history", ...)`` on HTTP or transport error.
    """
    params = {"frmdt": _fmt_date(frmdt), "todt": _fmt_date(todt)}
    headers = {"User-Agent": _USER_AGENT}
    try:
        if client is not None:
            resp = await client.get(
                NAV_HISTORY_URL, params=params, headers=headers, timeout=_TIMEOUT
            )
        else:
            async with httpx.AsyncClient() as c:
                resp = await c.get(
                    NAV_HISTORY_URL, params=params, headers=headers, timeout=_TIMEOUT
                )
        if resp.status_code != 200:
            raise ProviderError(
                "amfi_history",
                f"HTTP {resp.status_code} from NAVHistoryReport",
            )
        return parse_nav_history(resp.text)
    except ProviderError:
        raise
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise ProviderError("amfi_history", exc) from exc


async def stream_nav_history(
    frmdt: datetime.date,
    todt: datetime.date,
    client: httpx.AsyncClient | None = None,
) -> AsyncIterator[NavRow]:
    """
    Stream-parse a single window of historical NAV data from AMFI, one row
    at a time — memory-flat sibling of ``fetch_nav_history``.

    A 90-day all-funds window can be ~1.1M lines. ``fetch_nav_history``
    materializes the whole response as a NavRow list; a caller that then
    builds a second full list of upsert dicts holds ~2x the window in memory
    at once, which is what OOM-killed the multi-year backfill on the
    640MiB celery-batch worker. This variant never buffers the response body
    or the parsed rows — it uses ``client.stream()`` + ``aiter_lines()`` and
    yields one ``NavRow`` per valid line, via the SAME ``_parse_history_line``
    rule ``parse_nav_history`` uses (single source of parsing truth).

    Same single-window contract as ``fetch_nav_history``: AMFI caps this
    endpoint to ~3 months per request; the caller loops over windows.

    Raises ``ProviderError("amfi_history", ...)`` on HTTP or transport error
    (raised lazily, on first iteration, per async-generator semantics).
    """
    params = {"frmdt": _fmt_date(frmdt), "todt": _fmt_date(todt)}
    headers = {"User-Agent": _USER_AGENT}
    owns_client = client is None
    c = client if client is not None else httpx.AsyncClient()
    try:
        async with c.stream(
            "GET", NAV_HISTORY_URL, params=params, headers=headers, timeout=_TIMEOUT
        ) as resp:
            if resp.status_code != 200:
                raise ProviderError(
                    "amfi_history",
                    f"HTTP {resp.status_code} from NAVHistoryReport",
                )
            async for line in resp.aiter_lines():
                row = _parse_history_line(line)
                if row is not None:
                    yield row
    except ProviderError:
        raise
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise ProviderError("amfi_history", exc) from exc
    finally:
        if owns_client:
            await c.aclose()
