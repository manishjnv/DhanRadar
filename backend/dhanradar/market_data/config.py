"""
DhanRadar — Market Data configuration.

DataKind enum, DataRequest, and the provider ladder maps.
Config-driven: ``load_ladders(path)`` reads a YAML file when given, else
returns ``DEFAULT_LADDERS`` — so a provider swap is config-only (arch §B4).

No imports from auth / billing / scoring.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# DataKind
# ---------------------------------------------------------------------------

class DataKind(str, enum.Enum):
    """Minimal set of data kinds covering funds and equities."""

    FUND_NAV = "fund_nav"
    FUND_HOLDINGS = "fund_holdings"
    EQUITY_PRICE = "equity_price"
    EQUITY_HOLDINGS = "equity_holdings"
    MACRO_SIGNAL = "macro_signal"


# ---------------------------------------------------------------------------
# DataRequest
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DataRequest:
    """
    Immutable request passed to ``MarketDataAdapter.fetch()``.

    ``params`` carries kind-specific keys, e.g.::

        DataRequest(DataKind.FUND_NAV, {"scheme_code": "120503"})
        DataRequest(DataKind.EQUITY_PRICE, {"symbol": "RELIANCE"})
    """

    kind: DataKind
    params: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Default ladder maps (architecture ledger #5)
# ---------------------------------------------------------------------------

DEFAULT_LADDERS: dict[DataKind, list[str]] = {
    # Funds: mf_central → account_aggregator → cas_parser → amfi_nav
    DataKind.FUND_NAV: ["mf_central", "amfi_nav"],
    DataKind.FUND_HOLDINGS: ["mf_central", "account_aggregator", "cas_parser", "amfi_nav"],
    # Equities/ETF: upstox → kite → twelvedata → nse_dump
    DataKind.EQUITY_PRICE: ["upstox", "kite", "twelvedata", "nse_dump"],
    DataKind.EQUITY_HOLDINGS: ["upstox", "kite", "twelvedata", "nse_dump"],
    # Macro signals for Mood Compass (best-effort, NSE public JSON)
    DataKind.MACRO_SIGNAL: ["nse_macro"],
}


# ---------------------------------------------------------------------------
# Config-driven ladder loader
# ---------------------------------------------------------------------------

def load_ladders(path: str | None = None) -> dict[DataKind, list[str]]:
    """
    Return the provider ladder map.

    If ``path`` is given, load from a YAML file (``yaml.safe_load``); the file
    must contain a top-level mapping whose keys are DataKind values (e.g.
    ``fund_nav``) and whose values are lists of provider-name strings.

    If ``path`` is ``None``, return a copy of ``DEFAULT_LADDERS``.
    """
    if path is None:
        return {k: list(v) for k, v in DEFAULT_LADDERS.items()}

    import yaml  # pyyaml — available as a transitive dep

    with open(path, encoding="utf-8") as fh:
        raw: dict = yaml.safe_load(fh) or {}

    ladders: dict[DataKind, list[str]] = {}
    for key, providers in raw.items():
        try:
            kind = DataKind(key)
        except ValueError:
            # Unknown kind in YAML — skip rather than hard-fail so adding a
            # new kind to YAML doesn't break older code.
            continue
        if isinstance(providers, list):
            ladders[kind] = [str(p) for p in providers]

    # Fill in any kinds not present in the YAML from the defaults.
    for kind, default_providers in DEFAULT_LADDERS.items():
        if kind not in ladders:
            ladders[kind] = list(default_providers)

    return ladders
