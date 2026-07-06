"""
DhanRadar — UTI fund-manager JSON-API provider (Phase 6 rebuild, 2026-07).

UTI Mutual Fund's public site (utimf.com) is an Angular SPA (a `<genesis-investor-root>`
web-component shell); the old factsheet-listing URL AMC_FACTSHEET_SOURCES used to
carry for UTI (/forms-and-downloads/factsheet) now 404s -- there is no scrapeable
static factsheet page. Real-browser network inspection of a scheme detail page
(2026-07-06) found the Drupal-CMS JSON backend the SPA itself calls still lives
and answers unauthenticated GET requests:

  GET https://www.utimf.com/api/get_investor_scheme_fund
      -> {"data": [{"field_fund_name": <scheme name>, "nid": <drupal node id>,
                    "fund_manager_info": [{"field_manager_name": ...}, ...]}, ...]}
      ONE call returns all (~77 at time of writing) UTI schemes + node ids.
      `fund_manager_info` has manager NAMES but no tenure start date -- it is
      used ONLY to enumerate the nids to loop over below.

  GET https://www.utimf.com/api/scheme_mangaer/{nid}   (sic — the AMC's typo, not ours)
      -> {"rows": [{"title": <scheme name>, "field_name_fund": <manager name>,
                    "field_from_date": <MM-DD-YYYY>, ...}, ...]}
      Per-scheme manager tenure rows including the start date. This is the
      authoritative per-manager record this module extracts.

field_from_date format: MM-DD-YYYY. Confirmed against real payload values
"10-15-2025" and "08-17-2023" -- both have a day-of-month (15, 17) in the
SECOND position, which is impossible under DD-MM-YYYY. This is NOT the same
date convention `amc_managers.parse_fund_managers` accepts (YYYY-MM-DD /
DD-Mon-YYYY) -- do not reuse that parser's date regex here.

Rows are returned keyed by scheme NAME (UTI's JSON has no ISIN field). ISIN
resolution reuses the pg_trgm fuzzy-matcher already used by the constituents
pipeline (`dhanradar.tasks.mf._resolve_scheme_isins`) -- never a second
matcher; see `tasks/mf_fund_manager.py` for where that resolution happens.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

import httpx

from dhanradar.market_data.amc_managers import RawManagerRow

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.utimf.com"
_SCHEME_LIST_PATH = "/api/get_investor_scheme_fund"
_MANAGER_PATH_TMPL = "/api/scheme_mangaer/{nid}"

_MIN_NAME_LEN = 3
_MAX_NAME_LEN = 80
_PLACEHOLDER_NAMES = {"n/a", "na", "-", "tbd", "none", ""}


def _parse_mm_dd_yyyy(raw: str) -> date | None:
    """Parse UTI's MM-DD-YYYY `field_from_date`. None on any format mismatch —
    never guess the other field order."""
    raw = (raw or "").strip()
    try:
        return datetime.strptime(raw, "%m-%d-%Y").date()
    except ValueError:
        return None


def _is_plausible_manager_name(name: str) -> bool:
    """Fail-closed shape check — reject empty/placeholder/too-short/too-long
    strings that are obviously not a person's name (section headers, 'N/A', etc.)."""
    name = (name or "").strip()
    if not (_MIN_NAME_LEN <= len(name) <= _MAX_NAME_LEN):
        return False
    if name.lower() in _PLACEHOLDER_NAMES:
        return False
    if not re.search(r"[A-Za-z]", name):
        return False
    return True


def parse_uti_scheme_list(payload: dict) -> list[str]:
    """PURE parser — no I/O. Extracts the list of Drupal node ids from a
    `get_investor_scheme_fund` JSON payload. Returns [] for any malformed shape
    (fail closed; caller records this as format_mismatch, not a crash)."""
    entries = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []
    nids: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        nid = entry.get("nid")
        if nid:
            nids.append(str(nid))
    return nids


def parse_uti_scheme_manager_rows(payload: dict) -> list[RawManagerRow]:
    """PURE parser — no I/O. Extracts high-confidence rows from one
    `scheme_mangaer/{nid}` JSON payload. A row missing scheme name / a
    plausible manager name / a parseable start_date is dropped (fail-closed,
    never guessed)."""
    rows_in = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows_in, list):
        return []

    rows: list[RawManagerRow] = []
    for row in rows_in:
        if not isinstance(row, dict):
            continue
        scheme_name = (row.get("title") or "").strip()
        manager_name = (row.get("field_name_fund") or "").strip()
        start_date = _parse_mm_dd_yyyy(row.get("field_from_date") or "")

        if not scheme_name or not _is_plausible_manager_name(manager_name) or start_date is None:
            logger.debug(
                "parse_uti_scheme_manager_rows: dropping low-confidence row scheme=%r manager=%r date=%r",
                scheme_name,
                manager_name,
                row.get("field_from_date"),
            )
            continue

        rows.append(
            RawManagerRow(scheme_name=scheme_name, manager_name=manager_name, start_date=start_date)
        )
    return rows


async def fetch_uti_fund_managers(
    client: httpx.AsyncClient,
) -> tuple[list[RawManagerRow], dict]:
    """Fetch UTI fund-manager tenure rows via the two JSON endpoints documented
    above.

    Returns (rows, status) with the SAME status-bucket contract as
    `amc_managers.fetch_fund_managers`: "bot_blocked" (always [] — UTI is not
    bot-blocked), "unreachable" (network/HTTP failure on the scheme-list call),
    "format_mismatch" (HTTP 200 but the JSON shape changed / 0 usable rows),
    "ok" (["UTI"] if >= 1 row extracted).

    Never raises; a single per-scheme manager-detail call failing does NOT
    abort the others (best-effort, mirrors the §20 resilience rule the
    factsheet fetcher already follows).
    """
    empty_unreachable = {"bot_blocked": [], "unreachable": ["UTI"], "format_mismatch": [], "ok": []}
    empty_format_mismatch = {
        "bot_blocked": [],
        "unreachable": [],
        "format_mismatch": ["UTI"],
        "ok": [],
    }

    try:
        resp = await client.get(f"{_BASE_URL}{_SCHEME_LIST_PATH}", timeout=20.0)
        if resp.status_code != 200:
            logger.warning("fetch_uti_fund_managers: scheme list HTTP %s", resp.status_code)
            return [], empty_unreachable
        payload = resp.json()
    except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPError) as exc:
        logger.warning("fetch_uti_fund_managers: scheme list network error: %s", exc)
        return [], empty_unreachable
    except Exception as exc:  # noqa: BLE001 — e.g. non-JSON HTTP 200 body; site up, shape wrong
        logger.warning("fetch_uti_fund_managers: scheme list unexpected error: %s", exc)
        return [], empty_format_mismatch

    nids = parse_uti_scheme_list(payload)
    if not nids:
        logger.info("fetch_uti_fund_managers: scheme list returned 0 usable nids (format_mismatch)")
        return [], empty_format_mismatch

    rows: list[RawManagerRow] = []
    for nid in nids:
        try:
            detail_resp = await client.get(
                f"{_BASE_URL}{_MANAGER_PATH_TMPL.format(nid=nid)}", timeout=20.0
            )
            if detail_resp.status_code != 200:
                logger.debug(
                    "fetch_uti_fund_managers: nid=%s HTTP %s", nid, detail_resp.status_code
                )
                continue
            detail_payload = detail_resp.json()
        except Exception as exc:  # noqa: BLE001 — one bad nid must not abort the loop
            logger.debug("fetch_uti_fund_managers: nid=%s fetch failed: %s", nid, exc)
            continue

        rows.extend(parse_uti_scheme_manager_rows(detail_payload))

    if not rows:
        logger.info(
            "fetch_uti_fund_managers: 0 high-confidence rows across %d schemes (format_mismatch)",
            len(nids),
        )
        return [], empty_format_mismatch

    logger.info("fetch_uti_fund_managers: %d rows parsed across %d schemes", len(rows), len(nids))
    return rows, {"bot_blocked": [], "unreachable": [], "format_mismatch": [], "ok": ["UTI"]}
