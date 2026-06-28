"""Read-model assembler for the portfolio concept endpoints (C1 holdings.list / C2 portfolio.summary).

ONE place that loads a portfolio's holdings enriched with fund metadata + latest NAV + the educational
label/band, plus the portfolio totals. Both concepts HAND-BUILD their payloads from this — only explicit,
#2-safe fields; the raw `unified_score` is NEVER selected (structural #2 guarantee at the builder; the A3
boundary scrub is only a backstop). `invested` is the ledger **net-invested** (B86: the single invested
definition — the B3 projection writes it to `mf_user_holdings.invested_amount`).

Read-only, owner-scoped by RLS (the caller checks ownership first). No score, no advisory verbs.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.models.mf import MfFund, MfPortfolioSnapshot, MfUserHolding, UserFundScore


@dataclass(frozen=True)
class EnrichedHolding:
    isin: str
    scheme_name: str
    category: str | None
    folio_number: str
    units: float
    invested: float  # ledger net-invested (B86)
    current_nav: float | None
    current_value: float
    label: str | None  # verb_label — educational (#1), never an advisory verb
    confidence_band: str | None  # high|medium|low band — never a numeric score (#2)
    as_of: str | None


@dataclass(frozen=True)
class PortfolioReadModel:
    holdings: list[EnrichedHolding]
    total_invested: float
    total_value: float
    xirr_pct: float | None
    as_of: str | None


async def load_portfolio_read_model(db: AsyncSession, portfolio_id: str) -> PortfolioReadModel:
    """Load the owner's holdings (RLS-scoped) enriched with fund name/category + latest NAV + label/band,
    plus portfolio totals. `invested_amount` is read straight from `mf_user_holdings` = net-invested (B86).
    `unified_score` is never queried."""
    pid = uuid.UUID(portfolio_id)

    holdings = (
        await db.execute(select(MfUserHolding).where(MfUserHolding.portfolio_id == pid))
    ).scalars().all()
    isins = [h.isin for h in holdings]

    nav_map: dict[str, float] = {}
    fund_meta: dict[str, MfFund] = {}
    if isins:
        nav_rows = await db.execute(
            text(
                "SELECT DISTINCT ON (isin) isin, nav FROM mf.mf_nav_history"
                " WHERE isin = ANY(:isins) ORDER BY isin, nav_date DESC"
            ),
            {"isins": isins},
        )
        nav_map = {r.isin: float(r.nav) for r in nav_rows}
        fund_meta = {
            f.isin: f
            for f in (await db.execute(select(MfFund).where(MfFund.isin.in_(isins)))).scalars().all()
        }

    # Educational label/band only — UserFundScore.unified_score is deliberately NOT selected.
    score_rows = (
        await db.execute(select(UserFundScore).where(UserFundScore.portfolio_id == pid))
    ).scalars().all()
    score_map = {s.isin: s for s in score_rows}

    enriched: list[EnrichedHolding] = []
    total_invested = 0.0
    total_value = 0.0
    max_as_of: str | None = None
    for h in holdings:
        nav = nav_map.get(h.isin)
        current_nav = nav if nav is not None else (float(h.avg_cost_nav) if h.avg_cost_nav is not None else None)
        units = float(h.units or 0)
        current_value = units * current_nav if current_nav is not None else 0.0
        invested = float(h.invested_amount or 0)  # net-invested (B86)
        fund = fund_meta.get(h.isin)
        score = score_map.get(h.isin)
        as_of = h.as_of_date.isoformat() if h.as_of_date else None

        total_invested += invested
        total_value += current_value
        if as_of and (max_as_of is None or as_of > max_as_of):
            max_as_of = as_of

        enriched.append(
            EnrichedHolding(
                isin=h.isin,
                scheme_name=(fund.fund_name_short or fund.scheme_name) if fund else h.isin,
                category=(fund.sebi_category or fund.category) if fund else None,
                folio_number=h.folio_number or "",
                units=units,
                invested=invested,
                current_nav=current_nav,
                current_value=current_value,
                label=score.verb_label if score else None,
                confidence_band=score.confidence_band if score else None,
                as_of=as_of,
            )
        )

    snap = (
        await db.execute(
            select(MfPortfolioSnapshot)
            .where(MfPortfolioSnapshot.portfolio_id == pid)
            .order_by(MfPortfolioSnapshot.snapshot_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    xirr_pct = float(snap.xirr_pct) if snap and snap.xirr_pct is not None else None

    return PortfolioReadModel(
        holdings=enriched,
        total_invested=total_invested,
        total_value=total_value,
        xirr_pct=xirr_pct,
        as_of=max_as_of,
    )


def holdings_payload(rm: PortfolioReadModel, portfolio_id: str) -> dict:
    """C1 `holdings.list` payload — explicit safe fields only; no score. label/band are the educational
    outputs the client renders as StatusTag/BandRing."""
    return {
        "portfolio_id": portfolio_id,
        "holdings": [
            {
                "isin": h.isin,
                "scheme_name": h.scheme_name,
                "category": h.category,
                "folio_number": h.folio_number,
                "units": h.units,
                "invested_amount": h.invested,  # net-invested (B86)
                "current_value": h.current_value,
                "current_nav": h.current_nav,
                "label": h.label,
                "confidence_band": h.confidence_band,
                "as_of": h.as_of,
            }
            for h in rm.holdings
        ],
    }


def _portfolio_confidence_band(bands: list[str]) -> str | None:
    """The portfolio's overall DATA-confidence band (factual, not a verdict) — conservative aggregation
    of the per-fund confidence bands: low if any fund is low, high only if all are high, else medium.
    None when no fund is scored (the FE renders an insufficient/empty state). This is a data-quality
    descriptor, NOT a recommendation (#1) and NOT a composite score (#2)."""
    if not bands:
        return None
    if "low" in bands:
        return "low"
    if all(b == "high" for b in bands):
        return "high"
    return "medium"


def summary_payload(rm: PortfolioReadModel, portfolio_id: str) -> dict:
    """C2 `portfolio.summary` payload — the user's own calculated facts (value/invested/gain/XIRR, all
    DOM-allowed #2-exempt user numbers) + an overall data-confidence band. NO portfolio composite score
    and NO invented verdict label (that stays a future portfolio.health concept, rule-table-derived)."""
    gain = rm.total_value - rm.total_invested
    gain_pct = (gain / rm.total_invested * 100.0) if rm.total_invested else None
    bands = [h.confidence_band for h in rm.holdings if h.confidence_band]
    return {
        "portfolio_id": portfolio_id,
        "total_value": rm.total_value,
        "total_invested": rm.total_invested,  # net-invested (B86)
        "gain": gain,
        "gain_pct": gain_pct,
        "xirr_pct": rm.xirr_pct,
        "fund_count": len(rm.holdings),
        "funds_scored": len(bands),
        "confidence_band": _portfolio_confidence_band(bands),
        "as_of": rm.as_of,
    }
