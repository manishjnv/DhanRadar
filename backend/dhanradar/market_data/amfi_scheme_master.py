"""
DhanRadar — AMFI Scheme Master parser and async fetcher.

Endpoint: https://portal.amfiindia.com/DownloadSchemeData_Po.aspx?mf=0
Format: COMMA-delimited CSV (verified against the live feed 2026-06-19), header row:
  AMC,Code,Scheme Name,Scheme Type,Scheme Category,Scheme NAV Name,
  Scheme Minimum Amount,Launch Date,Closure Date,ISIN Div Payout/ISIN Growth+ISIN Div Reinvestment
i.e. 10 comma-separated fields per data row. QUIRK: the final field carries BOTH
ISINs (Div-Payout/Growth and Div-Reinvestment) CONCATENATED with no separator
(e.g. "INF209K01157INF209K01CE5") — an ISIN is exactly 12 chars (INF + 9), so the two
are split by a 12-char window / regex findall, not by a delimiter. A single 12-char
value means growth only (no reinvest plan).

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

# ISIN: INF followed by exactly 9 alphanumeric chars (12 total). The final CSV field
# concatenates the Growth and Reinvest ISINs with no separator, so findall extracts
# the 1–2 tokens by their fixed 12-char shape.
_ISIN_FINDALL = re.compile(r"INF[A-Z0-9]{9}")

# Comma-delimited CSV, 10 fields per data row. Scheme Name / NAV Name could in
# principle contain a comma, so the trailing columns are anchored from the RIGHT
# (the structured tail is fixed-width) and the name is re-joined from the middle.
_MIN_FIELDS = 10
_COL_AMC = 0
_COL_CODE = 1
_COL_SCHEME_NAME = 2
# From the right: [-1]=ISIN blob, [-2]=closure, [-3]=launch, [-4]=min amount,
# [-5]=NAV name, [-6]=category, [-7]=scheme type; scheme name = parts[2:-7].
_COL_ISIN_BLOB = -1
_COL_CLOSURE_DATE = -2
_COL_LAUNCH_DATE = -3
_COL_SCHEME_CATEGORY = -6
_COL_SCHEME_TYPE = -7
_NAME_TAIL = -7  # scheme name = ",".join(parts[2:_NAME_TAIL])

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


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse_scheme_master(text: str) -> list[SchemeMasterRow]:
    """
    Parse the AMFI Scheme Master CSV (comma-delimited, ≥10 fields per data row).

    Header row (``AMC,Code,…``) and blank lines are skipped. A data row is
    identified by a numeric Code in field[1]; rows with fewer than 10 fields or a
    non-numeric code are skipped (header/garbage). Trailing structured columns are
    anchored from the right so a stray comma inside a scheme name does not shift the
    ISIN/date columns; the scheme name is re-joined from the middle.

    The final field concatenates the Growth and Reinvest ISINs with no separator;
    both are extracted by ``re.findall`` (each ISIN is exactly 12 chars). Canonical
    ISIN preference: growth first, else reinvest. Rows where neither ISIN is present
    are SKIPPED — they cannot be keyed (counted as failed by the task layer).

    Dates parse from ``DD-MMM-YYYY``; None on failure (never fabricated).

    Pure function: no network, no DB, no side effects.
    """
    rows: list[SchemeMasterRow] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < _MIN_FIELDS:
            continue
        # A data row has a numeric AMFI code in field[1]; this also skips the
        # header (Code == "Code") and any stray non-data lines.
        if not parts[_COL_CODE].strip().isdigit():
            continue

        isins = _ISIN_FINDALL.findall(parts[_COL_ISIN_BLOB].strip())
        isin_g = isins[0] if isins else None
        isin_r = isins[1] if len(isins) > 1 else None
        # If neither ISIN is present, skip — the row cannot be keyed.
        if isin_g is None and isin_r is None:
            continue

        scheme_name = ",".join(parts[_COL_SCHEME_NAME:_NAME_TAIL]).strip()
        scheme_type_raw = parts[_COL_SCHEME_TYPE].strip()
        scheme_cat_raw = parts[_COL_SCHEME_CATEGORY].strip()

        rows.append(
            SchemeMasterRow(
                amfi_code=parts[_COL_CODE].strip(),
                scheme_name=scheme_name,
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
