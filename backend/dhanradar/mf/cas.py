"""
DhanRadar — CAS parsing service (architecture Tier-C MF Module, Phase 5).

Wraps `casparser.read_cas_pdf(path, password)` and normalizes its output into a
flat list of `ParsedHolding`. CAMS + KFintech only — NSDL/CDSL equity CAS is NOT
supported (anti-pattern guard); a non-MF CAS yields no MF schemes.

`casparser` is an optional runtime dependency (installed in the worker image). It
is injected via `reader=` so this module is unit-testable without the library or
a real PDF; production passes the real `casparser.read_cas_pdf`.

Transaction amounts are normalized from STATEMENT convention (casparser output,
where amount sign follows units sign) to INVESTOR convention (outflows negative,
inflows positive) inside `parse_cas`. All downstream consumers — `ParsedTxn`,
`snapshot.xirr()` — expect INVESTOR convention. See B65.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)

# A reader takes (path, password) and returns the casparser output — a dict
# (casparser 0.7.x) or a CASData pydantic model (>=1.0); parse_cas normalises both.
CasReader = Callable[[str, str | None], Any]


# ---------------------------------------------------------------------------
# Transaction sign normalization (B65) — statement → investor convention
# ---------------------------------------------------------------------------
# casparser emits CAMS/KFintech detailed-CAS transactions in STATEMENT
# convention: the amount sign follows the units sign (purchases positive,
# redemptions negative — casparser cross-checks signs against the running
# unit-balance column). ParsedTxn and snapshot.xirr() require INVESTOR
# convention: outflows from the investor's pocket negative, inflows positive.
# Without this normalization an all-purchase portfolio yields only positive
# cash flows → xirr() all-same-sign guard → XIRR null (B65).
#
#   negate (statement sign follows units; money to/from the fund):
#     PURCHASE, PURCHASE_SIP, SWITCH_IN(_MERGER), REDEMPTION,
#     SWITCH_OUT(_MERGER), REVERSAL (reversal pairs then self-cancel)
#   keep as printed (cash credited to the investor):
#     DIVIDEND_PAYOUT
#   excluded from cash flows (no external cash movement, or immaterial
#   charges that double-count against gross purchase rows):
#     DIVIDEND_REINVEST, SEGREGATION, STT_TAX, STAMP_DUTY_TAX, TDS_TAX,
#     MISC, UNKNOWN
_TXN_INFLOW_AS_PRINTED = frozenset({"DIVIDEND_PAYOUT"})
# Unit-affecting but NO external cashflow — recorded in the ledger with amount=0 (their UNITS matter
# for the holdings projection, B3): dividend_reinvest adds the reinvested units. Amount 0 is B65-neutral
# (XIRR ignores it) so the cashflow/report path is unchanged.
_TXN_UNIT_ONLY = frozenset({"DIVIDEND_REINVEST"})
# Fully excluded — no units AND no external cashflow (immaterial charges / noise).
_TXN_FLOW_EXCLUDED = frozenset(
    {"SEGREGATION", "STT_TAX", "STAMP_DUTY_TAX", "TDS_TAX", "MISC", "UNKNOWN"}
)

#: casparser txn type → canonical ledger txn_type (plan §11 vocab). Only the cashflow types B2 ingests
#: are mapped; the _TXN_FLOW_EXCLUDED types (dividend_reinvest/tax/misc) are not yet written to the
#: ledger. An unmapped type falls back to its lowercased name (honest, not dropped).
_CANON_TXN_TYPE = {
    "PURCHASE": "purchase",
    "PURCHASE_SIP": "sip",
    "REDEMPTION": "redemption",
    "SWITCH_IN": "switch_in",
    "SWITCH_IN_MERGER": "switch_in",
    "SWITCH_OUT": "switch_out",
    "SWITCH_OUT_MERGER": "switch_out",
    "DIVIDEND_PAYOUT": "dividend_payout",
    "DIVIDEND_REINVEST": "dividend_reinvest",
    "REVERSAL": "reversal",
}

#: Bump when the CAS parse/normalization changes — stamped on every ledger row for I11 replay (B82).
PARSER_VERSION = "cas-1"


class CasParseError(Exception):
    """The CAS could not be parsed (bad password, corrupt, or unsupported format)."""


@dataclass(frozen=True)
class ParsedTxn:
    when: date
    amount: float  # signed INVESTOR convention: outflows negative, inflows positive (normalized in parse_cas, B65)
    is_sip: bool = False
    # B2 ledger fields — defaulted for back-compat (parse_cas always sets them):
    txn_type: str = ""  # canonical ledger txn_type (purchase/sip/redemption/switch_in/switch_out/dividend_payout/reversal)
    units: float = 0.0  # signed by direction (purchase +, redemption -) — casparser convention, kept as-is
    nav: float | None = None  # per-txn NAV → nav_or_price on the ledger


@dataclass(frozen=True)
class ParsedHolding:
    isin: str
    amfi_code: str | None
    scheme_name: str
    folio_number: str
    units: float
    nav: float | None
    value: float | None
    cost: float | None
    as_of_date: date | None
    txns: list[ParsedTxn]


def _default_reader(path: str, password: str | None) -> Any:  # pragma: no cover
    import casparser  # imported lazily; only present in the worker image

    return casparser.read_cas_pdf(path, password)


def _to_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def _clean_text(s: str) -> str:
    """Strip ASCII control characters from free-text PDF fields.

    casparser can emit raw control chars (e.g. U+0002 STX) inside scheme names,
    which render as replacement-box glyphs in the UI.  This helper replaces any
    control character with a space, collapses double-spaces, and strips leading/
    trailing whitespace.  Legitimate punctuation (hyphens, slashes, parentheses,
    etc.) is untouched.  Returns the original value unchanged when falsy.
    """
    if not s:
        return s
    return _CTRL.sub(" ", s).replace("  ", " ").strip()


def parse_cas(
    path: str,
    password: str | None,
    *,
    reader: CasReader | None = None,
) -> list[ParsedHolding]:
    """Parse a CAMS/KFintech CAS PDF into normalized holdings.

    Walks `folios[].schemes[]`, keeping only schemes that carry an ISIN (a stock
    CAS / non-MF row has none). Raises CasParseError on any reader failure (e.g.
    wrong password) — the caller marks the job failed and purges the file."""
    read = reader or _default_reader
    try:
        raw = read(path, password)
    except Exception as exc:  # noqa: BLE001 - any reader failure is a parse failure
        # Preserve the underlying casparser exception CLASS (e.g.
        # IncorrectPasswordError / HeaderParseError / ParserException) so server
        # logs name the failure mode. NEVER include the exception MESSAGE for a
        # password failure: a PDF backend can embed the attempted password (the
        # user's PAN — DPDP-sensitive) in it. The class name alone is the
        # diagnosis for the password case; other errors keep their PII-free text.
        name = type(exc).__name__
        safe_detail = "" if "Password" in name else f": {exc}"
        raise CasParseError(f"{name}{safe_detail}") from exc

    # casparser >= 1.0 returns a typed `CASData` pydantic MODEL for output="dict"
    # (0.7.x returned a plain dict). The walk below is dict-shaped
    # (`raw.get("folios")` …) and a pydantic model has no `.get()`, so without
    # this every successful parse would 500. The 1.0 model field names line up
    # 1:1 with the 0.7 dict keys, so model_dump() is a drop-in normalisation.
    if hasattr(raw, "model_dump"):
        raw = raw.model_dump(mode="python")

    holdings: list[ParsedHolding] = []
    excluded_txns = 0
    for folio in raw.get("folios", []) or []:
        folio_no = str(folio.get("folio") or "")
        for scheme in folio.get("schemes", []) or []:
            isin = (scheme.get("isin") or "").strip()
            if not isin:
                continue  # non-MF / unsupported row — skip (CAMS/KFintech MF only)
            valuation = scheme.get("valuation") or {}
            txns = []
            for t in scheme.get("transactions", []) or []:
                when = _to_date(t.get("date"))
                amt = t.get("amount")
                if when is None or amt is None:
                    continue
                ttype_raw = t.get("type")
                ttype = str(getattr(ttype_raw, "value", ttype_raw) or "").upper()
                if ttype in _TXN_FLOW_EXCLUDED:
                    excluded_txns += 1
                    continue
                if ttype in _TXN_UNIT_ONLY:
                    # Reinvested units, no external cash → amount 0 (XIRR-neutral); captured so the
                    # holdings projection's Σ units reaches the AMC close balance (B3 units parity).
                    txns.append(ParsedTxn(
                        when=when,
                        amount=0.0,
                        is_sip=False,
                        txn_type=_CANON_TXN_TYPE.get(ttype, ttype.lower()),
                        units=_opt_float(t.get("units")) or 0.0,
                        nav=_opt_float(t.get("nav")),
                    ))
                    continue
                amount = float(amt) if ttype in _TXN_INFLOW_AS_PRINTED else -float(amt)
                txns.append(ParsedTxn(
                    when=when,
                    amount=amount,
                    is_sip=(ttype == "PURCHASE_SIP"),
                    txn_type=_CANON_TXN_TYPE.get(ttype, ttype.lower()),
                    units=_opt_float(t.get("units")) or 0.0,
                    nav=_opt_float(t.get("nav")),
                ))
            holdings.append(
                ParsedHolding(
                    isin=isin,
                    amfi_code=(str(scheme["amfi"]) if scheme.get("amfi") else None),
                    scheme_name=_clean_text(str(scheme.get("scheme") or "")),
                    folio_number=folio_no,
                    units=float(scheme.get("close") or scheme.get("units") or 0.0),
                    nav=_opt_float(valuation.get("nav")),
                    value=_opt_float(valuation.get("value")),
                    cost=_opt_float(valuation.get("cost")),
                    as_of_date=_to_date(valuation.get("date")),
                    txns=txns,
                )
            )

    if excluded_txns:
        logger.info(
            "cas.parse: excluded %d non-cashflow txns (tax/reinvest/misc)", excluded_txns
        )

    # casparser 1.1.0 CDSL CAS: holdings are under accounts[].mutual_funds[]
    # (distinct from the folios[] structure used by CAMS/KFintech CAS).
    # CDSL MF entries have no transaction history → txns=[], xirr=None.
    # Only parse accounts that were not already covered by the folios walk above.
    if not holdings and raw.get("accounts"):
        for account in raw.get("accounts", []) or []:
            mf_list = account.get("mutual_funds", []) if isinstance(account, dict) else []
            if not isinstance(mf_list, list):
                continue
            for entry in mf_list:
                if not isinstance(entry, dict):
                    continue
                isin = (entry.get("isin") or "").strip()
                if not isin:
                    continue
                raw_name = str(entry.get("name") or "")
                # CDSL names embed "AMC_NAME#FUND_HOUSE#SCHEME_NAME" or
                # "AMC_NAME#FUND_HOUSE-SCHEME_NAME" prefixes.
                # Strategy: take everything after the LAST "#" when "#" is present,
                # which is consistently the scheme name portion in CDSL format.
                # Fall back to the full name when no "#" is present.
                if "#" in raw_name:
                    scheme_name = raw_name.rsplit("#", 1)[-1].strip()
                    # Strip a remaining "FUND_HOUSE-" prefix if present
                    # e.g. "AXIS MF-AXIS SMALL CAP FUND" → "AXIS SMALL CAP FUND"
                    if "-" in scheme_name:
                        parts = scheme_name.split("-", 1)
                        # Only strip if the prefix looks like a fund-house abbreviation
                        # (short, all-caps, no spaces or just one word)
                        prefix = parts[0].strip()
                        if len(prefix) <= 20 and " " not in prefix.replace("  ", ""):
                            scheme_name = parts[1].strip()
                else:
                    scheme_name = raw_name
                holdings.append(
                    ParsedHolding(
                        isin=isin,
                        amfi_code=(str(entry["amfi"]) if entry.get("amfi") else None),
                        scheme_name=_clean_text(scheme_name),
                        folio_number=str(entry.get("folio") or ""),
                        units=float(entry.get("balance") or entry.get("units") or 0.0),
                        nav=_opt_float(entry.get("nav")),
                        value=_opt_float(entry.get("value")),
                        cost=_opt_float(entry.get("total_cost")),
                        as_of_date=None,  # CDSL CAS has no per-holding date field
                        txns=[],  # CDSL CAS has no transaction history
                    )
                )

    return holdings


def _opt_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Ledger row construction (B2) — CAS holdings → canonical append-only ledger rows
# ---------------------------------------------------------------------------

_FOLIO_PLAN_SUFFIX = re.compile(r"\s*/\s*0+\s*$")


def normalize_folio(folio: str) -> str:
    """Canonical folio for ledger/holdings agreement (B82): trim whitespace and strip a trailing `/0`
    plan suffix CAMS appends (e.g. `12345/0` → `12345`). Conservative — only a slash-zeros tail is
    removed, never digits from the folio body."""
    if not folio:
        return ""
    return _FOLIO_PLAN_SUFFIX.sub("", folio.strip()).strip()


# ---------------------------------------------------------------------------
# CAMS Transaction Details Statement parsers (.txt / .xls / .xlsx)
#
# The "Transaction Details Statement" from camsonline.com is a separate product
# from the CAS PDF.  It contains full transaction history (Purchase/SIP/
# Redemption/Switch) but no ISIN codes.  The parser returns ParsedHolding
# objects where `isin` is a PLACEHOLDER of the form "CAMS:<product_code>" —
# the caller (tasks/mf.py _resolve_cams_txn_isins) is expected to resolve
# these to real ISINs via the mf_funds master before further processing.
#
# Supported formats:
#   .txt   — tab-separated (CAMS Text option)
#   .xls   — legacy Excel 97-2003 (CAMS Excel option, requires xlrd)
#   .xlsx  — modern Excel (requires openpyxl)
#
# Column contract (both formats, 14 columns):
#   MF_NAME, INVESTOR_NAME, PAN, FOLIO_NUMBER, PRODUCT_CODE, SCHEME_NAME,
#   Type, TRADE_DATE, TRANSACTION_TYPE, DIVIDEND_RATE, AMOUNT, UNITS, PRICE,
#   BROKER
# ---------------------------------------------------------------------------

# Map CAMS TRANSACTION_TYPE (normalised, uppercased) → (canonical_txn_type, b65_sign)
# b65_sign = -1 means negate (statement → investor convention), +1 means keep as-is.
_CAMS_TXN_MAP: dict[str, tuple[str, int]] = {
    "PURCHASE": ("purchase", -1),
    "SIP PURCHASE": ("sip", -1),
    "PURCHASE SIP": ("sip", -1),
    "ADDITIONAL PURCHASE": ("purchase", -1),
    "ADDITIONAL SIP PURCHASE": ("sip", -1),
    "SWITCH IN": ("switch_in", -1),
    "SWITCH IN (MERGER)": ("switch_in", -1),
    "REDEMPTION": ("redemption", -1),
    "REDEMPTION SIP": ("redemption", -1),
    "SWITCH OUT": ("switch_out", -1),
    "SWITCH OUT (MERGER)": ("switch_out", -1),
    "DIVIDEND PAYOUT": ("dividend_payout", 1),  # already investor-convention (positive inflow)
    "DIVIDEND REINVESTED": ("dividend_reinvest", 0),
    "IDCW REINVESTED": ("dividend_reinvest", 0),
    "REVERSAL": ("reversal", -1),
}

# Non-financial transaction types to silently skip (admin corrections, etc.)
_CAMS_ADMIN_KEYWORDS = (
    "address", "nct ", "nct-", "data updat", "permanent address",
    "change of bank", "ars", "contact", "mobile", "email", "registered",
    "cancelled", " cancelled", "invalid", "refund",
)


def _cams_txn_to_parsedtxn(row: dict[str, Any]) -> ParsedTxn | None:
    """Convert one CAMS Transaction Details row dict to ParsedTxn.

    Returns None for admin/non-cash rows and rows with zero amount.
    Applies B65 sign normalisation (statement → investor convention).
    """
    raw_type = str(row.get("TRANSACTION_TYPE") or "").strip()
    raw_amount = row.get("AMOUNT")
    raw_units = row.get("UNITS")
    raw_price = row.get("PRICE")
    raw_date = str(row.get("TRADE_DATE") or "").strip()

    # Skip admin/non-cash rows
    rt_lower = raw_type.lower()
    if any(kw in rt_lower for kw in _CAMS_ADMIN_KEYWORDS):
        return None

    try:
        amount = float(raw_amount) if raw_amount not in (None, "", "0") else 0.0
        units = float(raw_units) if raw_units not in (None, "", "0") else 0.0
        price = float(raw_price) if raw_price not in (None, "", "0") else None
    except (TypeError, ValueError):
        return None

    if amount == 0.0 and units == 0.0:
        return None

    # Parse date — CAMS uses DD-MON-YYYY (e.g. 27-FEB-2017)
    try:
        d = datetime.strptime(raw_date, "%d-%b-%Y").date()
    except ValueError:
        return None

    rt_upper = raw_type.strip().upper()
    txn_info = _CAMS_TXN_MAP.get(rt_upper)
    if txn_info is None:
        # Try prefix match for variants
        for key, info in _CAMS_TXN_MAP.items():
            if rt_upper.startswith(key):
                txn_info = info
                break
    if txn_info is None:
        logger.debug("cams_txn_parser: unknown txn type %r — skipping", raw_type)
        return None

    canon_type, sign = txn_info
    if sign == 0:
        # DIVIDEND_REINVEST — unit-only, no external cashflow; record amount=0
        return ParsedTxn(
            when=d, amount=0.0, is_sip=False,
            txn_type=canon_type, units=units, nav=price,
        )

    # B65: investor convention — purchases negative (outflow), redemptions positive (inflow).
    # CAMS statement convention: purchases are +amount, redemptions are -amount.
    # Multiplying by sign (-1 for all cashflow types, +1 only for dividend_payout)
    # correctly converts: -(+8000) = -8000 for purchase; -(-101) = +101 for redemption.
    investor_amount = amount * sign
    is_sip = canon_type == "sip"
    return ParsedTxn(
        when=d, amount=investor_amount, is_sip=is_sip,
        txn_type=canon_type, units=units, nav=price,
    )


def _rows_to_parsedholdings(rows: list[dict[str, Any]]) -> list[ParsedHolding]:
    """Core CAMS TDS parser: list of row dicts → list[ParsedHolding].

    Groups rows by (FOLIO_NUMBER, PRODUCT_CODE) so each distinct folio+scheme
    becomes one ParsedHolding.  The `isin` field is set to the placeholder
    "CAMS:<product_code>" — the caller resolves it to a real ISIN.
    """
    from collections import defaultdict

    holdings_txns: dict[tuple[str, str], list[ParsedTxn]] = defaultdict(list)
    holdings_meta: dict[tuple[str, str], dict] = {}

    for row in rows:
        folio = str(row.get("FOLIO_NUMBER") or "").strip()
        product = str(row.get("PRODUCT_CODE") or "").strip()
        scheme_name = str(row.get("SCHEME_NAME") or "").strip()
        mf_name = str(row.get("MF_NAME") or "").strip()

        key = (folio, product)
        if key not in holdings_meta:
            holdings_meta[key] = {
                "scheme_name": scheme_name,
                "mf_name": mf_name,
                "folio": folio,
                "product": product,
            }

        txn = _cams_txn_to_parsedtxn(row)
        if txn is not None:
            holdings_txns[key].append(txn)

    result: list[ParsedHolding] = []
    for key, meta in holdings_meta.items():
        txns = sorted(holdings_txns.get(key, []), key=lambda t: t.when)

        # Compute current units from transaction history
        current_units = sum(t.units for t in txns if t.units != 0.0)
        # Net invested = sum of purchase amounts (outflows are negative in investor convention)
        net_invested = sum(-t.amount for t in txns if t.amount < 0)

        result.append(
            ParsedHolding(
                isin=f"CAMS:{meta['product']}",   # placeholder — caller resolves
                amfi_code=None,
                scheme_name=_clean_text(meta["scheme_name"]) or meta["product"],
                folio_number=normalize_folio(meta["folio"]),
                units=round(current_units, 6),
                nav=None,
                value=None,     # unknown without current NAV
                cost=round(net_invested, 2) if net_invested > 0 else None,
                as_of_date=None,
                txns=txns,
            )
        )

    return result


def parse_cams_txn_text(path: str) -> list[ParsedHolding]:
    """Parse a CAMS Transaction Details Statement in TAB-SEPARATED TEXT format (.txt).

    This is the "Text" format downloaded from camsonline.com → Statements →
    Transaction Details Statement.  No password required.

    Returns a list of ParsedHolding with isin="CAMS:<product_code>" placeholders
    that the caller must resolve to real ISINs before further processing.
    """
    import csv

    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append(dict(row))

    if not rows:
        raise CasParseError(f"No data rows found in {path}")

    holdings = _rows_to_parsedholdings(rows)
    logger.info("cams_txn_text: parsed %d holdings from %s", len(holdings), path)
    return holdings


def parse_cams_txn_excel(path: str) -> list[ParsedHolding]:
    """Parse a CAMS Transaction Details Statement in EXCEL format (.xls or .xlsx).

    Supports:
      .xls  — Excel 97-2003 (via xlrd, must be installed)
      .xlsx — Excel 2007+ (via openpyxl, already a dependency)

    Returns ParsedHolding list with isin="CAMS:<product_code>" placeholders.
    """
    rows: list[dict[str, Any]] = []
    ext = path.rsplit(".", 1)[-1].lower()

    if ext == "xls":
        import xlrd  # xlrd handles legacy .xls; add to requirements if needed

        wb = xlrd.open_workbook(path)
        ws = wb.sheet_by_index(0)
        if ws.nrows < 2:
            raise CasParseError(f"No data rows found in {path}")
        headers = [str(ws.cell_value(0, c)).strip() for c in range(ws.ncols)]
        for r in range(1, ws.nrows):
            row = {}
            for c, h in enumerate(headers):
                v = ws.cell_value(r, c)
                row[h] = v
            rows.append(row)
    else:
        # .xlsx via openpyxl
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        row_iter = iter(ws.rows)
        headers = [str(cell.value).strip() for cell in next(row_iter)]
        for xrow in row_iter:
            row = {h: (cell.value if cell.value is not None else "") for h, cell in zip(headers, xrow)}
            rows.append(row)
        wb.close()

    if not rows:
        raise CasParseError(f"No data rows found in {path}")

    holdings = _rows_to_parsedholdings(rows)
    logger.info("cams_txn_excel: parsed %d holdings from %s", len(holdings), path)
    return holdings


def detect_and_parse(path: str, password: str | None = None) -> list[ParsedHolding]:
    """Route to the correct parser based on file extension.

    Supported:
      .pdf        — standard CAS PDF (casparser)
      .txt        — CAMS Transaction Details Statement (tab-separated text)
      .xls/.xlsx  — CAMS Transaction Details Statement (Excel)
    """
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if ext == "pdf":
        return parse_cas(path, password=password)
    if ext == "txt":
        return parse_cams_txn_text(path)
    if ext in ("xls", "xlsx"):
        return parse_cams_txn_excel(path)
    raise CasParseError(
        f"Unsupported file type '.{ext}'. "
        "Upload a CAS PDF, a CAMS Transaction Details Statement (.txt or .xls/.xlsx)."
    )


def _cas_source_ref(isin: str, folio_norm: str, t: ParsedTxn) -> str:
    """Deterministic per-txn fingerprint. casparser exposes NO stable txn id, so source_ref must be
    derived so a re-upload of the same statement reproduces it → ON CONFLICT skip (idempotent). Encodes
    units, so two same-amount/different-units txns don't collide. A genuine duplicate (every field
    identical) is indistinguishable in a CAS and de-dups to one row — accepted, best-effort."""
    import hashlib

    raw = f"{isin}|{folio_norm}|{t.when.isoformat()}|{t.txn_type}|{t.amount:.2f}|{t.units:.4f}"
    return "cas:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def build_cas_ledger_rows(
    parsed: list[ParsedHolding], *, user_id: str, portfolio_id: str
) -> list[dict[str, Any]]:
    """Map parsed CAS holdings → canonical append-only ledger rows (mf.portfolio_transactions), reusing
    the B65 signed `amount` from parse_cas (never raw casparser amounts). `user_id` is the AUTHENTICATED
    uploader (task arg) — a ParsedHolding carries NO user_id, so a row can never be owned by the file.

    v1 ingests the cashflow txns parse_cas surfaces; dividend_reinvest/bonus/split/tax are not yet in
    the ledger — B3's holdings replay-parity vs mf_user_holdings will surface any units gap and drive
    the extension (don't add them speculatively)."""
    import uuid as _uuid

    uid = _uuid.UUID(user_id)
    pid = _uuid.UUID(portfolio_id)
    rows: list[dict[str, Any]] = []
    for p in parsed:
        folio_norm = normalize_folio(p.folio_number)
        for t in p.txns:
            rows.append(
                {
                    "user_id": uid,
                    "portfolio_id": pid,
                    "asset_class": "mf",
                    "instrument_id": p.isin,
                    "folio_number": folio_norm,
                    "txn_type": t.txn_type,
                    "txn_date": t.when,
                    "units": t.units,
                    "nav_or_price": t.nav,
                    "amount": t.amount,
                    "source": "cas",
                    "source_ref": _cas_source_ref(p.isin, folio_norm, t),
                    "parser_version": PARSER_VERSION,
                }
            )
    return rows
