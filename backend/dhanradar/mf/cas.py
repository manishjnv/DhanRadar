"""
DhanRadar — CAS parsing service (architecture Tier-C MF Module, Phase 5).

Wraps `casparser.read_cas_pdf(path, password)` and normalizes its output into a
flat list of `ParsedHolding`. CAMS + KFintech only — NSDL/CDSL equity CAS is NOT
supported (anti-pattern guard); a non-MF CAS yields no MF schemes.

`casparser` is an optional runtime dependency (installed in the worker image). It
is injected via `reader=` so this module is unit-testable without the library or
a real PDF; production passes the real `casparser.read_cas_pdf`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

# A reader takes (path, password) and returns the casparser output — a dict
# (casparser 0.7.x) or a CASData pydantic model (>=1.0); parse_cas normalises both.
CasReader = Callable[[str, str | None], Any]


class CasParseError(Exception):
    """The CAS could not be parsed (bad password, corrupt, or unsupported format)."""


@dataclass(frozen=True)
class ParsedTxn:
    when: date
    amount: float  # signed: purchases negative (outflow), redemptions positive


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
                txns.append(ParsedTxn(when=when, amount=float(amt)))
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
