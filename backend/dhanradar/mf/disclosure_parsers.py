"""
DhanRadar — pure parsers for NON-portfolio disclosure file classes arriving
through the manual-ingest inbox (2026-07-07, built against the founder's real
first-batch files):

  - AAUM annexure  (SEBI "Annexure I/A1" monthly Average-AUM disclosure —
    per-scheme AAUM ₹Cr; AXIS/EDEL publish .xlsx, SBI/HDFC legacy .xls)
  - Annual riskometer disclosure (ICICI publishes a clean 1-sheet .xlsx:
    scheme · start-FY band · end-FY band · change count)
  - Scheme performance disclosure (two real layouts: ICICI = repeating blocks
    in one sheet, benchmark row follows the "Scheme" row; SBI = one sheet per
    scheme, explicit "SCHEME NAME :" and "Scheme Benchmark: <name>" cells) —
    parsed ONLY for the per-scheme BENCHMARK NAME (the `mf_funds.benchmark_index`
    unblock, plan §11); returns are NOT extracted (we compute our own from NAV).
  - Scheme master details (2026-07-08 — SBI's per-scheme "Fund Details" page
    from their own website, saved with a misleading `.xls` extension: it's
    plain HTML, not a spreadsheet at all. Confirmed identical label/value
    TEMPLATE across every real sample — riskometer band, primary benchmark
    name, fund-manager name(s) + tenure start, and the stated TER. Exit load
    is deliberately NOT extracted — free-form multi-tier text that would need
    lossy guessing to fit a single (pct, days) pair; a wrong compliance-
    adjacent fee figure is worse than none, per §8.4 verbatim-only.)

All parsers are PURE (bytes in, tuples out — no DB, no network) so they unit-
test without fixtures beyond in-memory workbooks. Writers live in
tasks/manual_ingest.py. Fail-closed everywhere: an unrecognizable layout
yields an empty result (the caller marks the file 'unsupported'), never a
guess. Values are taken VERBATIM from the file — riskometer bands validated
against the 6 regulatory words, AAUM never derived or imputed (ADR-0035).
"""

from __future__ import annotations

import html
import io
import logging
import re
from collections.abc import Iterator
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)

# The 6 SEBI riskometer bands — a parsed value must match one VERBATIM
# (case-insensitive) or the row is skipped; we never normalize into a band.
RISKOMETER_BANDS: tuple[str, ...] = (
    "Low",
    "Low to Moderate",
    "Moderate",
    "Moderately High",
    "High",
    "Very High",
)
_BANDS_LOWER = {b.lower(): b for b in RISKOMETER_BANDS}


def classify_file_class(filename: str, data: bytes | None = None) -> str:
    """'aaum' | 'riskometer' | 'performance' | 'scheme_master' | 'portfolio'
    (default) — pure.

    Keyed off the disclosure-type words AMCs put in their own filenames
    (verified against the founder's real batch: "Average_Assets_Under_
    Management", "Monthly AAUM_May 2026", "monthly-average-asset-under-
    management", "Annual Disclosure of Scheme Riskometer", "Scheme
    Performance Disclosure", "scheme-performance---may-2026").

    `data`, when provided, is CONTENT-sniffed first for `scheme_master` — SBI's
    "Fund Details" page (confirmed 2026-07-08) is saved with a normal
    per-scheme filename indistinguishable from a real portfolio disclosure
    (e.g. "SBI Multicap Fund.xls"), so filename keywords alone can't
    recognize it; content sniffing is the only reliable signal.
    """
    if data is not None and _looks_like_scheme_master_html(data):
        return "scheme_master"
    low = filename.lower()
    if "aaum" in low or "average asset" in low or "average_asset" in low or "average-asset" in low:
        return "aaum"
    if "riskometer" in low or "risk-o-meter" in low or "risk o meter" in low:
        return "riskometer"
    if "performance" in low:
        return "performance"
    return "portfolio"


def _iter_sheets(data: bytes, ext: str) -> Iterator[tuple[str, list[list[Any]]]]:
    """Yield (sheet_name, rows-of-raw-values) — openpyxl for .xlsx, xlrd for
    legacy OLE2 .xls (xlrd>=2.0 reads ONLY .xls; already a dependency via the
    CAMS legacy parser). Raw values (not str) — AAUM needs the floats."""
    if ext == ".xls":
        import xlrd

        book = xlrd.open_workbook(file_contents=data)
        for sheet in book.sheets():
            rows = [
                [sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)
            ]
            yield sheet.name, rows
    else:
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        try:
            for name in wb.sheetnames:
                yield name, [list(row) for row in wb[name].iter_rows(values_only=True)]
        finally:
            wb.close()


def _s(v: Any) -> str:
    return str(v).strip() if v is not None else ""


_AS_ON_RE = re.compile(r"as on\s+(\d{4})-(\d{2})-(\d{2})", re.IGNORECASE)


def parse_aaum_annexure(data: bytes, ext: str) -> tuple[date | None, list[tuple[str, float]]]:
    """SEBI AAUM annexure → (period, [(scheme_name, aaum_crore)]).

    Anchors on the standardized header pair: a 'Scheme Category/ Scheme Name'
    cell and a 'GRAND TOTAL' cell in the same row (verified identical across
    AXIS .xlsx and SBI .xls). Scheme rows = name in the scheme-name column +
    a positive number in the GRAND TOTAL column; SUB-TOTAL/TOTAL and category
    header rows carry no grand-total number or a 'total' name and are skipped.
    Values are ₹ Cr as published (AXIS LIQUID grand total 59,127.66 verified
    against the fund's real ~₹59k Cr AAUM); a header mentioning 'lakh' scales
    /100 — anything else unrecognized fails closed to an empty result.
    """
    for _name, rows in _iter_sheets(data, ext):
        header_idx = None
        name_ci = None
        total_ci = None
        for idx, row in enumerate(rows[:12]):
            cells = [_s(c) for c in row]
            for ci, cell in enumerate(cells):
                if cell.lower().startswith("scheme category"):
                    name_ci = ci
                if "grand total" in cell.lower():
                    total_ci = ci
            if name_ci is not None and total_ci is not None:
                header_idx = idx
                break
        if header_idx is None or name_ci is None or total_ci is None:
            continue  # not the annexure sheet — try the next one

        # Units: ₹ Cr unless the header block explicitly says lakhs.
        head_text = " ".join(_s(c) for row in rows[: header_idx + 1] for c in row).lower()
        scale = 0.01 if "lakh" in head_text else 1.0

        # Period: the header carries "as on YYYY-MM-DD" (AXIS verified);
        # the caller falls back to the filename when this is absent.
        period: date | None = None
        m = _AS_ON_RE.search(head_text)
        if m:
            try:
                period = date(int(m.group(1)), int(m.group(2)), 1)
            except ValueError:
                period = None

        out: list[tuple[str, float]] = []
        for row in rows[header_idx + 1 :]:
            if name_ci >= len(row) or total_ci >= len(row):
                continue
            name = _s(row[name_ci])
            value = row[total_ci]
            if not name or "total" in name.lower():
                continue
            if not isinstance(value, (int, float)) or value <= 0:
                continue  # category headers / blank rows have no grand total
            out.append((name, round(float(value) * scale, 2)))
        if out:
            return period, out
    return None, []


def parse_riskometer_annual(data: bytes, ext: str) -> list[tuple[str, str]]:
    """Annual riskometer disclosure → [(scheme_name, band)] using the LATEST
    'Risk-o-meter level as on <date>' column (files carry start-of-FY and
    end-of-FY columns; the last one is current). Bands validated VERBATIM
    against the 6 regulatory words — 'NA'/unknown rows skipped, never coerced.
    """
    for _name, rows in _iter_sheets(data, ext):
        header_idx = None
        name_ci = None
        band_ci = None
        for idx, row in enumerate(rows[:10]):
            cells = [_s(c).lower() for c in row]
            if any("scheme name" in c for c in cells) and any("risk-o-meter" in c for c in cells):
                header_idx = idx
                name_ci = next(ci for ci, c in enumerate(cells) if "scheme name" in c)
                band_cols = [ci for ci, c in enumerate(cells) if "risk-o-meter level" in c]
                band_ci = band_cols[-1] if band_cols else None
                break
        if header_idx is None or name_ci is None or band_ci is None:
            continue

        out: list[tuple[str, str]] = []
        for row in rows[header_idx + 1 :]:
            if name_ci >= len(row) or band_ci >= len(row):
                continue
            name = _s(row[name_ci])
            band_raw = _s(row[band_ci])
            band = _BANDS_LOWER.get(band_raw.lower())
            if name and band:
                out.append((name, band))
        if out:
            return out
    return []


_SBI_BENCH_RE = re.compile(r"^scheme benchmark\s*:\s*(.+)$", re.IGNORECASE)
_TRAILING_BENCH_RE = re.compile(r"\s*\(benchmark\)?\s*$", re.IGNORECASE)


def parse_scheme_performance(data: bytes, ext: str) -> list[tuple[str, str]]:
    """Scheme-performance disclosure → [(scheme_name, benchmark_name)].

    Handles both real layouts (2026-07-07):
      - SBI: one sheet per scheme; a 'SCHEME NAME :' label row (name in the
        next non-empty cell) + an explicit 'Scheme Benchmark: <name>' cell.
      - ICICI: repeating blocks in one sheet; block header = the scheme name
        repeated across >=2 cells, then a 'Scheme' particulars row, then the
        benchmark row whose first cell is '<index name> (Benchmark)'.
    Additional benchmarks ('Additional Benchmark: ...') are deliberately
    ignored — `benchmark_index` holds the scheme's PRIMARY benchmark.
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    for _name, rows in _iter_sheets(data, ext):
        sheet_scheme: str | None = None
        block_scheme: str | None = None
        after_scheme_row = False

        for row in rows:
            cells = [_s(c) for c in row]
            non_empty = [c for c in cells if c]
            if not non_empty:
                continue

            # SBI: "SCHEME NAME :" label — the scheme is the next non-empty cell.
            # The captured value must LOOK like a scheme name: the per-column
            # table header row also carries a literal 'Scheme Name' cell whose
            # neighbor is 'CAGR %' — without this guard it overwrites the real
            # scheme captured from the true label row above it.
            for ci, cell in enumerate(cells):
                if cell.upper().startswith("SCHEME NAME"):
                    rest = next((c for c in cells[ci + 1 :] if c), "")
                    if rest and any(kw in rest.lower() for kw in ("fund", "etf", "scheme", "plan")):
                        sheet_scheme = rest
                    break

            # SBI: explicit benchmark label anywhere in the row.
            for cell in non_empty:
                m = _SBI_BENCH_RE.match(cell)
                if m and sheet_scheme and sheet_scheme not in seen:
                    out.append((sheet_scheme, m.group(1).strip()))
                    seen.add(sheet_scheme)
                    break

            # ICICI: block header = same value repeated across >=2 cells — and it
            # must LOOK like a scheme name (repeated 'CAGR (%)' / 'Returns' header
            # rows otherwise satisfy the repetition check and steal the block).
            if len(non_empty) >= 2 and len(set(non_empty)) == 1:
                cand = non_empty[0]
                cand_low = cand.lower()
                if any(kw in cand_low for kw in ("fund", "etf", "scheme", "plan")) and not any(
                    kw in cand_low for kw in ("cagr", "return", "%")
                ):
                    block_scheme = cand
                    after_scheme_row = False
                continue

            first = cells[0] if cells else ""
            if first.lower() == "scheme":
                after_scheme_row = True
                continue
            if after_scheme_row and first and first.lower() not in ("particulars",):
                if block_scheme and block_scheme not in seen:
                    bench = _TRAILING_BENCH_RE.sub("", first).strip()
                    # A benchmark cell names an index — require an index-ish word
                    # (every real benchmark carries one), never a bare number.
                    if any(
                        kw in bench.lower()
                        for kw in ("index", "tri", "nifty", "sensex", "crisil", "bse")
                    ):
                        out.append((block_scheme, bench))
                        seen.add(block_scheme)
                after_scheme_row = False

    return out


# ---------------------------------------------------------------------------
# Scheme master details — SBI's per-scheme "Fund Details" HTML page
# (confirmed 2026-07-08, ~52 files — saved with a misleading ".xls"
# extension, plain HTML, not a spreadsheet at all).
# ---------------------------------------------------------------------------

# The AMC's OWN template schema — every real sample carries this identical
# label list in this identical order. This is a generic template shared by
# EVERY scheme (like RISKOMETER_BANDS' 6 fixed words), never a per-scheme
# lookup table: used only to find where one label's value ENDS (the position
# of whichever label comes next), not to hardcode any scheme's own data.
_FUND_DETAILS_LABELS: tuple[str, ...] = (
    "Fund Name",
    "Options Names",
    "Fund Type",
    "Riskometer At Launch",
    "Riskometer As on Date",
    "Category as per SEBI categorization Circular",
    "Potential Risk Class",
    "Description",
    "Stated Asset Allocation",
    "Face Value",
    "NFO Open Date",
    "NFO Close Date",
    "Allotment Date",
    "Reopen Date",
    "Maturity Date",
    "Benchmark(Tier 1)",
    "Benchmark(Tier 2)",
    "Fund Manager",
    "Fund Manager Type",
    "Fund Manager From Date",
    "Annual Expense (Stated Maximum)",
    "Exit Load",
    "Custodian",
    "Auditor",
    "Registrar",
    "RTA Code",
    "Swing Pricing",
    "Side-Pocketing",
    "Listing Details",
    "ISIN",
)

_TAG_RE = re.compile(r"<[^>]+>")
_MANAGER_DATE_RE = re.compile(r"((?:Mr|Ms|Mrs)\.?[^:]+?):\s*(\d{1,2}-[A-Za-z]{3}-\d{4})")


def _looks_like_scheme_master_html(data: bytes) -> bool:
    """Content sniff — the file's own filename looks like a normal per-scheme
    portfolio file (e.g. "SBI Multicap Fund.xls"), so only the BYTES reveal
    this is actually an AMC website page, not a spreadsheet."""
    head = data[:4000].decode("utf-8", errors="ignore").lower()
    return "<html" in head and "fund details for" in head


def _flatten_html(data: bytes) -> str:
    """Strip every tag to a single space (collapsing nested tables' cell
    values into the surrounding text stream) and unescape entities — turns
    the label/value table into one flat, whitespace-normalized string that
    `_value_after` can slice by label position."""
    text = data.decode("utf-8", errors="replace")
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_all_labels(flat_text: str) -> dict[str, str]:
    """ONE sequential pass through the known label order (each label
    searched for starting only AFTER the previous label's own match ends),
    extracting every label's value as the text up to the NEXT label found in
    sequence. Sequential, monotonically-advancing search means an EARLIER
    label's name reappearing INSIDE a LATER value can never be mistaken for
    a boundary (confirmed 2026-07-08: a co-manager designation "(Co-Fund
    Manager)" literally contains the substring "Fund Manager", which a
    whole-list re-scan from position 0 wrongly matched as the next section
    start, truncating "Fund Manager From Date"'s real value)."""
    positions: list[tuple[str, int]] = []
    search_from = 0
    for label in _FUND_DETAILS_LABELS:
        idx = flat_text.find(label, search_from)
        if idx < 0:
            continue
        positions.append((label, idx))
        search_from = idx + len(label)

    values: dict[str, str] = {}
    for i, (label, idx) in enumerate(positions):
        start = idx + len(label)
        end = positions[i + 1][1] if i + 1 < len(positions) else len(flat_text)
        values[label] = flat_text[start:end].strip(" :")
    return values


def parse_scheme_master_details(data: bytes) -> dict[str, Any]:
    """SBI's per-scheme "Fund Details" page → one dict (ONE file = ONE
    scheme). Returns {} if the file doesn't even carry a Fund Name (fail-
    closed — caller marks 'unsupported', never guesses).

    Keys (any may be absent/None if the file omits a label):
      scheme_name: str
      risk_band: str | None — validated VERBATIM against the 6 regulatory
        words (RISKOMETER_BANDS), same rule as the dedicated riskometer parser.
      benchmark_tier1: str | None — the scheme's PRIMARY benchmark name.
      ter_pct: float | None — "Annual Expense (Stated Maximum)"'s number.
      manager_pairs: list[tuple[str, date]] — (manager_name, tenure start),
        parsed from "Fund Manager From Date"'s own "Name:DD-Mon-YYYY" pairs
        (NOT the separate "Fund Manager" list — that field has no per-name
        date, so pairing off this field is the only way to attribute the
        right start date to the right manager when a scheme has more than one).

    Exit load is deliberately NOT extracted (see module docstring).
    """
    flat = _flatten_html(data)
    labels = _extract_all_labels(flat)

    scheme_name = labels.get("Fund Name", "")
    if not scheme_name:
        return {}

    risk_raw = labels.get("Riskometer As on Date", "")
    risk_band = _BANDS_LOWER.get(risk_raw.strip().lower())

    benchmark_raw = labels.get("Benchmark(Tier 1)", "").strip()
    benchmark: str | None = (
        benchmark_raw if benchmark_raw.upper() not in ("", "NA", "N/A", "-") else None
    )

    expense_raw = labels.get("Annual Expense (Stated Maximum)", "")
    ter_pct: float | None = None
    ter_m = re.search(r"(\d+(?:\.\d+)?)", expense_raw)
    if ter_m:
        try:
            ter_pct = float(ter_m.group(1))
        except ValueError:
            ter_pct = None

    since_raw = labels.get("Fund Manager From Date", "")
    manager_pairs: list[tuple[str, date]] = []
    for name_part, date_str in _MANAGER_DATE_RE.findall(since_raw):
        try:
            manager_pairs.append(
                (name_part.strip(), datetime.strptime(date_str, "%d-%b-%Y").date())
            )
        except ValueError:
            continue

    return {
        "scheme_name": scheme_name,
        "risk_band": risk_band,
        "benchmark_tier1": benchmark,
        "ter_pct": ter_pct,
        "manager_pairs": manager_pairs,
    }
