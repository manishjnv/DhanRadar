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
_TXN_FLOW_EXCLUDED = frozenset(
    {"DIVIDEND_REINVEST", "SEGREGATION", "STT_TAX", "STAMP_DUTY_TAX",
     "TDS_TAX", "MISC", "UNKNOWN"}
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
