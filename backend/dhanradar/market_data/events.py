"""
DhanRadar — Market Data normalized event types.

Frozen dataclasses consumed by domain modules after the adapter walks the
provider ladder.  Pure data — no I/O, no imports from auth/billing/scoring.

Canonical event name constants mirror the architecture ledger and are the
stable strings emitted to the pluggable event sink.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Canonical event name constants
# ---------------------------------------------------------------------------
EVENT_MFCENTRAL_HOLDINGS_RECEIVED = "mfcentral.holdings.received"
EVENT_AA_HOLDINGS_RECEIVED = "aa.holdings.received"
EVENT_BROKER_POSITIONS_RECEIVED = "broker.positions.received"
EVENT_NAV_REFRESHED = "nav.refreshed"
EVENT_PRICE_REFRESHED = "price.refreshed"
EVENT_MACRO_SIGNAL_RECEIVED = "macro.signal.received"


# ---------------------------------------------------------------------------
# Normalized event dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NavRefreshed:
    """NAV updated for a mutual-fund scheme (from mf_central / amfi_nav)."""

    scheme_code: str
    nav: float
    nav_date: str   # ISO-8601 date string, e.g. "2026-06-05"
    source: str     # provider name that produced this event

    # Stable event name — matches EVENT_NAV_REFRESHED
    event_name: str = EVENT_NAV_REFRESHED

    @property
    def name(self) -> str:
        return self.event_name


@dataclass(frozen=True)
class PriceRefreshed:
    """Latest price tick for an equity / ETF (from upstox / kite / twelvedata / nse_dump)."""

    symbol: str
    price: float
    ts: str     # ISO-8601 timestamp string
    source: str

    event_name: str = EVENT_PRICE_REFRESHED

    @property
    def name(self) -> str:
        return self.event_name


@dataclass(frozen=True)
class MacroSignalReceived:
    """Best-effort macro signals for the Mood Compass (from nse_macro provider).

    ``signals`` carries raw or lightly-processed values for the subset of
    signals the provider managed to fetch; absent signals are omitted (None
    means the key is not present, not that it was normalised to 0).
    Consumer (mood/signals.py) normalises each value to [0,1] independently.
    """

    source: str
    signals: dict  # e.g. {"nifty_trend": 0.42, "india_vix": 15.3, ...}
    fetched_at: str  # ISO-8601 timestamp string
    event_name: str = EVENT_MACRO_SIGNAL_RECEIVED

    @property
    def name(self) -> str:
        return self.event_name


@dataclass(frozen=True)
class HoldingsReceived:
    """
    Normalised holdings payload from any holdings provider.

    ``event_name`` must be one of the three ``*.holdings.received`` /
    ``*.positions.received`` constants depending on origin:
      - mf_central  → EVENT_MFCENTRAL_HOLDINGS_RECEIVED
      - account_aggregator → EVENT_AA_HOLDINGS_RECEIVED
      - broker / upstox / kite → EVENT_BROKER_POSITIONS_RECEIVED
    """

    source: str
    owner_ref: str          # opaque owner reference (user_id hash or equivalent)
    holdings: list[dict]    # list of normalised holding dicts
    received_at: str        # ISO-8601 timestamp string
    event_name: str         # one of the three *.received constants above

    @property
    def name(self) -> str:
        return self.event_name
