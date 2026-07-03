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
from statistics import median
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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


#: Message substrings that mean "we understood you gave us a file, but couldn't read it"
#: (corrupt PDF, empty statement, unsupported extension) — as opposed to a wrong password.
#: Matched against str(exc): every raise site above preserves either the underlying
#: casparser exception's CLASS NAME (parse_cas's `except Exception` handler) or one of
#: these literal phrases (the txt/xls/unsupported-type raises further down this file).
_UNREADABLE_MARKERS = (
    "CASParseError", "HeaderParseError", "CASIntegrityError", "IncompleteCASError",
    "Unsupported file type", "No data rows found",
)


def classify_cas_failure(exc: CasParseError) -> str:
    """Map a CasParseError to a closed, machine-readable code for `MfCasJob.error_message`.

    The frontend translates the code to plain-language copy — the raw exception text is
    NEVER served to the client (it can carry PDF-library internals, and for a generic
    reader failure could even echo the attempted password). incorrect_password /
    unreadable_file are diagnosed from the class name/phrase cas.py preserves in the
    message; anything unrecognised falls back to the generic parse_failed code.
    """
    msg = str(exc)
    if "IncorrectPasswordError" in msg:
        return "incorrect_password"
    if any(marker in msg for marker in _UNREADABLE_MARKERS):
        return "unreadable_file"
    return "parse_failed"


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
class ParsedCasIdentity:
    """Investor identity extracted from a CAS file (best-effort; all fields nullable).

    PAN is validated against the canonical 10-char format before being stored;
    anything that doesn't match is set to None so downstream callers never receive
    a malformed PAN. investor_name is trimmed but otherwise kept as-is.

    stmt_from/stmt_to (§39.4) are the CAS's own statement-period header — casparser's PDF
    parsers (CAMS/KFintech/CDSL/NSDL) expose `statement_period`; the CAMS Transaction-Details
    .txt/.xls format has NO such header, so those stay None (never guessed).
    """

    pan: str | None           # uppercase, 10-char PAN — None if absent or malformed
    investor_name: str | None  # as printed in the CAS
    stmt_from: date | None = None
    stmt_to: date | None = None


_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


def _parse_pan(raw: str | None) -> str | None:
    """Normalize and validate a raw PAN string. Returns None if invalid."""
    if not raw:
        return None
    # Strip common prefixes from CAMS TDS format: "PAN NO:BQOPK2200H"
    pan = re.sub(r"^PAN\s*NO\s*:\s*", "", raw.strip(), flags=re.IGNORECASE).strip().upper()
    return pan if _PAN_RE.match(pan) else None


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
    # Per-folio PAN, when the source exposes one (casparser PDF folios, CAMS TDS rows carry a PAN
    # column) — the per-folio ownership guard (family-merge incident 2026-07-04: a consolidated PDF
    # can carry a DIFFERENT investor's folios, e.g. a household member sharing one RTA email)
    # compares this to the portfolio owner's stored PAN and excludes a folio whose PAN doesn't
    # match. None when the source has no per-folio PAN (assumed the owner's — status quo).
    folio_pan: str | None = None


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
) -> tuple[list[ParsedHolding], ParsedCasIdentity]:
    """Parse a CAMS/KFintech CAS PDF into normalized holdings + investor identity.

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
        # Per-folio PAN (family-merge guard) — casparser exposes it on the folio dict itself.
        folio_pan = _parse_pan(folio.get("PAN") or folio.get("pan"))
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
                    folio_pan=folio_pan,
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
            account_pan = (
                _parse_pan(account.get("PAN") or account.get("pan"))
                if isinstance(account, dict) else None
            )
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
                        folio_pan=account_pan,
                    )
                )

    return holdings, _extract_pdf_identity(raw)


#: casparser's PDF statement_period strings are "dd-Mmm-yyyy" (e.g. "01-Apr-2023") — the same
#: format its own STMT_PERIOD_RE/PERIOD_RE regexes emit for CAMS/KFintech and CDSL/NSDL alike.
_STMT_DATE_FMTS = ("%d-%b-%Y", "%d-%b-%y", "%Y-%m-%d")


def _parse_stmt_date(s: str | None) -> date | None:
    """Best-effort parse of a casparser statement_period date string. None on empty/unparseable
    input (§39.4: never guess) — casparser itself defaults to "" when it can't find the header."""
    if not s:
        return None
    for fmt in _STMT_DATE_FMTS:
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _extract_pdf_identity(raw: dict) -> ParsedCasIdentity:
    """Best-effort investor identity from a casparser raw output dict.

    casparser embeds investor info in `investor_info` (name, email, mobile) and
    the PAN in the first folio's `PAN` / `pan` key or in `investor_info.pan`.
    All of these are optional depending on the CAS type and casparser version.

    §39.4: also extracts the statement-period header (`statement_period.from`/`.to` — pydantic
    model_dump uses the field name `from_`, so both spellings are checked defensively).
    """
    info = raw.get("investor_info") or {}
    raw_pan = (
        info.get("pan")
        or info.get("PAN")
        or next(
            (f.get("PAN") or f.get("pan") for f in raw.get("folios", []) or []
             if f.get("PAN") or f.get("pan")),
            None,
        )
    )
    name = str(info.get("name") or "").strip() or None
    sp = raw.get("statement_period") or {}
    stmt_from = _parse_stmt_date(sp.get("from_") or sp.get("from"))
    stmt_to = _parse_stmt_date(sp.get("to"))
    return ParsedCasIdentity(
        pan=_parse_pan(raw_pan), investor_name=name, stmt_from=stmt_from, stmt_to=stmt_to
    )


def _extract_cams_tds_identity(rows: list[dict]) -> ParsedCasIdentity:
    """Extract investor identity from the first data row of a CAMS TDS file."""
    if not rows:
        return ParsedCasIdentity(pan=None, investor_name=None)
    row = rows[0]
    raw_pan = str(row.get("PAN") or "").strip()
    name = str(row.get("INVESTOR_NAME") or "").strip() or None
    return ParsedCasIdentity(pan=_parse_pan(raw_pan), investor_name=name)


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

_FOLIO_PLAN_SUFFIX = re.compile(r"/0+$")


def normalize_folio(folio: str) -> str:
    """Canonical folio for ledger/holdings agreement across EVERY source format (B82, hardened
    2026-07-04 after the cross-format dedup incident): strip ALL whitespace — not just
    leading/trailing — since one format prints "33375865/ 73" (internal space) and another prints
    "33375865/73" for the SAME real folio; then uppercase (a folio suffix letter can be cased
    differently across exports); then strip a trailing `/0` plan suffix CAMS appends (e.g.
    `12345/0` -> `12345`). Conservative — only a slash-zeros tail is removed, never digits from the
    folio body. EVERY seam that keys on folio (source_ref fingerprint, the ledger row itself, the
    holdings projection + write, statement checkpoints) MUST call this so the same real-world folio
    collides to one key regardless of which format printed it."""
    if not folio:
        return ""
    no_ws = re.sub(r"\s+", "", folio).upper()
    return _FOLIO_PLAN_SUFFIX.sub("", no_ws)


# ---------------------------------------------------------------------------
# CAMS Transaction Details Statement parsers (.txt / .xls / .xlsx)
#
# The "Transaction Details Statement" from camsonline.com is a separate product
# from the CAS PDF.  It contains full transaction history (Purchase/SIP/
# Redemption/Switch) but no ISIN codes.  The parser returns ParsedHolding
# objects where `isin` is a PLACEHOLDER of the form "CAMS:<product_code>" —
# the caller (tasks/mf.py _run_pipeline) resolves these to real ISINs via
# resolve_cams_isins() below before further processing.
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
        pan = str(row.get("PAN") or "").strip()

        key = (folio, product)
        if key not in holdings_meta:
            holdings_meta[key] = {
                "scheme_name": scheme_name,
                "mf_name": mf_name,
                "folio": folio,
                "product": product,
                "pan": pan,
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
                folio_pan=_parse_pan(meta.get("pan")),
            )
        )

    return result


def parse_cams_txn_text(path: str) -> tuple[list[ParsedHolding], ParsedCasIdentity]:
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

    identity = _extract_cams_tds_identity(rows)
    holdings = _rows_to_parsedholdings(rows)
    logger.info("cams_txn_text: parsed %d holdings from %s", len(holdings), path)
    return holdings, identity


def parse_cams_txn_excel(path: str) -> tuple[list[ParsedHolding], ParsedCasIdentity]:
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

    identity = _extract_cams_tds_identity(rows)
    holdings = _rows_to_parsedholdings(rows)
    logger.info("cams_txn_excel: parsed %d holdings from %s", len(holdings), path)
    return holdings, identity


def detect_and_parse(path: str, password: str | None = None) -> tuple[list[ParsedHolding], ParsedCasIdentity]:
    """Route to the correct parser based on file extension. Returns (holdings, identity).

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


# ---------------------------------------------------------------------------
# CAMS placeholder → real-ISIN resolution (B94-hardened)
# ---------------------------------------------------------------------------
# B94 (prod 2026-07-03): a bare best-similarity match resolved the founder's
# "HDFC NIFTY Smallcap 250 Index Fund" to DSP's INF740KA1XH4 (both names contain
# "Nifty Smallcap 250 Index Fund"); 12 SIPs were priced off the wrong fund's NAV
# (txn prices matched HDFC's NAV to 4 decimals, deviated 77% from DSP's).
# A resolution must now clear THREE independent guards; anything that fails ANY
# guard keeps its placeholder and scores as insufficient_data (honest fail-safe).

#: Guard 2 — pg_trgm similarity floor for the best AMC-gate survivor.
CAMS_RESOLVE_MIN_SIM = 0.45
#: Guard 2 — required margin between best and second-best survivor (ambiguity).
CAMS_RESOLVE_MIN_MARGIN = 0.05
#: Guard 3 — max median relative deviation of txn purchase prices vs NAV history.
CAMS_RESOLVE_MAX_PRICE_DEV = 0.05


def _amc_token(amc_name: str | None, scheme_name: str) -> str:
    """AMC brand token: first word of mf_funds.amc_name lowercased (fallback: first
    word of the matched scheme_name — AMFI scheme names lead with the AMC brand)."""
    words = ((amc_name or "").strip() or scheme_name.strip()).split()
    return words[0].lower() if words else ""


async def resolve_cams_isins(db: AsyncSession, holdings: list[ParsedHolding]) -> dict[str, str]:
    """Resolve "CAMS:<product_code>" placeholder ISINs to real ISINs (B94-hardened).

    Returns {placeholder_isin: real_isin} ONLY for holdings that clear all three guards:

      1. AMC token gate — the candidate fund's AMC brand token must appear in the
         CAMS scheme name ('dsp' is not in an HDFC statement line → rejected).
      2. Similarity floor + ambiguity margin — best sim >= CAMS_RESOLVE_MIN_SIM AND
         (best - second_best) >= CAMS_RESOLVE_MIN_MARGIN among AMC-gate survivors.
      3. Price consistency (the money check) — the holding's per-txn purchase prices
         must agree with mf_nav_history for the candidate ISIN on those dates
         (median relative deviation <= CAMS_RESOLVE_MAX_PRICE_DEV). No comparable
         price points → accept on guards 1+2 alone, logged cams_isin_unvalidated.

    Holdings that fail any guard are omitted from the map (the caller keeps the
    placeholder → the existing insufficient_data path downstream).
    """
    from sqlalchemy import Date, String, bindparam
    from sqlalchemy import text as _sa_text
    from sqlalchemy.dialects.postgresql import ARRAY

    # Group by placeholder (same product code can appear under several folios).
    by_ph: dict[str, list[ParsedHolding]] = {}
    for h in holdings:
        if h.isin.startswith("CAMS:"):
            by_ph.setdefault(h.isin, []).append(h)
    if not by_ph:
        return {}

    placeholders = list(by_ph)
    names = [by_ph[ph][0].scheme_name for ph in placeholders]

    # ONE batched query, top-5 candidates per name (0.25 is a deliberately wide
    # candidate net — the three guards below do the actual accepting).
    rows = (
        await db.execute(
            _sa_text("""
            SELECT idx, isin, scheme_name, amc_name, sim FROM (
                SELECT (n.idx - 1)::int AS idx,
                       f.isin, f.scheme_name, f.amc_name,
                       similarity(f.scheme_name, n.name) AS sim,
                       row_number() OVER (
                           PARTITION BY n.idx
                           ORDER BY similarity(f.scheme_name, n.name) DESC, f.isin
                       ) AS rn
                FROM unnest(:names) WITH ORDINALITY AS n(name, idx),
                     mf.mf_funds f
                WHERE similarity(f.scheme_name, n.name) > 0.25
            ) c WHERE rn <= 5
            ORDER BY idx, sim DESC
        """).bindparams(bindparam("names", type_=ARRAY(String))),
            {"names": names},
        )
    ).all()
    candidates: dict[int, list[Any]] = {}
    for r in rows:
        candidates.setdefault(r.idx, []).append(r)

    # Guards 1 + 2 → at most one winner per placeholder.
    winners: dict[str, tuple[str, float]] = {}  # placeholder → (isin, sim)
    for i, ph in enumerate(placeholders):
        cams_name = names[i]
        cands = candidates.get(i, [])
        if not cands:
            logger.warning(
                "cams_isin_unresolved: %r (no candidates above 0.25) -- keeping placeholder",
                cams_name,
            )
            continue
        cams_lower = cams_name.lower()
        survivors = [c for c in cands if _amc_token(c.amc_name, c.scheme_name) in cams_lower]
        if not survivors:
            logger.warning(
                "cams_isin_rejected: %r (reason=amc_token_mismatch, best_candidate=%s sim=%.2f)"
                " -- keeping placeholder",
                cams_name,
                cands[0].isin,
                float(cands[0].sim),
            )
            continue
        best = survivors[0]
        best_sim = float(best.sim)
        second_sim = float(survivors[1].sim) if len(survivors) > 1 else 0.0
        if best_sim < CAMS_RESOLVE_MIN_SIM:
            logger.warning(
                "cams_isin_rejected: %r (reason=low_similarity, best=%s sim=%.2f)"
                " -- keeping placeholder",
                cams_name,
                best.isin,
                best_sim,
            )
            continue
        if best_sim - second_sim < CAMS_RESOLVE_MIN_MARGIN:
            logger.warning(
                "cams_isin_rejected: %r (reason=ambiguous, best=%s sim=%.2f vs second=%s sim=%.2f)"
                " -- keeping placeholder",
                cams_name,
                best.isin,
                best_sim,
                survivors[1].isin,
                second_sim,
            )
            continue
        winners[ph] = (best.isin, best_sim)

    if not winners:
        return {}

    # Guard 3 — price consistency. Collect (winner_isin, txn_date) pairs across all
    # winners' txns that carry a purchase price, fetch NAV for all of them in ONE query.
    points: dict[str, list[tuple[date, float]]] = {}  # placeholder → [(when, txn_price)]
    pairs: set[tuple[str, date]] = set()
    for ph, (isin, _sim) in winners.items():
        pts = [
            (t.when, float(t.nav))
            for h in by_ph[ph]
            for t in h.txns
            if t.nav is not None and t.nav > 0
        ]
        points[ph] = pts
        pairs.update((isin, when) for when, _ in pts)

    nav_by_key: dict[tuple[str, date], float] = {}
    if pairs:
        ordered = sorted(pairs)
        nav_rows = (
            await db.execute(
                _sa_text("""
                SELECT n.isin AS isin, n.d AS nav_date, h.nav AS nav
                FROM unnest(:isins, :dates) AS n(isin, d)
                JOIN mf.mf_nav_history h ON h.isin = n.isin AND h.nav_date = n.d
            """).bindparams(
                    bindparam("isins", type_=ARRAY(String)),
                    bindparam("dates", type_=ARRAY(Date)),
                ),
                {"isins": [p[0] for p in ordered], "dates": [p[1] for p in ordered]},
            )
        ).all()
        nav_by_key = {(r.isin, r.nav_date): float(r.nav) for r in nav_rows if float(r.nav) > 0}

    resolved: dict[str, str] = {}
    for ph, (isin, sim) in winners.items():
        cams_name = by_ph[ph][0].scheme_name
        devs = [
            abs(txn_price - nav_by_key[(isin, when)]) / nav_by_key[(isin, when)]
            for when, txn_price in points[ph]
            if (isin, when) in nav_by_key
        ]
        if devs:
            med = median(devs)
            if med > CAMS_RESOLVE_MAX_PRICE_DEV:
                # This is the guard that would have caught B94 even if the names had
                # passed: the DSP series deviated 77% from the actual txn prices.
                logger.warning(
                    "cams_isin_price_mismatch: %r -> %s REJECTED"
                    " (median_dev=%.4f, n_price_points=%d) -- keeping placeholder",
                    cams_name,
                    isin,
                    med,
                    len(devs),
                )
                continue
            logger.info(
                "cams_isin_resolved: %r -> %s (sim=%.2f, validated_pct_dev=%.4f, n_price_points=%d)",
                cams_name,
                isin,
                sim,
                med,
                len(devs),
            )
        else:
            logger.info(
                "cams_isin_unvalidated: %r -> %s (sim=%.2f, n_price_points=0)"
                " -- no comparable NAV coverage; accepted on name+amc guards",
                cams_name,
                isin,
                sim,
            )
        resolved[ph] = isin
    return resolved


def filter_foreign_pan_folios(
    parsed: list[ParsedHolding], owner_pan: str | None
) -> tuple[list[ParsedHolding], list[ParsedHolding]]:
    """Per-folio ownership guard (family-merge incident 2026-07-04): split parsed holdings into
    (owned, foreign) against the portfolio owner's authoritative stored PAN. A consolidated
    statement can carry a DIFFERENT investor's folios (e.g. a household member sharing one RTA
    email) — a folio whose OWN PAN (when the source exposed one) disagrees with `owner_pan` is
    foreign and must be excluded from the upload entirely (no ledger rows, no holdings, no
    checkpoints). A folio with no PAN info is assumed the owner's (status quo — e.g. CAMS TDS
    exports that predate this field, or CDSL account-level holdings). No `owner_pan` at all (the
    uploader has no PAN on file yet and this CAS carried none either) → nothing to compare
    against, so everything passes through unfiltered."""
    if not owner_pan:
        return list(parsed), []
    owned = [p for p in parsed if not (p.folio_pan and p.folio_pan != owner_pan)]
    foreign = [p for p in parsed if (p.folio_pan and p.folio_pan != owner_pan)]
    return owned, foreign


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
