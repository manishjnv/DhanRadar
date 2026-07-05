"""
DhanRadar — AMFI monthly category-wise fund flows parser.

Source (Phase A verified 2026-07-05): AMFI's "AMFI Data" page
(research-information/amfi-data → "AMFI Monthly Data") lists a predictable
monthly report URL:

    https://portal.amfiindia.com/spages/am{mon}{yyyy}repo.xls

e.g. ammay2026repo.xls (3-letter lowercase month). History goes back to
FY1999-2000. Same lightly-protected portal.amfiindia.com domain as NAVAll.

NOTE: the originally-guessed source `/otherdata/industry-data-analysis` was a
dead end — that page's 4 cards (Industry Trends, Folio & Ticket Size, AUM by
geography, per-capita AUM/GDP) are NOT category-wise flows and have no
downloadable content. This module's source is the real one.

File layout (legacy .xls, 2 sheets — "MCR_MonthlyReport" is the one we want;
"NSR" is New Scheme Reporting / NFO data and is not parsed here):
    row 0: blank
    row 1: title ("Monthly Report for the month of May 2026 ")
    row 2: header (Sr | Scheme Name | No. of Schemes | No. of Folios |
           Funds Mobilized (INR cr) | Repurchase/Redemption (INR cr) |
           Net Inflow(+ve)/Outflow(-ve) (INR cr) | Net AUM | Average AUM |
           No. of segregated portfolios | Net Assets in segregated portfolio)
    row 3+: hierarchical rows —
        'A' / blank-numbered rows = supergroup headers (e.g. "Open ended
            Schemes") — no numeric data, SKIP.
        'I', 'II', ... (uppercase roman) = category-group headers (e.g.
            "Income/Debt Oriented Schemes", "Growth/Equity Oriented
            Schemes") — no numeric data, SKIP.
        'i', 'ii', ... (lowercase roman) = the actual leaf SEBI scheme
            categories (Overnight Fund, Liquid Fund, ... Multi/Large/Mid/
            Small Cap Fund, etc.) — THESE are the rows we want.
        'Sub Total - ...' rows = aggregate rollups, SKIP (never double-count).
        blank rows = separators, SKIP.

Pure module: `parse_category_flow_rows` takes already-extracted (xlrd)
row-value tuples — no I/O, no DB — so it is unit-testable with plain Python
tuples mirroring the real layout above. `fetch_category_flows` is the thin
I/O wrapper (httpx GET + xlrd parse) used by the ingestion task.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date

import httpx

from dhanradar.market_data.exceptions import ProviderError

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Lowercase-roman-numeral leaf rows (i, ii, iii, ... up to xx — generous upper
# bound; AMFI's category list has never exceeded ~20 leaf rows per supergroup).
_LOWERCASE_ROMAN_RE = re.compile(r"^(x{0,3})(ix|iv|v?i{0,3})$")
_SUB_TOTAL_RE = re.compile(r"^\s*sub\s*total\b", re.IGNORECASE)


@dataclass(frozen=True)
class CategoryFlowRow:
    """One parsed row: a SEBI scheme category's monthly mobilisation/flow figures."""

    period_month: date  # first-of-month
    scheme_category: str
    num_schemes: int | None
    num_folios: int | None
    funds_mobilized_cr: float | None
    redemption_cr: float | None
    net_flow_cr: float | None
    net_aum_cr: float | None
    avg_aum_cr: float | None


def _is_leaf_roman(sr: object) -> bool:
    """True if the Sr column value is a lowercase roman numeral (leaf category row)."""
    if not isinstance(sr, str):
        return False
    token = sr.strip()
    if not token or token.isupper():
        return False
    return bool(_LOWERCASE_ROMAN_RE.fullmatch(token))


def _num(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _int(value: object) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)
    return None


def parse_category_flow_rows(rows: list[tuple], *, period_month: date) -> list[CategoryFlowRow]:
    """PURE parser — takes already-extracted (xlrd) row-value tuples.

    Only keeps rows whose Sr column is a lowercase roman numeral (the leaf
    SEBI scheme category rows); skips supergroup headers, Sub Total rollups,
    and blank separator rows so category-level figures are never double-counted.
    Column order (0-indexed): 0=Sr, 1=Scheme Name, 2=No. of Schemes,
    3=No. of Folios, 4=Funds Mobilized, 5=Repurchase/Redemption,
    6=Net Inflow/Outflow, 7=Net AUM, 8=Average AUM, 9=segregated count,
    10=segregated net assets.
    """
    out: list[CategoryFlowRow] = []
    for row in rows:
        if not row or len(row) < 9:
            continue
        sr = row[0]
        name = row[1]
        if _SUB_TOTAL_RE.match(name) if isinstance(name, str) else False:
            continue
        if not _is_leaf_roman(sr):
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        out.append(
            CategoryFlowRow(
                period_month=period_month,
                scheme_category=name.strip(),
                num_schemes=_int(row[2]),
                num_folios=_int(row[3]),
                funds_mobilized_cr=_num(row[4]),
                redemption_cr=_num(row[5]),
                net_flow_cr=_num(row[6]),
                net_aum_cr=_num(row[7]),
                avg_aum_cr=_num(row[8]),
            )
        )
    return out


def candidate_months(today: date) -> list[date]:
    """Most-recent-first candidate report months to try (last full month, then
    the one before). AMFI publishes month M's report with roughly a 1-month
    lag, so the just-closed month may not be up yet."""
    candidates: list[date] = []
    year, month = today.year, today.month
    for _ in range(3):
        month -= 1
        if month == 0:
            month = 12
            year -= 1
        candidates.append(date(year, month, 1))
    return candidates


def build_url(period_month: date) -> str:
    """Predictable AMFI URL for a report month."""
    mon = period_month.strftime("%b").lower()
    return f"https://portal.amfiindia.com/spages/am{mon}{period_month.year}repo.xls"


async def fetch_category_flows(
    client: httpx.AsyncClient | None, today: date | None = None
) -> tuple[list[CategoryFlowRow], date, str]:
    """Fetch + parse the most-recent resolvable monthly category-flows report.

    Returns (rows, period_month, source_url). Raises ProviderError if no
    candidate month resolves (never guesses/fabricates data).
    """
    import xlrd

    today = today or date.today()
    headers = {"User-Agent": _USER_AGENT}

    for period_month in candidate_months(today):
        url = build_url(period_month)
        try:
            if client is not None:
                resp = await client.get(url, headers=headers, timeout=_TIMEOUT)
            else:
                async with httpx.AsyncClient() as new_client:
                    resp = await new_client.get(url, headers=headers, timeout=_TIMEOUT)
        except httpx.HTTPError as exc:
            logger.warning("fetch_category_flows: %s network error: %s", url, exc)
            continue

        if resp.status_code != 200:
            logger.debug(
                "fetch_category_flows: %s returned HTTP %s, trying earlier month",
                url,
                resp.status_code,
            )
            continue

        try:
            wb = xlrd.open_workbook(file_contents=resp.content)
            ws = wb.sheet_by_name("MCR_MonthlyReport")
            raw_rows = [ws.row_values(r) for r in range(ws.nrows)]
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch_category_flows: %s unparseable: %s", url, exc)
            continue

        # Data rows start after the blank row (0) and title (1) and header (2).
        data_rows = [tuple(r) for r in raw_rows[3:]]
        parsed = parse_category_flow_rows(data_rows, period_month=period_month)
        if not parsed:
            logger.warning("fetch_category_flows: %s returned 0 parseable rows", url)
            continue
        return parsed, period_month, url

    raise ProviderError(
        "fetch_category_flows: no candidate month resolved "
        f"(tried {[build_url(p) for p in candidate_months(today)]})"
    )
