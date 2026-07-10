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
  - TER (Total Expense Ratio) disclosure (2026-07-09 — SBI/ABSL/Edelweiss/
    HDFC all publish a Regular-Plan-vs-Direct-Plan table, one row per scheme
    per date; header depth/labels vary but every layout shares one invariant:
    a "Regular"-labelled column group and a "Direct"-labelled group, each
    ending in its own "Total TER (%)" column). Only the LATEST date's row per
    scheme is kept — TER changes over time and only the current effective
    rate should ever be written.
  - AMFI consolidated scheme-wise AAUM (2026-07-10 — the quarterly all-AMC
    workbook from the AMFI portal: one row per scheme carrying its AMFI CODE,
    which joins exactly on mf_funds.amfi_code — the one disclosure class that
    needs ZERO name resolution. Multi-AMC by design, so its file class
    ('amfi_aaum') is content-sniffed and bypasses AMC detection.)

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
    """'aaum' | 'amfi_aaum' | 'riskometer' | 'ter' | 'performance' |
    'scheme_master' | 'portfolio' (default) — pure.

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
    # AMFI's consolidated scheme-wise AAUM download has an arbitrary filename
    # ("average-aum2.xlsx" from the portal) that matches NO keyword below —
    # content is the only reliable signal, same reasoning as scheme_master.
    if data is not None and _looks_like_amfi_aaum(data):
        return "amfi_aaum"
    low = filename.lower()
    if "aaum" in low or "average asset" in low or "average_asset" in low or "average-asset" in low:
        return "aaum"
    if "riskometer" in low or "risk-o-meter" in low or "risk o meter" in low:
        return "riskometer"
    if (
        "expense ratio" in low
        or "expenseratio" in low
        or "_ter_" in low
        or "_ter." in low
        or re.search(r"\bter\b", low)
    ):
        # `_`/`-` are `\w` for `\b` purposes, so a bare word-boundary regex
        # alone can't catch an underscore-delimited "_ter_"/"_ter." (e.g.
        # "HDFCMF_SCHEMES_TER_02-06-2026_1.xls") — those need the explicit
        # checks above. `\bter\b` then covers every hyphen/space-delimited
        # form (e.g. HSBC's real "...HSBC MF Total Exp Ter Report_
        # 06072026.xlsx", confirmed 2026-07-09) in one pattern instead of
        # enumerating every separator combination — never matches inside a
        # real word like "water"/"after".
        return "ter"
    if "performance" in low:
        return "performance"
    return "portfolio"


def _repair_corrupted_stylesheet_xlsx(data: bytes) -> bytes:
    """Patch a malformed `xl/styles.xml` `rgb="..."` color value in-place and
    return corrected xlsx bytes, unchanged if nothing needed fixing.

    Confirmed 2026-07-09 (Edelweiss's real "TotalExpenseRatio-2026-2027.xlsx"
    and its siblings): openpyxl raises `ValueError: Unable to read workbook:
    could not read stylesheet ... Colors must be aRGB hex values` because one
    `<color rgb="0000000"/>` element has a 7-character hex value — a genuinely
    truncated 8-char aRGB value (should be e.g. "00000000"), not a different
    color format. Zero-padding any `rgb="..."` value that is neither 6 nor 8
    hex characters (the only two valid lengths — plain RGB or aRGB) to 8
    chars recovers the file without altering any VALID color, and this is a
    zip-level, in-memory patch — never touches the on-disk stored original.
    """
    import zipfile

    with zipfile.ZipFile(io.BytesIO(data)) as zin:
        if "xl/styles.xml" not in zin.namelist():
            return data
        styles = zin.read("xl/styles.xml").decode("utf-8")

        def _pad(m: re.Match[str]) -> str:
            hexval = m.group(1)
            return m.group(0) if len(hexval) in (6, 8) else f'rgb="{hexval.zfill(8)}"'

        fixed = re.sub(r'rgb="([0-9A-Fa-f]+)"', _pad, styles)
        if fixed == styles:
            return data

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                content = (
                    fixed.encode("utf-8")
                    if item.filename == "xl/styles.xml"
                    else zin.read(item.filename)
                )
                zout.writestr(item, content)
        return buf.getvalue()


def _iter_sheets(data: bytes, ext: str) -> Iterator[tuple[str, list[list[Any]]]]:
    """Yield (sheet_name, rows-of-raw-values) — openpyxl for .xlsx, xlrd for
    legacy OLE2 .xls (xlrd>=2.0 reads ONLY .xls; already a dependency via the
    CAMS legacy parser). Raw values (not str) — AAUM needs the floats.

    The file EXTENSION is a hint, never trusted blindly both ways (confirmed
    2026-07-09, HDFC's own "...TER_02-06-2026_1.xls" — the opposite mismatch
    of the earlier SBI "Fund Details" HTML-saved-as-.xls case: this one is a
    genuine, valid XLSX zip that someone saved with a legacy ".xls"
    extension). If the extension-suggested reader fails with the SPECIFIC
    "wrong container format" error, retry with the other reader once before
    giving up — never guess data, just don't let a mislabeled extension mask
    a file that's perfectly readable under its real format.
    """
    import xlrd

    if ext == ".xls":
        try:
            book = xlrd.open_workbook(file_contents=data)
        except xlrd.XLRDError as exc:
            if "not supported" not in str(exc):
                raise
            yield from _iter_sheets_xlsx(data)
            return
        for sheet in book.sheets():
            rows = [
                [sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)
            ]
            yield sheet.name, rows
    else:
        import zipfile

        try:
            yield from _iter_sheets_xlsx(data)
        except zipfile.BadZipFile:
            book = xlrd.open_workbook(file_contents=data)
            for sheet in book.sheets():
                rows = [
                    [sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)
                ]
                yield sheet.name, rows


def _iter_sheets_xlsx(data: bytes) -> Iterator[tuple[str, list[list[Any]]]]:
    """The .xlsx branch of `_iter_sheets`, split out so it can be retried with
    repaired bytes on a stylesheet-corruption ValueError without duplicating
    the openpyxl-open-and-iterate logic."""
    import openpyxl

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except ValueError as exc:
        if "could not read stylesheet" not in str(exc):
            raise
        repaired = _repair_corrupted_stylesheet_xlsx(data)
        wb = openpyxl.load_workbook(io.BytesIO(repaired), read_only=True, data_only=True)
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


def _looks_like_amfi_aaum(data: bytes) -> bool:
    """CONTENT sniff for the AMFI consolidated scheme-wise AAUM workbook:
    a header row carrying BOTH 'AMFI Code' and 'Scheme NAV Name' plus an
    'Average Assets' title within the first few rows. xlsx-only (the portal
    serves xlsx; the check needs to open the zip) — anything unreadable is
    simply not this class, never an error.
    """
    if not data.startswith(b"PK\x03\x04"):
        return False
    import openpyxl

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        try:
            ws = wb[wb.sheetnames[0]]
            head: list[str] = []
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= 6:
                    break
                head.extend(_s(c).lower() for c in row if c is not None)
        finally:
            wb.close()
    except Exception:  # noqa: BLE001 — a sniff must never break classification
        return False
    return (
        any("average assets" in c for c in head)
        and any(c == "amfi code" for c in head)
        and any("scheme nav name" in c for c in head)
    )


_MONTH_NUMBERS = {
    name: num
    for num, name in enumerate(
        (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ),
        start=1,
    )
}
_AMFI_AAUM_QUARTER_RE = re.compile(
    r"quarter of\s+[a-z]+\s*[-–]\s*([a-z]+)\s+(\d{4})", re.IGNORECASE
)


def parse_amfi_aaum(data: bytes, ext: str) -> tuple[date | None, list[tuple[str, str, float]]]:
    """AMFI consolidated scheme-wise AAUM workbook →
    (period, [(amfi_code, scheme_name, aaum_crore)]).

    Layout (verified against the real portal download 2026-07-10 — 8,545
    scheme rows): r0 title "Average Assets under Management (AAUM) for the
    quarter of April - June 2026 (Rs in Lakhs)"; r1 header ['AMFI Code',
    'Scheme NAV Name', 'Excluding Fund of Funds - Domestic but including
    Fund of Funds - Overseas', 'Fund Of Funds - Domestic']; below that, AMC
    section rows and category section rows (single-cell, no numeric code)
    interleave with scheme rows (numeric AMFI code + name + a value in
    exactly ONE of the two value columns — verified: no scheme carries
    both). Scheme AAUM = sum of the value columns.

    Units MUST be stated in the title block: 'lakh' → /100, 'crore' → as-is;
    an unstated unit FAILS CLOSED (a silent crore default would 100×-inflate
    every fund if AMFI ever dropped the suffix). Period comes from the
    "quarter of <M1> - <M2> <year>" title as month-start of the quarter's
    END month (the as_of_month convention used everywhere else); the caller
    may fall back to the filename, and a period-less result must never
    invent one (§8.4).
    """
    for _name, rows in _iter_sheets(data, ext):
        header_idx = None
        code_ci = None
        name_ci = None
        val_cis: list[int] = []
        for idx, row in enumerate(rows[:8]):
            lows = [_s(c).lower() for c in row]
            if "amfi code" in lows and any("scheme nav name" in c for c in lows):
                header_idx = idx
                code_ci = lows.index("amfi code")
                name_ci = next(ci for ci, c in enumerate(lows) if "scheme nav name" in c)
                val_cis = [ci for ci, c in enumerate(lows) if c and ci not in (code_ci, name_ci)]
                break
        if header_idx is None or code_ci is None or name_ci is None or not val_cis:
            continue

        head_text = " ".join(_s(c) for row in rows[: header_idx + 1] for c in row).lower()
        if "average assets" not in head_text:
            continue
        if "lakh" in head_text:
            scale = 0.01
        elif "crore" in head_text or "cr." in head_text:
            scale = 1.0
        else:
            continue  # unstated units → fail closed, never guess a 100× factor

        period: date | None = None
        m = _AMFI_AAUM_QUARTER_RE.search(head_text)
        if m:
            month = _MONTH_NUMBERS.get(m.group(1).lower())
            if month:
                try:
                    period = date(int(m.group(2)), month, 1)
                except ValueError:
                    period = None

        out: list[tuple[str, str, float]] = []
        for row in rows[header_idx + 1 :]:
            if code_ci >= len(row) or name_ci >= len(row):
                continue
            code = _s(row[code_ci])
            if code.endswith(".0"):
                code = code[:-2]  # xlrd renders integer cells as floats
            if not code.isdigit():
                continue  # AMC / category section rows carry no numeric code
            name = _s(row[name_ci])
            if not name:
                continue
            total = 0.0
            seen = False
            for ci in val_cis:
                if ci >= len(row):
                    continue
                v = row[ci]
                if isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)):
                    total += float(v)
                    seen = True
                elif isinstance(v, str):
                    try:
                        total += float(v.replace(",", ""))
                        seen = True
                    except ValueError:
                        pass
            if not seen or total <= 0:
                continue  # a scheme with no/zero AAUM is skipped, never written as 0
            out.append((code, name, round(total * scale, 4)))
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

    Handles THREE real layouts (2026-07-07/08):
      - SBI: one sheet per scheme; a 'SCHEME NAME :' label row (name in the
        next non-empty cell) + an explicit 'Scheme Benchmark: <name>' cell.
      - ICICI: repeating blocks in one sheet; block header = the scheme name
        repeated across >=2 cells, then a 'Scheme' particulars row, then the
        benchmark row whose first cell is '<index name> (Benchmark)'.
      - Kotak: a plain table — one header row literally naming its own
        columns ("Scheme name" / "Benchmark Name (Tier 1)"), one scheme per
        row after that. Found inside Kotak's OWN "riskometer" disclosure
        file (its risk-o-meter LEVEL column is genuinely blank in every row —
        a change-COUNT disclosure, not a current-level one — but the same
        file carries this usable benchmark table instead); the caller tries
        this parser on any `riskometer`-classified file too, not only ones
        named/classified `performance`.
    Additional benchmarks ('Additional Benchmark: ...') are deliberately
    ignored — `benchmark_index` holds the scheme's PRIMARY benchmark.
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    for _name, rows in _iter_sheets(data, ext):
        sheet_scheme: str | None = None
        block_scheme: str | None = None
        after_scheme_row = False
        table_name_ci: int | None = None
        table_bench_ci: int | None = None

        for row in rows:
            cells = [_s(c) for c in row]
            non_empty = [c for c in cells if c]
            if not non_empty:
                continue

            # Kotak-style plain table: a header row literally naming its own
            # columns. Once found, every later row in THIS sheet is read by
            # column position directly — this shape never satisfies the
            # SBI/ICICI heuristics below, so skip straight past them.
            if table_name_ci is None:
                low_cells = [c.lower() for c in cells]
                name_hits = [ci for ci, c in enumerate(low_cells) if "scheme name" in c]
                bench_hits = [ci for ci, c in enumerate(low_cells) if "benchmark name" in c]
                if name_hits and bench_hits:
                    table_name_ci, table_bench_ci = name_hits[0], bench_hits[0]
                    continue
            if table_name_ci is not None and table_bench_ci is not None:
                if table_name_ci < len(cells) and table_bench_ci < len(cells):
                    # Strip a trailing footnote marker ("Kotak Active Momentum
                    # Fund^") — Kotak (and several AMCs) mark ~1 in 7 scheme
                    # names this way in this exact table; never touches a real
                    # scheme name, which always ends alphanumeric.
                    name = cells[table_name_ci].rstrip("^*#†‡ ")
                    bench = cells[table_bench_ci]
                    if name and bench and name not in seen:
                        out.append((name, bench))
                        seen.add(name)
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


def _parse_ter_date(v: Any) -> date | None:
    """A TER-date cell is either a real `datetime` (openpyxl auto-converts a
    genuine Excel date cell) or a string in one of the two conventions AMCs
    actually use in these files (DD-MON-YYYY / DD/MM/YYYY — Indian date
    order, never US MM/DD)."""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = _s(v)
    if not s:
        return None
    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_ter_number(v: Any) -> float | None:
    """A TER percentage cell can be a real float/int OR a numeric-looking
    string (confirmed 2026-07-09, Edelweiss: every value cell is text like
    "0.0000", not a genuine number) — accept either, never guess on anything
    else."""
    if isinstance(v, (int, float)):
        return float(v)
    s = _s(v)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_ter_disclosure(data: bytes, ext: str) -> list[tuple[str, date, float, float]]:
    """Total Expense Ratio (TER) disclosure -> [(scheme_name, ter_date,
    regular_total_ter_pct, direct_total_ter_pct)], ONE row per scheme (the
    LATEST date only — TER changes over time and only the current effective
    rate should ever be written).

    Confirmed 2026-07-09 across 3 real AMC layouts (SBI, ABSL, Edelweiss) that
    all share one structural invariant despite differing header shapes: a
    "Regular"-labelled column GROUP and a "Direct"-labelled column group
    (Regular always precedes Direct left-to-right), each ending in its own
    "Total TER (%)" sub-column — the all-in number; the BER/brokerage/
    transaction-cost/GST components that precede it are deliberately NOT
    extracted (§8.4 verbatim-only — we want the one number the AMC itself
    calls the total, never a recomputation). Header depth varies (SBI: one
    row, every column literally prefixed "Regular Plan - " / "Direct Plan -";
    Edelweiss: a group-title row ["Regular Plan", "Direct Plan"] followed by
    a shared 5-label sub-header row; ABSL: the same 2-row shape with bare
    "Regular"/"Direct" group titles) — detected generically by locating the
    "regular"/"direct" group-start columns and every "total ter" column,
    rather than hardcoding 3 separate branches.

    A scheme's holdings are IDENTICAL across Regular and Direct plans (TER is
    a plan-level, not option-level, fee) — the resolver in manual_ingest.py
    applies these two values to ALL option-variant ISINs (Growth/IDCW/Bonus/
    etc.) under each plan, never a single top-1 fuzzy match.
    """
    latest: dict[str, tuple[date, float, float]] = {}

    for _name, rows in _iter_sheets(data, ext):
        header_rows = rows[:4]
        has_regular = False
        has_direct = False
        name_ci: int | None = None
        date_ci: int | None = None
        total_ter_cols: list[int] = []
        header_end = 0

        for ri, hr in enumerate(header_rows):
            non_empty_count = sum(1 for c in hr if _s(c))
            row_has_total_ter = False
            for ci, cell in enumerate(hr):
                s = _s(cell).lower()
                if not s:
                    continue
                if "regular" in s:
                    has_regular = True
                if "direct" in s:
                    has_direct = True
                if "name" in s and name_ci is None:
                    name_ci = ci
                if "date" in s and date_ci is None:
                    date_ci = ci
                # A free-text title banner ("Total Expense Ratio (TER) for
                # Mutual Fund Schemes") can spell out both "total" and "ter"
                # in prose — confirmed 2026-07-09, HDFC's TER file — and is
                # never a real multi-column header row (always <=2 non-empty
                # cells: either the single banner cell itself, or the
                # 2-cell "Regular Plan"/"Direct Plan" group-title row, which
                # never contains "total"/"ter" anyway). Require >2 non-empty
                # cells so only a genuine tabular header row can contribute.
                if non_empty_count > 2 and "total" in s and "ter" in s:
                    total_ter_cols.append(ci)
                    row_has_total_ter = True
            if row_has_total_ter:
                header_end = ri

        # Every real layout has EXACTLY one "Total TER" column per plan — the
        # group-TITLE cells ("Regular Plan" / "Direct Plan") are not reliably
        # positioned at the START of their own column block (confirmed
        # 2026-07-09, Edelweiss: title cells sit at columns 0/1 while the
        # actual Regular/Direct sub-column blocks are 2-6/7-11), so bucketing
        # by title-column proximity is unreliable. Left-to-right POSITION
        # order is: every real AMC lists the Regular block before the Direct
        # block, so with exactly 2 "Total TER" columns the smaller index is
        # always Regular's and the larger is always Direct's — simpler and
        # correct across all 3 known layouts (SBI/ABSL/Edelweiss). More or
        # fewer than 2 is an unrecognized layout — skip the sheet, never
        # guess which column is which.
        if (
            not has_regular
            or not has_direct
            or name_ci is None
            or date_ci is None
            or len(total_ter_cols) != 2
        ):
            continue

        regular_total_ci, direct_total_ci = sorted(total_ter_cols)

        for row in rows[header_end + 1 :]:
            if max(name_ci, date_ci, regular_total_ci, direct_total_ci) >= len(row):
                continue
            name = _s(row[name_ci])
            if not name:
                continue
            ter_date = _parse_ter_date(row[date_ci])
            reg_val = _parse_ter_number(row[regular_total_ci])
            dir_val = _parse_ter_number(row[direct_total_ci])
            if ter_date is None or reg_val is None or dir_val is None:
                continue
            prior = latest.get(name)
            if prior is None or ter_date > prior[0]:
                latest[name] = (ter_date, round(float(reg_val), 4), round(float(dir_val), 4))

    return [(name, d, reg, dirv) for name, (d, reg, dirv) in latest.items()]


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
    return _scheme_master_from_flat(_flatten_html(data))


def _flatten_pdf(data: bytes) -> str:
    """pypdf text extraction across all pages, whitespace-normalized into the
    same flat "Label Value Label Value" stream `_extract_all_labels` slices.
    pypdf is already a declared dependency (NIPPON factsheet parser)."""
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    text = " ".join(page.extract_text() or "" for page in reader.pages)
    return re.sub(r"\s+", " ", text).strip()


def looks_like_scheme_master_pdf(data: bytes) -> bool:
    """Content sniff for SBI's per-scheme "Fund Details" PDF (2026-07-10:
    the founder's 52 SBI uploads are this page rendered to PDF — they sat
    'archived' while carrying CURRENT riskometer/TER/benchmark/manager/exit
    load). First page only — cheap enough for the intake dispatch path."""
    if not data.startswith(b"%PDF"):
        return False
    try:
        import io

        from pypdf import PdfReader

        first = PdfReader(io.BytesIO(data)).pages[0].extract_text() or ""
    except Exception:  # noqa: BLE001 — a corrupt PDF is simply not this class
        return False
    return "fund details for" in first.lower()


def parse_scheme_master_pdf(data: bytes) -> dict[str, Any]:
    """PDF twin of `parse_scheme_master_details` — same labels, same output
    dict (the AMC renders the same Fund-Details page to both HTML and PDF).
    Fail-closed {} when no Fund Name is found."""
    try:
        flat = _flatten_pdf(data)
    except Exception:  # noqa: BLE001 — unreadable PDF → unsupported, never a guess
        return {}
    return _scheme_master_from_flat(flat)


def _scheme_master_from_flat(flat: str) -> dict[str, Any]:
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

    exit_load_pct, exit_load_days = _parse_exit_load_text(labels.get("Exit Load", ""))

    return {
        "scheme_name": scheme_name,
        "risk_band": risk_band,
        "benchmark_tier1": benchmark,
        "ter_pct": ter_pct,
        "manager_pairs": manager_pairs,
        "exit_load_pct": exit_load_pct,
        "exit_load_days": exit_load_days,
    }


_EXIT_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_EXIT_PERIOD_RES = (
    (re.compile(r"(\d+)\s*day", re.IGNORECASE), 1),
    (re.compile(r"(\d+)\s*month", re.IGNORECASE), 30),
    (re.compile(r"(\d+)\s*year", re.IGNORECASE), 365),
)


def _parse_exit_load_text(text: str) -> tuple[float | None, int | None]:
    """Exit-load prose → (pct, days) — fail-closed (None, None) when unstated.

    Real SBI Fund-Details form (2026-07-10): "For exit within 30 days from
    the date of allotment - 1%. For exit after 30 days - Nil." → (1.0, 30).
    A bare "Nil"/"NIL" is a REAL fact (no exit load) → (0.0, None). The pct
    is the FIRST percentage stated (the binding near-term tier); days is the
    longest period mentioned. Historically this label was deliberately
    skipped; extracting it now (founder-directed, 2026-07-10) because the
    BSE StAR source stays dormant until prod creds."""
    cleaned = text.strip()
    if not cleaned:
        return None, None
    m = _EXIT_PCT_RE.search(cleaned)
    if m is None:
        if re.fullmatch(r"nil\.?", cleaned, re.IGNORECASE):
            return 0.0, None
        return None, None
    try:
        pct = float(m.group(1))
    except ValueError:
        return None, None
    if not 0 <= pct <= 20:
        return None, None
    periods = [
        int(pm.group(1)) * mult
        for pattern, mult in _EXIT_PERIOD_RES
        for pm in pattern.finditer(cleaned)
        if 0 < int(pm.group(1)) * mult <= 3650
    ]
    return pct, (max(periods) if periods else None)
