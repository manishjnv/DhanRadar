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


def parse_nav_history(text: str) -> list[NavRow]:
    """
    Parse the HISTORICAL AMFI report (DownloadNAVHistoryReport_Po.aspx).

    Expected format — 8 fields, ";" delimiter, DIFFERENT column order
    compared to NAVAll.txt::

        Scheme Code;Scheme Name;ISIN Div Payout/ISIN Growth;
        ISIN Div Reinvestment;Net Asset Value;Repurchase Price;Sale Price;Date

    Field mapping: [0] code, [1] name, [2] ISIN growth, [3] ISIN reinvest,
    [4] NAV, [5] Repurchase (ignored), [6] Sale (ignored), [7] Date.

    Lines that do not split into exactly 8 fields are skipped.
    Rows with unparseable NAV or date are also skipped.

    Note: AMFI caps this endpoint to ~3 months per request. For multi-year
    backfills the caller must loop over multiple (frmdt, todt) windows and
    concatenate results — this function and ``fetch_nav_history`` handle
    exactly one window each.
    """
    rows: list[NavRow] = []
    for line in text.splitlines():
        parts = line.split(";")
        if len(parts) != _HISTORY_FIELDS:
            continue
        if parts[0].strip().lower() == _SCHEME_CODE_HEADER:
            continue
        nav = _parse_nav(parts[4])
        if nav is None:
            continue
        nav_date = _parse_date(parts[7])
        if nav_date is None:
            continue
        rows.append(
            NavRow(
                amfi_code=parts[0].strip(),
                isin_growth=_isin_or_none(parts[2]),
                isin_reinvest=_isin_or_none(parts[3]),
                scheme_name=parts[1].strip(),
                nav=nav,
                nav_date=nav_date,
            )
        )
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
