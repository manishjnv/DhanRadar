"""
DhanRadar — NIPPON factsheet PDF fund-manager parser (Phase 6 rebuild, 2026-07).

NIPPON's public factsheet-listing page (the AMC_FACTSHEET_SOURCES url) is real
(reachable, not bot-blocked) but does not serve delimited rows the way
`amc_managers.parse_fund_managers` expects — it links out to a monthly PDF
factsheet (e.g. Nippon-FS-JUNE-2026.pdf, ~20MB, ~167 pages, one scheme per
page, confirmed by downloading the live June 2026 file). This module extracts
fund-manager tenure rows from that PDF's TEXT using `pypdf` (already installed
transitively via `casparser`'s CAS-parsing dependency chain — no new
dependency added; verified with `pip show pypdf` before writing this module).

Real layout (verified against the June 2026 factsheet, one page per scheme):

    <Scheme Name>
    <Category line, may contain parentheses>
    Details as on <Month DD, YYYY>
    ... (scheme prose) ...
    Fund Manager(s)
    <Manager Name> (Managing Since <Mon> <YYYY>)
    Total Experience of more than <N> years
    [<Manager Name 2> (Assistant Fund Manager) (Managing Since <Mon> <YYYY>)
    Total Experience of more than <N> years]
    AMFI Tier 1 Benchmark
    ...

`Managing Since <Mon> <YYYY>` is MONTH+YEAR granularity only (no day). This
parser anchors `start_date` to day 1 of that month — an explicit, disclosed
normalisation of the stated granularity, not a fabricated value (the month
and year themselves are exactly what the PDF states; nothing is invented).

FAIL-CLOSED: a page's manager rows are only kept if BOTH a scheme-name
heading AND at least one manager line matching the exact
"(Managing Since <Mon> <YYYY>)" shape are found on the SAME page. Any page
missing either is silently skipped — no partial/guessed row (e.g. a page
whose category line broke the scheme-name regex correctly yields nothing
rather than a mis-attributed manager).

Returns `RawManagerRow` (scheme NAME, not ISIN); ISIN resolution reuses the
shared pg_trgm fuzzy-matcher (`dhanradar.tasks.mf._resolve_scheme_isins`,
also used by amc_managers_uti.py) at the task layer — never a second matcher.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import httpx
import pypdf

from dhanradar.market_data.amc_managers import RawManagerRow

logger = logging.getLogger(__name__)

_LISTING_URL = "https://mf.nipponindiaim.com/investor-service/downloads/factsheet-portfolio-and-other-disclosures"
_PDF_BASE_URL = "https://mf.nipponindiaim.com"

# Matches e.g. href="/InvestorServices/FactSheetsDocuments/Nippon-FS-JUNE-2026.pdf"
# The listing page lists the newest month first (verified 2026-07-06), so the
# FIRST match is the latest factsheet.
_PDF_LINK_RE = re.compile(r'href="([^"]*Nippon-FS-[^"]*\.pdf)"', re.IGNORECASE)

_FM_BLOCK_RE = re.compile(r"Fund Manager\(s\)\s*\n(.*?)\n\s*AMFI", re.DOTALL)
_MGR_LINE_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z .'\-]+?)\s*(?:\([^)]*\))?\s*"
    r"\(Managing Since\s+(?P<mon>[A-Za-z]{3,9})\s+(?P<year>\d{4})\)"
)
_SCHEME_NAME_RE = re.compile(
    r"([A-Z][A-Za-z0-9&.,'\-\s]{3,80}?Fund)\s*\n[A-Za-z0-9 &\-()]{2,60}\s*\nDetails as on"
)
_MONTH_MAP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _parse_month_year(mon: str, year: str) -> date | None:
    month_num = _MONTH_MAP.get(mon.strip().lower()[:3])
    if month_num is None:
        return None
    try:
        return date(int(year), month_num, 1)
    except ValueError:
        return None


def parse_nippon_factsheet_pages(page_texts: list[str]) -> list[RawManagerRow]:
    """PURE parser — no I/O. Takes the already-extracted per-page text of a
    NIPPON monthly factsheet PDF (one entry per PDF page, in page order) and
    returns high-confidence (scheme_name, manager_name, start_date) rows.
    """
    rows: list[RawManagerRow] = []
    for page_text in page_texts:
        fm_match = _FM_BLOCK_RE.search(page_text)
        if not fm_match:
            continue
        scheme_match = _SCHEME_NAME_RE.search(page_text)
        if not scheme_match:
            # Fund Manager(s) block found but no confident scheme-name heading
            # on this page — fail closed, drop the whole page's rows rather
            # than guess which scheme they belong to.
            logger.debug(
                "parse_nippon_factsheet_pages: Fund Manager(s) block with no scheme-name match, skipping page"
            )
            continue
        scheme_name = scheme_match.group(1).strip()

        block = fm_match.group(1)
        for line in (ln.strip() for ln in block.split("\n") if ln.strip()):
            m = _MGR_LINE_RE.match(line)
            if not m:
                continue
            manager_name = m.group("name").strip()
            start_date = _parse_month_year(m.group("mon"), m.group("year"))
            if not manager_name or start_date is None:
                continue
            rows.append(
                RawManagerRow(
                    scheme_name=scheme_name, manager_name=manager_name, start_date=start_date
                )
            )
    return rows


def extract_pdf_page_texts(pdf_bytes: bytes) -> list[str]:
    """CPU-bound (no network) — extracts per-page text from a factsheet PDF's
    raw bytes via pypdf. Isolated from `parse_nippon_factsheet_pages` so the
    parser itself stays pure/testable against captured fixture text."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return [(page.extract_text() or "") for page in reader.pages]


async def fetch_nippon_fund_managers(
    client: httpx.AsyncClient,
) -> tuple[list[RawManagerRow], dict]:
    """Fetch + parse NIPPON's current monthly factsheet PDF for fund-manager rows.

    Returns (rows, status) with the SAME status-bucket contract as
    `amc_managers.fetch_fund_managers`. Never raises — a discovery failure,
    download failure, or PDF-parse failure all degrade to a recorded status
    entry, never a crash or a partial/guessed row.
    """
    empty_unreachable = {
        "bot_blocked": [],
        "unreachable": ["NIPPON"],
        "format_mismatch": [],
        "ok": [],
    }
    empty_format_mismatch = {
        "bot_blocked": [],
        "unreachable": [],
        "format_mismatch": ["NIPPON"],
        "ok": [],
    }

    try:
        resp = await client.get(_LISTING_URL, timeout=20.0, follow_redirects=True)
        if resp.status_code != 200:
            logger.warning("fetch_nippon_fund_managers: listing page HTTP %s", resp.status_code)
            return [], empty_unreachable
        html = resp.text
    except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPError) as exc:
        logger.warning("fetch_nippon_fund_managers: listing page network error: %s", exc)
        return [], empty_unreachable

    pdf_match = _PDF_LINK_RE.search(html)
    if not pdf_match:
        logger.info(
            "fetch_nippon_fund_managers: no factsheet PDF link found on listing page (format_mismatch)"
        )
        return [], empty_format_mismatch

    pdf_url = pdf_match.group(1)
    if pdf_url.startswith("/"):
        pdf_url = _PDF_BASE_URL + pdf_url

    try:
        pdf_resp = await client.get(pdf_url, timeout=60.0, follow_redirects=True)
        if pdf_resp.status_code != 200:
            logger.warning(
                "fetch_nippon_fund_managers: PDF download HTTP %s url=%s",
                pdf_resp.status_code,
                pdf_url,
            )
            return [], empty_unreachable
        pdf_bytes = pdf_resp.content
    except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPError) as exc:
        logger.warning("fetch_nippon_fund_managers: PDF download network error: %s", exc)
        return [], empty_unreachable

    try:
        page_texts = extract_pdf_page_texts(pdf_bytes)
    except Exception as exc:  # noqa: BLE001 — a corrupt/changed PDF must not crash the run
        logger.warning("fetch_nippon_fund_managers: PDF extraction failed: %s", exc)
        return [], empty_format_mismatch

    rows = parse_nippon_factsheet_pages(page_texts)
    if not rows:
        logger.info(
            "fetch_nippon_fund_managers: 0 high-confidence rows in %d-page PDF (format_mismatch)",
            len(page_texts),
        )
        return [], empty_format_mismatch

    logger.info(
        "fetch_nippon_fund_managers: %d rows parsed from %d-page PDF", len(rows), len(page_texts)
    )
    return rows, {"bot_blocked": [], "unreachable": [], "format_mismatch": [], "ok": ["NIPPON"]}
