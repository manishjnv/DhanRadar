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

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Optional

# A reader takes (path, password) and returns the casparser dict structure.
CasReader = Callable[[str, Optional[str]], dict[str, Any]]


class CasParseError(Exception):
    """The CAS could not be parsed (bad password, corrupt, or unsupported format)."""


@dataclass(frozen=True)
class ParsedTxn:
    when: date
    amount: float  # signed: purchases negative (outflow), redemptions positive


@dataclass(frozen=True)
class ParsedHolding:
    isin: str
    amfi_code: Optional[str]
    scheme_name: str
    folio_number: str
    units: float
    nav: Optional[float]
    value: Optional[float]
    cost: Optional[float]
    as_of_date: Optional[date]
    txns: list[ParsedTxn]


def _default_reader(path: str, password: Optional[str]) -> dict[str, Any]:  # pragma: no cover
    import casparser  # imported lazily; only present in the worker image

    return casparser.read_cas_pdf(path, password)


def _to_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def parse_cas(
    path: str,
    password: Optional[str],
    *,
    reader: Optional[CasReader] = None,
) -> list[ParsedHolding]:
    """Parse a CAMS/KFintech CAS PDF into normalized holdings.

    Walks `folios[].schemes[]`, keeping only schemes that carry an ISIN (a stock
    CAS / non-MF row has none). Raises CasParseError on any reader failure (e.g.
    wrong password) — the caller marks the job failed and purges the file."""
    read = reader or _default_reader
    try:
        raw = read(path, password)
    except Exception as exc:  # noqa: BLE001 - any reader failure is a parse failure
        raise CasParseError(str(exc)) from exc

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
                    scheme_name=str(scheme.get("scheme") or ""),
                    folio_number=folio_no,
                    units=float(scheme.get("close") or scheme.get("units") or 0.0),
                    nav=_opt_float(valuation.get("nav")),
                    value=_opt_float(valuation.get("value")),
                    cost=_opt_float(valuation.get("cost")),
                    as_of_date=_to_date(valuation.get("date")),
                    txns=txns,
                )
            )
    return holdings


def _opt_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
