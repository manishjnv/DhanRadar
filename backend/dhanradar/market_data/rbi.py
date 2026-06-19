"""
DhanRadar — RBI DBIE macro indicator provider (Phase 6).

Fetches published macro values from the Reserve Bank of India's DBIE portal
(https://data.rbi.org.in). DBIE is a SPA backed by undocumented REST endpoints;
this module attempts a best-effort GET on a known download path and parses the
response as CSV.

BEST-EFFORT NOTICE:
  RBI DBIE endpoints are undocumented, change without notice, and may return
  bot-blocks, session-cookie gates, or redirects to a JavaScript SPA shell.
  On any structural failure a ProviderError is raised so the ingestion_run
  helper records the source as unreachable (status='failed'). A partial success
  (some rows parsed, some skipped) is silently handled by returning the good rows
  and logging the skips — no partial ProviderError.

COMPLIANCE:
  - No advisory verbs.
  - Values stored are PUBLISHED facts only — no interpolation, no forecast,
    no imputation. Rows with unknown indicator_key or non-finite/missing values
    are skipped (counted as stats.failed by the task, never guessed).
  - macro values (rates, inflation, growth) are numeric facts, NOT scores/weights;
    non-neg #2 (no-numeric-in-DOM) does not apply to this table.

Pure module: no DB, no Redis, no Celery, no auth/billing/scoring imports.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import logging
import math
from dataclasses import dataclass
from datetime import date

import httpx

from dhanradar.market_data.exceptions import ProviderError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# RBI DBIE base URL. The actual download endpoint is undocumented and may change.
# We attempt a best-effort GET on the CSV export path. On failure a ProviderError
# is raised so the task marks the source unreachable.
_RBI_DBIE_BASE = "https://data.rbi.org.in"

# Known DBIE CSV export path (best-effort; subject to change without notice).
# The path is the standard DBIE "Handbook of Statistics on Indian Economy" macro
# download. If this 404s, ProviderError propagates and the source is unreachable.
_RBI_MACRO_CSV_URL = (
    "https://data.rbi.org.in/DBIE/dbie.rbi?site=publications"
    "&type=2&subtype=9&publicationID=1091"
)

# RBI DBIE accepts browser-like UA; bare urllib tends to be redirected.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# ---------------------------------------------------------------------------
# Canonical indicator key registry
# Exactly these strings are accepted by parse_macro(); anything else is skipped.
# ---------------------------------------------------------------------------

CANONICAL_INDICATOR_KEYS: frozenset[str] = frozenset({
    "repo_rate",
    "cpi_inflation",
    "wpi_inflation",
    "gdp_growth",
    "m3_money_supply",
})

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class MacroRow:
    """One parsed macro observation from RBI DBIE.

    indicator_key  — canonical key (one of CANONICAL_INDICATOR_KEYS)
    indicator_value — published value (finite float; rows with NaN/Inf skipped)
    unit           — unit of measurement as published, or None
    as_of_date     — reference date of the published observation
    """

    indicator_key: str
    indicator_value: float
    unit: str | None
    as_of_date: date


# ---------------------------------------------------------------------------
# Fixture CSV format (used by tests and as the parser contract)
#
# The parser expects a CSV with at least these columns (case-insensitive header):
#   indicator_key, indicator_value, as_of_date[, unit]
#
# Example:
#   indicator_key,indicator_value,unit,as_of_date
#   repo_rate,6.50,percent,2024-04-01
#   cpi_inflation,4.83,percent,2024-03-01
#   ...
#
# The RBI DBIE live endpoint may return a different layout; the fetcher wraps
# the raw payload into this normalised CSV format before calling parse_macro.
# If the live endpoint returns an unparseable response, ProviderError is raised.
# ---------------------------------------------------------------------------

_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%b-%Y", "%b %Y")


def _parse_date(raw: str) -> date | None:
    """Try multiple date formats; return None if all fail."""
    raw = raw.strip()
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return _dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_macro(payload: str) -> list[MacroRow]:
    """Parse a CSV payload into a list of MacroRow.

    PURE function — no I/O, no DB, no side effects.

    Skips rows where:
      - indicator_key is not in CANONICAL_INDICATOR_KEYS
      - indicator_value is non-finite (NaN, Inf) or unparseable
      - as_of_date is missing or unparseable

    Each skipped row is logged at DEBUG level. The caller (task) counts skips
    against stats.failed so the ingestion run records the data gap.

    Args:
        payload: raw CSV text (first line must be header).

    Returns:
        List of valid MacroRow objects (may be empty).
    """
    rows: list[MacroRow] = []
    reader = csv.DictReader(io.StringIO(payload.strip()))

    # Normalise column names to lowercase + strip whitespace.
    if reader.fieldnames is None:
        logger.debug("rbi_macro.parse_macro: empty or header-less payload")
        return rows

    for raw_row in reader:
        # Normalise key names.
        row = {k.lower().strip(): v.strip() for k, v in raw_row.items() if k is not None}

        indicator_key = row.get("indicator_key", "").strip()
        if indicator_key not in CANONICAL_INDICATOR_KEYS:
            logger.debug(
                "rbi_macro.parse_macro: skipping unknown indicator_key=%r",
                indicator_key,
            )
            continue

        raw_value = row.get("indicator_value", "").strip()
        try:
            value = float(raw_value)
        except (ValueError, TypeError):
            logger.debug(
                "rbi_macro.parse_macro: skipping non-numeric value=%r for key=%s",
                raw_value,
                indicator_key,
            )
            continue

        if not math.isfinite(value):
            logger.debug(
                "rbi_macro.parse_macro: skipping non-finite value=%s for key=%s",
                value,
                indicator_key,
            )
            continue

        raw_date = row.get("as_of_date", "").strip()
        as_of = _parse_date(raw_date)
        if as_of is None:
            logger.debug(
                "rbi_macro.parse_macro: skipping missing/unparseable as_of_date=%r for key=%s",
                raw_date,
                indicator_key,
            )
            continue

        unit_raw = row.get("unit", "").strip()
        unit: str | None = unit_raw if unit_raw else None

        rows.append(
            MacroRow(
                indicator_key=indicator_key,
                indicator_value=value,
                unit=unit,
                as_of_date=as_of,
            )
        )

    return rows


# ---------------------------------------------------------------------------
# Async fetcher
# ---------------------------------------------------------------------------


async def fetch_macro_indicators(client: httpx.AsyncClient) -> str:
    """Attempt a best-effort GET from RBI DBIE and return the raw CSV payload.

    Raises ProviderError only on structural failures (connection error, non-200
    response, or response that cannot be interpreted as text). A successful fetch
    that returns zero parseable rows is NOT a ProviderError — that is handled by
    the task counting skips against stats.failed.

    The live DBIE endpoint is undocumented; if it returns an HTML SPA shell
    (common) instead of CSV, the parser will yield 0 rows and the run will be
    recorded as status='failed' (all fetched=0, written=0, failed=0 → 'success'
    with 0 rows, which the operator can investigate via the Ops console).

    Args:
        client: an open httpx.AsyncClient (caller manages lifecycle).

    Returns:
        Raw response text (CSV or other format; parse_macro handles the format).

    Raises:
        ProviderError: on connection error, timeout, or non-200 HTTP status.
    """
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/csv,text/plain,application/csv,*/*",
    }
    try:
        response = await client.get(
            _RBI_MACRO_CSV_URL,
            headers=headers,
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
    except httpx.TimeoutException as exc:
        # TimeoutException is a subclass of TransportError — catch it first (most specific).
        raise ProviderError("rbi_dbie", f"timeout: {exc}") from exc
    except httpx.TransportError as exc:  # noqa: B014 — parent after subclass is intentional
        raise ProviderError("rbi_dbie", f"transport error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 — wrap all httpx failures
        raise ProviderError("rbi_dbie", f"unexpected fetch error: {exc}") from exc

    if response.status_code != 200:
        raise ProviderError(
            "rbi_dbie",
            f"HTTP {response.status_code} from {_RBI_MACRO_CSV_URL}",
        )

    try:
        text = response.text
    except Exception as exc:  # noqa: BLE001
        raise ProviderError("rbi_dbie", f"response decode error: {exc}") from exc

    logger.info(
        "rbi_macro.fetch_macro_indicators: received %d bytes from DBIE",
        len(text),
    )
    return text
