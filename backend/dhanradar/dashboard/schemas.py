"""
DhanRadar — Dashboard response schemas (B56).

EXPLICIT allowlist Pydantic models — never `from_orm`/expose-all over an ORM row,
so a tier-gated numeric (`mf.user_fund_scores.unified_score`) can never leak into a
client payload (non-neg #2). The only numerics present are PUBLIC market index /
ticker levels — never a score / factor weight / fair value.
"""

from __future__ import annotations

from pydantic import BaseModel


class MarketIndex(BaseModel):
    """A public market index level — `value` and `change_pct` are public market data
    (not a DhanRadar score), explicitly allowed in the DOM."""

    name: str
    value: float
    change_pct: float


class TickerItem(BaseModel):
    """One global-ticker-strip quote — raw public market data (index/FX/commodity
    level + daily % change), DOM-allowed like `MarketIndex`."""

    key: str
    label: str
    value: float
    change_pct: float


class TickerOut(BaseModel):
    """The global top-strip payload: quote items in render order plus the cached
    FII/DII net flows (₹ Cr) + Nifty PCR from the mood snapshot — all raw public
    figures, all None when the flows cache is cold (strip shows an em-dash)."""

    items: list[TickerItem]
    fii_cr: float | None = None
    dii_cr: float | None = None
    pcr: float | None = None
    flows_as_of: str | None = None
