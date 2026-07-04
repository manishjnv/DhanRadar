"""
DhanRadar — Dashboard response schemas (B56).

EXPLICIT allowlist Pydantic models — never `from_orm`/expose-all over an ORM row,
so a tier-gated numeric (`mf.user_fund_scores.unified_score`) can never leak into a
client payload (non-neg #2). The only numerics present are the user's OWN money
figures (`current_value`, `xirr_pct`) and PUBLIC market index levels — neither is a
score / factor weight / fair value.

`label` carries the non-advisory verb-label enum value only
(`in_form/on_track/off_track/out_of_form/insufficient_data`); `confidence_band` is
`high/medium/low/insufficient_data`. No advisory verbs anywhere (non-neg #1).
"""

from __future__ import annotations

from pydantic import BaseModel


class FundLabel(BaseModel):
    """One holding's public projection — label + band only, never a numeric score."""

    isin: str
    scheme_name: str
    label: str
    confidence_band: str


class PortfolioSummary(BaseModel):
    """The requesting user's own MF rollup. `current_value`/`xirr_pct` are the user's
    own money figures (allowed in DOM) and may be null when no snapshot exists yet."""

    current_value: float | None
    xirr_pct: float | None
    fund_count: int
    last_updated: str | None
    funds: list[FundLabel]
    # Disclosure bundle — this surface renders labels, so it carries NOT_ADVICE +
    # the in-force disclaimer version (non-neg #9), mirroring the Mood payload.
    disclosure: str
    not_advice: str
    disclaimer_version: str


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


class TopScoredFund(BaseModel):
    """One ranked fund — label + band only (no numeric)."""

    isin: str
    scheme_name: str
    category: str
    label: str
    confidence_band: str


class TopScoredResponse(BaseModel):
    """Envelope for the top-scored list. Carries the disclosure bundle because this
    surface renders labels (non-neg #9) — same pattern as the portfolio summary and
    the Mood payload, so the disclosure is tied to the in-force disclaimer version."""

    funds: list[TopScoredFund]
    disclosure: str
    not_advice: str
    disclaimer_version: str
