"""
DhanRadar — AMFI Scheme Master parser and async fetcher.

Endpoint: https://portal.amfiindia.com/DownloadSchemeData_Po.aspx?mf=0
Format: semicolon-delimited text with header row:
  AMC;Code;Scheme Name;Scheme Type;Scheme Category;Scheme NAV Name;
  Scheme Minimum Amount;Launch Date;Closure Date;
  ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment

Pure module: no DB, no Redis, no Celery, no auth/billing/scoring imports.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from dhanradar.market_data.exceptions import ProviderError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEME_MASTER_URL = (
    "https://portal.amfiindia.com/DownloadSchemeData_Po.aspx?mf=0"
)

# AMFI/Cloudflare 403s on bare urllib UAs — mirror the guard in amfi.py.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

_DATE_FMT = "%d-%b-%Y"

# ISIN regex: must start with INF followed by exactly 9 alphanumeric chars.
_ISIN_RE = re.compile(r"^INF[A-Z0-9]{9}$")

# Column indices in the semicolon-delimited master file.
_COL_AMC = 0
_COL_CODE = 1
_COL_SCHEME_NAME = 2
_COL_SCHEME_TYPE = 3
_COL_SCHEME_CATEGORY = 4
# _COL_NAV_NAME = 5   (scheme NAV name — not used)
# _COL_MIN_AMOUNT = 6 (not used)
_COL_LAUNCH_DATE = 7
_COL_CLOSURE_DATE = 8
_COL_ISIN_GROWTH = 9
_COL_ISIN_REINVEST = 10

_EXPECTED_FIELDS = 11

# Header row sentinel — skip when present.
_HEADER_AMC = "amc"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class SchemeMasterRow:
    """One parsed, validated row from the AMFI Scheme Master file."""

    amfi_code: str
    scheme_name: str
    amc_name: str
    scheme_type: str | None
    scheme_category: str | None
    isin_growth: str | None
    isin_reinvest: str | None
    launch_date: date | None
    closure_date: date | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_date(raw: str) -> date | None:
    """Parse "DD-MMM-YYYY" (e.g. "01-Jun-2026") or return None on failure."""
    s = raw.strip()
    if not s or s in ("-", "N.A.", "N/A"):
        return None
    try:
        return datetime.strptime(s, _DATE_FMT).date()
    except (ValueError, AttributeError):
        return None


def _isin_valid(raw: str) -> str | None:
    """Return the ISIN if it matches ^INF[A-Z0-9]{9}$, else None."""
    s = raw.strip()
    if _ISIN_RE.match(s):
        return s
    return None


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse_scheme_master(text: str) -> list[SchemeMasterRow]:
    """
    Parse the AMFI Scheme Master text (semicolon-delimited, 11 fields).

    Header row (AMC;Code;…) is skipped.  Blank lines are skipped.  Rows that
    don't split into exactly 11 fields are skipped.

    Canonical ISIN preference: isin_growth first; else isin_reinvest.
    Rows where neither ISIN passes ``^INF[A-Z0-9]{9}$`` are SKIPPED — they
    cannot be keyed and are counted as failed by the task layer.

    Dates are parsed from ``DD-MMM-YYYY``; None on any parse failure (never
    fabricated).

    Pure function: no network, no DB, no side effects.
    """
    rows: list[SchemeMasterRow] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(";")
        if len(parts) != _EXPECTED_FIELDS:
            continue
        # Skip header row.
        if parts[_COL_AMC].strip().lower() == _HEADER_AMC:
            continue

        isin_g = _isin_valid(parts[_COL_ISIN_GROWTH])
        isin_r = _isin_valid(parts[_COL_ISIN_REINVEST])

        # Canonical ISIN: prefer growth, fall back to reinvest.
        # If neither is valid, skip this row entirely.
        if isin_g is None and isin_r is None:
            continue

        scheme_type_raw = parts[_COL_SCHEME_TYPE].strip()
        scheme_cat_raw = parts[_COL_SCHEME_CATEGORY].strip()

        rows.append(
            SchemeMasterRow(
                amfi_code=parts[_COL_CODE].strip(),
                scheme_name=parts[_COL_SCHEME_NAME].strip(),
                amc_name=parts[_COL_AMC].strip(),
                scheme_type=scheme_type_raw if scheme_type_raw else None,
                scheme_category=scheme_cat_raw if scheme_cat_raw else None,
                isin_growth=isin_g,
                isin_reinvest=isin_r,
                launch_date=_parse_date(parts[_COL_LAUNCH_DATE]),
                closure_date=_parse_date(parts[_COL_CLOSURE_DATE]),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Async fetcher
# ---------------------------------------------------------------------------


async def fetch_scheme_master(client: httpx.AsyncClient) -> str:
    """
    Fetch the AMFI Scheme Master text from the AMFI portal.

    ``client`` is always required (the task supplies its own pooled client).
    Returns the raw response text on HTTP 200.

    Raises ``ProviderError("amfi_scheme_master", ...)`` on:
    - non-200 HTTP status
    - empty response body
    - transport / timeout error

    Non-structural issues (e.g. a handful of malformed rows) are NOT raised
    here — the parser skips those rows silently and the task increments
    ``stats.failed`` per skipped row (caller responsibility).
    """
    headers = {"User-Agent": _USER_AGENT}
    try:
        resp = await client.get(SCHEME_MASTER_URL, headers=headers, timeout=_TIMEOUT)
        if resp.status_code != 200:
            raise ProviderError(
                "amfi_scheme_master",
                f"HTTP {resp.status_code} from DownloadSchemeData_Po.aspx",
            )
        text = resp.text
        if not text or not text.strip():
            raise ProviderError(
                "amfi_scheme_master",
                "Empty response body from DownloadSchemeData_Po.aspx",
            )
        return text
    except ProviderError:
        raise
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise ProviderError("amfi_scheme_master", exc) from exc
