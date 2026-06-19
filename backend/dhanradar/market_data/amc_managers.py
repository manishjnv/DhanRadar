"""
DhanRadar — AMC factsheet fund-manager provider (Phase 6).

Parses fund-manager tenure rows from AMC factsheet HTML/text pages.
Only AMCs that serve parseable, non-bot-blocked pages are fetched; the five
bot-blocked AMCs (HDFC/SBI/ICICI_PRU/KOTAK/AXIS) are skipped with a recorded
status entry rather than a crash or a retry loop.

Public surface
--------------
FundManagerRow                          — pure dataclass
parse_fund_managers(html_or_text)       — PURE parser; no I/O
fetch_fund_managers(client, sources)    — async fetcher; best-effort per AMC

Factsheet layout handled
------------------------
The parser targets a simple delimited row format that AMC factsheet pages
expose (or that a thin scraper wrapper produces):

    scheme_uid | manager_name | start_date | end_date
    INF123ABC456 | Priya Sharma | 2021-06-01 |
    INF456DEF012 | Rahul Mehta  | 2019-03-15 | 2023-12-31

Columns may be separated by pipe (|), comma, or tab. end_date is optional
(blank = current manager). Both YYYY-MM-DD and DD-Mon-YYYY date formats are
accepted (matching common AMFI/SEBI factsheet conventions).

Compliance note
---------------
No advisory verbs, no aum imputation, no numeric scores. A row whose
scheme_uid does not match ^INF[A-Z0-9]{9}$ or whose manager_name is empty
or whose start_date is missing is INVALID; it is silently dropped by the
parser so the task's stats.failed counter reflects only rows the pipeline
itself attempted to write.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from dhanradar.market_data.amc_registry import (
    AMC_FACTSHEET_SOURCES,
    is_bot_blocked,
)

logger = logging.getLogger(__name__)

# ISIN pattern for SEBI-style Indian mutual fund ISINs (12 chars total).
_ISIN_RE = re.compile(r"^INF[A-Z0-9]{9}$")

# Row pattern: ISIN | manager_name | start_date [ | end_date ]
# Separator: pipe, comma, or tab (with surrounding whitespace).
# Dates accepted: YYYY-MM-DD or DD-Mon-YYYY (e.g. 01-Jun-2021).
_SEP = r"[\s]*[|,\t][\s]*"
_DATE_PAT = r"(\d{4}-\d{2}-\d{2}|\d{2}-[A-Za-z]{3}-\d{4})"
_ROW_RE = re.compile(
    r"(INF[A-Z0-9]{9})"   # group 1: ISIN / scheme_uid
    + _SEP
    + r"([^|,\t\r\n]+?)"  # group 2: manager_name (non-greedy, no sep chars)
    + _SEP
    + _DATE_PAT            # group 3: start_date
    + r"(?:" + _SEP + r"(" + r"\d{4}-\d{2}-\d{2}|\d{2}-[A-Za-z]{3}-\d{4}" + r")" + r")?",  # group 4: optional end_date
    re.IGNORECASE,
)

_DATE_FORMATS = ("%Y-%m-%d", "%d-%b-%Y")


def _parse_date(raw: str) -> date | None:
    """Try both YYYY-MM-DD and DD-Mon-YYYY; return None on failure."""
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class FundManagerRow:
    """A single fund-manager tenure record.

    scheme_uid  — SEBI ISIN (^INF[A-Z0-9]{9}$); the canonical scheme identifier.
    manager_name — full name of the fund manager.
    start_date   — date the manager took charge of this scheme.
    end_date     — date tenure ended; None means the manager is current.
    """

    scheme_uid: str
    manager_name: str
    start_date: date
    end_date: date | None


def parse_fund_managers(html_or_text: str) -> list[FundManagerRow]:
    """Parse fund-manager tenure rows from a factsheet HTML/text page.

    PURE — no I/O, no DB, no network. Designed so the unit-test fixture
    matches the exact layout this parser handles:

        scheme_uid    | manager_name  | start_date  | end_date
        INF123ABC456  | Priya Sharma  | 2021-06-01  |
        INF456DEF012  | Rahul Mehta   | 2019-03-15  | 2023-12-31

    Rules:
    - Skip rows with no valid ISIN (must match ^INF[A-Z0-9]{9}$).
    - Skip rows with an empty manager_name (after strip).
    - Skip rows with a missing or unparseable start_date.
    - end_date is optional; blank / absent → None (current manager).
    - Does NOT fabricate, interpolate, or impute any missing value.
    """
    rows: list[FundManagerRow] = []
    for match in _ROW_RE.finditer(html_or_text):
        isin_raw = match.group(1).strip().upper()
        name_raw = match.group(2).strip()
        start_raw = match.group(3).strip()
        end_raw = (match.group(4) or "").strip()

        # Validate ISIN format.
        if not _ISIN_RE.match(isin_raw):
            logger.debug("parse_fund_managers: skipping invalid ISIN %r", isin_raw)
            continue

        # Require non-empty manager name.
        if not name_raw:
            logger.debug("parse_fund_managers: empty manager_name for %s", isin_raw)
            continue

        # Require a parseable start_date.
        start_date = _parse_date(start_raw)
        if start_date is None:
            logger.debug(
                "parse_fund_managers: bad start_date %r for %s", start_raw, isin_raw
            )
            continue

        end_date: date | None = None
        if end_raw:
            end_date = _parse_date(end_raw)
            if end_date is None:
                logger.debug(
                    "parse_fund_managers: bad end_date %r for %s — treating as None",
                    end_raw,
                    isin_raw,
                )

        rows.append(
            FundManagerRow(
                scheme_uid=isin_raw,
                manager_name=name_raw,
                start_date=start_date,
                end_date=end_date,
            )
        )

    return rows


async def fetch_fund_managers(
    client: httpx.AsyncClient,
    sources: list[dict[str, str]] | None = None,
) -> tuple[list[FundManagerRow], dict]:
    """Fetch and parse fund-manager rows from all non-bot-blocked AMC factsheet pages.

    Args:
        client:  An httpx.AsyncClient (injected; allows test mocking).
        sources: List of AMC dicts with 'name' and 'url'. Defaults to
                 AMC_FACTSHEET_SOURCES (non-bot-blocked AMCs only).

    Returns:
        (all_rows, status_dict) where status_dict has keys:
            "bot_blocked"  — list of AMC names skipped due to bot protection
            "unreachable"  — list of AMC names where GET/parse failed
            "ok"           — list of AMC names that returned >= 1 row

    Contract:
    - Never raises; best-effort per AMC (a single AMC failure does NOT abort
      the rest). This is the §20 resilience rule: a failed source is recorded
      as unreachable, never a silent drop or a crash.
    - Does NOT retry on failure or timeout — one attempt per AMC per run.
    - Does NOT fetch bot-blocked AMCs even if they appear in `sources`.
    """
    if sources is None:
        sources = AMC_FACTSHEET_SOURCES

    all_rows: list[FundManagerRow] = []
    bot_blocked: list[str] = []
    unreachable: list[str] = []
    ok: list[str] = []

    for amc in sources:
        name = amc.get("name", "<unknown>")
        url = amc.get("url", "")

        if is_bot_blocked(name):
            logger.debug("fetch_fund_managers: %s is bot-blocked, skipping", name)
            bot_blocked.append(name)
            continue

        try:
            resp = await client.get(url, timeout=20.0)
            if resp.status_code != 200:
                logger.warning(
                    "fetch_fund_managers: %s returned HTTP %s", name, resp.status_code
                )
                unreachable.append(name)
                continue

            parsed = parse_fund_managers(resp.text)
            if not parsed:
                logger.info("fetch_fund_managers: %s returned 0 parseable rows", name)
                unreachable.append(name)
                continue

            all_rows.extend(parsed)
            ok.append(name)
            logger.info(
                "fetch_fund_managers: %s — %d rows parsed", name, len(parsed)
            )

        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPError) as exc:
            logger.warning("fetch_fund_managers: %s network error: %s", name, exc)
            unreachable.append(name)
        except Exception as exc:  # noqa: BLE001 — best-effort; never abort the loop
            logger.warning("fetch_fund_managers: %s unexpected error: %s", name, exc)
            unreachable.append(name)

    status: dict[str, list[str]] = {
        "bot_blocked": bot_blocked,
        "unreachable": unreachable,
        "ok": ok,
    }
    return all_rows, status
