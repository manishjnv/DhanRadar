"""
DhanRadar — AMC factsheet expense-ratio provider (Phase 6).

Parses TER (total expense ratio) rows from AMC factsheet HTML/text pages.
Only AMCs that serve parseable, non-bot-blocked pages are fetched; the five
bot-blocked AMCs (HDFC/SBI/ICICI_PRU/KOTAK/AXIS) are skipped with a recorded
status entry rather than a crash or a retry loop.

Public surface
--------------
ExpenseRatioRow   — pure dataclass (isin, ter_pct, effective_date)
parse_expense_ratios(html_or_text)    — PURE parser; no I/O
fetch_expense_ratios(client, sources) — async fetcher; best-effort per AMC

Compliance note
---------------
No advisory verbs, no aum imputation, no numeric scores. A row whose ter_pct
is outside 0 < ter ≤ 10 is INVALID; the caller (task) counts it as
stats.failed and never writes it. This module rejects such rows in parsing
so unit tests catch the boundary too.
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

# ISIN pattern for SEBI-style Indian mutual fund ISINs.
_ISIN_RE = re.compile(r"^INF[A-Z0-9]{9}$")
# Row pattern: ISIN | TER% | YYYY-MM-DD  (tab or pipe or comma separated)
# Also handles common factsheet table layouts with extra whitespace.
_ROW_RE = re.compile(
    r"(INF[A-Z0-9]{9})"           # group 1: ISIN
    r"[\s|,\t]+"                   # separator
    r"(\d+(?:\.\d+)?)"             # group 2: TER percentage
    r"[\s|,\t]+"                   # separator
    r"(\d{4}-\d{2}-\d{2})",        # group 3: effective date YYYY-MM-DD
    re.IGNORECASE,
)


@dataclass
class ExpenseRatioRow:
    """A single TER data point for one ISIN on one effective date."""

    isin: str
    ter_pct: float
    effective_date: date


def parse_expense_ratios(html_or_text: str) -> list[ExpenseRatioRow]:
    """Parse expense-ratio rows from a factsheet HTML/text page.

    PURE — no I/O, no DB, no network. Designed so the unit-test fixture
    matches the exact layout this parser handles:

        ISIN            | TER%  | effective_date
        INF123ABC456789 | 0.50  | 2026-06-01

    Rules:
    - Skip rows with no valid ISIN (must match ^INF[A-Z0-9]{9}$).
    - Skip rows where ter_pct <= 0 or ter_pct > 10 (out-of-range / data error);
      this boundary is also enforced by the DB CHECK constraint, but catching it
      here keeps the task's stats.failed counter honest.
    - Accepts pipe, comma, or tab as column separators; tolerant of extra spaces.
    - Does NOT fabricate, interpolate, or impute any missing value.
    """
    rows: list[ExpenseRatioRow] = []
    for match in _ROW_RE.finditer(html_or_text):
        isin = match.group(1).strip().upper()
        ter_raw = match.group(2).strip()
        date_raw = match.group(3).strip()

        # Validate ISIN format (belt-and-suspenders: the regex already anchors on INF).
        if not _ISIN_RE.match(isin):
            logger.debug("parse_expense_ratios: skipping invalid ISIN %r", isin)
            continue

        try:
            ter_pct = float(ter_raw)
        except ValueError:
            logger.debug("parse_expense_ratios: non-numeric TER %r for %s", ter_raw, isin)
            continue

        # Reject out-of-range TER — the DB CHECK also catches this, but we want
        # stats.failed to count it at the Python layer so the run reflects reality.
        if ter_pct <= 0 or ter_pct > 10:
            logger.debug(
                "parse_expense_ratios: TER %s out of range (0,10] for %s", ter_pct, isin
            )
            continue

        try:
            effective_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
        except ValueError:
            logger.debug(
                "parse_expense_ratios: bad date %r for %s", date_raw, isin
            )
            continue

        rows.append(ExpenseRatioRow(isin=isin, ter_pct=ter_pct, effective_date=effective_date))

    return rows


async def fetch_expense_ratios(
    client: httpx.AsyncClient,
    sources: list[dict[str, str]] | None = None,
) -> tuple[list[ExpenseRatioRow], dict]:
    """Fetch and parse TER rows from all non-bot-blocked AMC factsheet pages.

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

    all_rows: list[ExpenseRatioRow] = []
    bot_blocked: list[str] = []
    unreachable: list[str] = []
    ok: list[str] = []

    for amc in sources:
        name = amc.get("name", "<unknown>")
        url = amc.get("url", "")

        if is_bot_blocked(name):
            logger.debug("fetch_expense_ratios: %s is bot-blocked, skipping", name)
            bot_blocked.append(name)
            continue

        try:
            resp = await client.get(url, timeout=20.0)
            if resp.status_code != 200:
                logger.warning(
                    "fetch_expense_ratios: %s returned HTTP %s", name, resp.status_code
                )
                unreachable.append(name)
                continue

            parsed = parse_expense_ratios(resp.text)
            if not parsed:
                logger.info("fetch_expense_ratios: %s returned 0 parseable rows", name)
                unreachable.append(name)
                continue

            all_rows.extend(parsed)
            ok.append(name)
            logger.info(
                "fetch_expense_ratios: %s — %d rows parsed", name, len(parsed)
            )

        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPError) as exc:
            logger.warning("fetch_expense_ratios: %s network error: %s", name, exc)
            unreachable.append(name)
        except Exception as exc:  # noqa: BLE001 — best-effort; never abort the loop
            logger.warning("fetch_expense_ratios: %s unexpected error: %s", name, exc)
            unreachable.append(name)

    status: dict[str, list[str]] = {
        "bot_blocked": bot_blocked,
        "unreachable": unreachable,
        "ok": ok,
    }
    return all_rows, status
