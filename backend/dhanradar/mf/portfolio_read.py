"""Read-model assembler for the portfolio concept endpoints (C1 holdings.list / C2 portfolio.summary).

ONE place that loads a portfolio's holdings enriched with fund metadata + latest NAV + the educational
label/band, plus the portfolio totals. Both concepts HAND-BUILD their payloads from this — only explicit,
#2-safe fields; the raw `unified_score` is NEVER selected (structural #2 guarantee at the builder; the A3
boundary scrub is only a backstop). `invested` is the ledger **net-invested** (B86: the single invested
definition — the B3 projection writes it to `mf_user_holdings.invested_amount`).

Read-only, owner-scoped by RLS (the caller checks ownership first). No score, no advisory verbs.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.config import settings
from dhanradar.mf.risk import risk_adjusted_stats
from dhanradar.mf.snapshot import CashFlow, windowed_xirr, xirr
from dhanradar.mf.valuation import (
    ValuationPoint,
    _dated_flow_adjusted_returns,
    max_drawdown_and_recovery,
    twr_index_series,
    wealth_index,
)
from dhanradar.models.mf import (
    MfFund,
    MfFundMetrics,
    MfPortfolioDailyValue,
    MfPortfolioSnapshot,
    MfPortfolioTransaction,
    MfUserHolding,
    UserFundScore,
)


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
    amc: str | None = None  # fund house — public fact (M2.1 allocation/concentration by AMC)


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
    `unified_score` is never queried. Active positions only (`units > 0`) — a fully-redeemed (closed) folio
    from CAS stays a row in the DB but is hidden from this and every downstream view; its history lives in
    the transaction ledger, not here."""
    pid = uuid.UUID(portfolio_id)

    holdings = (
        await db.execute(
            select(MfUserHolding).where(MfUserHolding.portfolio_id == pid, MfUserHolding.units > 0)
        )
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
                amc=(fund.amc_name if fund else None),
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


def holdings_payload(
    rm: PortfolioReadModel,
    portfolio_id: str,
    xirr_map: dict[tuple[str, str], float | None] | None = None,
) -> dict:
    """C1 `holdings.list` payload — explicit safe fields only; no score. label/band are the educational
    outputs the client renders as StatusTag/BandRing. `xirr_map` (M2.3, keyed by isin+folio_number) is
    the per-holding XIRR from `load_holdings_xirr`; None (honest) for a holding it doesn't cover — the
    user's OWN return, DOM-allowed (#2-exempt)."""
    xirr_map = xirr_map or {}
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
                "xirr_pct": xirr_map.get((h.isin, h.folio_number)),  # M2.3 — None when no ledger history
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


def summary_payload(
    rm: PortfolioReadModel,
    portfolio_id: str,
    day_change: float | None = None,
    day_change_pct: float | None = None,
    xirr_1y: tuple[float, int] | None = None,
) -> dict:
    """C2 `portfolio.summary` payload — the user's own calculated facts (value/invested/gain/XIRR, all
    DOM-allowed #2-exempt user numbers) + an overall data-confidence band + today's value change.
    NO portfolio composite score and NO invented verdict label (that stays a future portfolio.health concept,
    rule-table-derived). `day_change`/`day_change_pct` are the owner's OWN bottom-up daily move
    (Σ units × ΔNAV from load_day_change, §39.1) — None when no holding has 2 NAV dates yet. The pct
    is computed server-side from the SAME NAV pairs as the ₹ change (the live summary total is a
    different base — don't recompute client-side). `xirr_1y` is `load_windowed_xirr`'s (pct, actual_days)
    (M2.3) — None on cold-start or a too-short window; `xirr_1y_window_days` lets the client refuse to
    label a shrunk window "1Y" (§ FE: only render when >= 360 days)."""
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
        "xirr_1y_pct": xirr_1y[0] if xirr_1y else None,  # M2.3 — windowed XIRR, DOM-allowed (#2-exempt)
        "xirr_1y_window_days": xirr_1y[1] if xirr_1y else None,  # actual days covered (may be < 365)
        "day_change": day_change,  # user's own daily ₹ change — DOM-allowed (#2-exempt); None until ≥2 valuation rows
        "day_change_pct": day_change_pct,  # same two rows as day_change; None with it
        "fund_count": len(rm.holdings),
        "funds_scored": len(bands),
        "confidence_band": _portfolio_confidence_band(bands),
        "as_of": rm.as_of,
    }


# --- C3: portfolio risk (M2.3 true series once long enough, else the per-fund fallback) -----------

# Annualised-volatility (%) thresholds → a factual risk band (a standard-measure descriptor, NOT a verdict
# and NOT a composite score). Tuned to typical Indian-MF category vols (debt ~2-5, hybrid ~6-10,
# large-cap ~12-16, mid/small ~18-24+). Applied unchanged to volatility_pct regardless of source
# (the true portfolio series or the value-weighted fallback) — same σ scale; `risk_band_basis`
# says which one it is.
_VOL_BANDS = ((8.0, "low"), (14.0, "moderate"), (22.0, "high"))


@dataclass(frozen=True)
class PortfolioRisk:
    volatility_pct: float | None
    max_drawdown_pct: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    rolling_1y_avg_pct: float | None
    rolling_1y_pct_positive: float | None
    fund_count: int
    funds_with_metrics: int
    as_of: str | None
    # M2.3 (resolves B88) — both default so existing PortfolioRisk(**kw) call sites (tests
    # built before M2.3) keep constructing a valid fallback-shaped instance unmodified.
    # recovery_months: months from the wealth index's deepest trough back to its prior peak.
    recovery_months: int | None = None
    # risk_band_basis: which series volatility_pct/risk_band are actually based on —
    # "portfolio return series" (true, >= _MIN_TRUE_RISK_ROWS daily rows) or the honest
    # fallback "average fund volatility" (value-weighted per-fund proxy, upper-bound).
    risk_band_basis: str = "average fund volatility"


def _vol_band(vol_pct: float | None) -> str | None:
    """Annualised volatility % → a factual risk band (low|moderate|high|very_high). None when no metric."""
    if vol_pct is None:
        return None
    for ceiling, band in _VOL_BANDS:
        if vol_pct < ceiling:
            return band
    return "very_high"


# ~3 months of daily rows; below this, keep the honest weighted-avg fallback
_MIN_TRUE_RISK_ROWS = 90


async def load_portfolio_risk(db: AsyncSession, portfolio_id: str) -> PortfolioRisk:
    """Portfolio-level risk (C3, M2.3 — resolves B88's deferral).

    When the portfolio's OWN daily valuation series (`mf_portfolio_daily_values`, M2.2) has at
    least `_MIN_TRUE_RISK_ROWS` rows: volatility/Sharpe/Sortino/rolling come from
    `risk.risk_adjusted_stats` run on the flow-adjusted return series's wealth index (a real
    portfolio σ, not the value-weighted upper-bound proxy), and max-drawdown/recovery come from
    that same wealth index — `risk_band_basis` = "portfolio return series".

    Below that row count (a young portfolio) — the ORIGINAL, unchanged fallback: the
    **value-weighted** aggregate of the per-fund precomputed STANDARD ratios (`mf_fund_metrics`,
    refreshed nightly), weighted by each holding's current value; Sharpe/Sortino/max-drawdown stay
    None because averaging per-fund RATIOS isn't the portfolio ratio and drawdown doesn't aggregate
    linearly — `risk_band_basis` = "average fund volatility". Either way: only standard ratios,
    NEVER the DhanRadar composite. True alpha/beta still need a benchmark return series (ADR-0033b,
    out of scope here) — the payloads return None for those (the client renders 'coming soon')."""
    rm = await load_portfolio_read_model(db, portfolio_id)
    isins = [h.isin for h in rm.holdings]
    metrics: dict[str, MfFundMetrics] = {}
    if isins:
        metrics = {
            m.isin: m
            for m in (
                await db.execute(select(MfFundMetrics).where(MfFundMetrics.isin.in_(isins)))
            ).scalars().all()
        }

    # ponytail: weights are current_value (units × latest NAV), which falls back to avg_cost_nav for a
    # fund with no live NAV (load_portfolio_read_model) — a minor weight distortion for stale funds.
    # funds_with_metrics surfaces metric coverage; upgrade = require a live NAV or surface NAV-staleness.
    def weighted(attr: str) -> float | None:
        num = den = 0.0
        for h in rm.holdings:
            m = metrics.get(h.isin)
            v = getattr(m, attr, None) if m is not None else None
            if v is not None and h.current_value > 0:
                num += h.current_value * float(v)
                den += h.current_value
        return (num / den) if den > 0 else None

    fund_count = len(rm.holdings)
    funds_with_metrics = sum(1 for h in rm.holdings if h.isin in metrics)

    series = await load_portfolio_valuation_series(db, portfolio_id, days=_MAX_VALUATION_DAYS)
    if len(series) >= _MIN_TRUE_RISK_ROWS:
        flows_by_date = await load_ledger_flows_by_date(db, portfolio_id)
        dated_returns = _dated_flow_adjusted_returns(series, flows_by_date)
        wealth = wealth_index(dated_returns)
        # min_points=1: the product-level gate is `_MIN_TRUE_RISK_ROWS` above; risk_adjusted_stats's
        # own internal n<2 floor still applies. periods_per_year=365: the series is genuinely
        # calendar-daily (a weekend row carries its NAV forward — a real zero return, not a gap).
        stats = risk_adjusted_stats(
            wealth,
            risk_free_annual=settings.RISK_FREE_RATE_ANNUAL,
            min_points=1,
            periods_per_year=365,
        )
        max_dd, recovery_months = max_drawdown_and_recovery(wealth)
        return PortfolioRisk(
            volatility_pct=stats.volatility_pct,
            max_drawdown_pct=max_dd,
            sharpe_ratio=stats.sharpe_ratio,
            sortino_ratio=stats.sortino_ratio,
            rolling_1y_avg_pct=stats.rolling_1y_avg_pct,
            rolling_1y_pct_positive=stats.rolling_1y_pct_positive,
            fund_count=fund_count,
            funds_with_metrics=funds_with_metrics,
            as_of=rm.as_of,
            recovery_months=recovery_months,
            risk_band_basis="portfolio return series",
        )

    return PortfolioRisk(
        # Value-weighted σ (Σwσ) OVERSTATES the true portfolio σ = √(w'Σw) (ignores
        # correlation < 1), so it is an upper-bound proxy, relabelled indicative in the payload.
        volatility_pct=weighted("volatility_pct"),
        # Sharpe/Sortino are RATIOS (a value-weighted average of fund ratios is NOT the portfolio
        # ratio) and max-drawdown does not aggregate linearly (fund drawdowns occur at different
        # times) — don't ship a wrong number → None until the series above is long enough.
        max_drawdown_pct=None,
        sharpe_ratio=None,
        sortino_ratio=None,
        # Rolling RETURNS aggregate by weight (Σw·r is exact for returns) → the weighted rolling
        # AVERAGE is a defensible estimate and is kept. rolling_1y_pct_positive is a per-fund
        # hit-RATE (not a return); value-weighting it is the SAME defect class as Sharpe/σ (the
        # portfolio's % positive depends on correlation/timing), so it stays None in the fallback
        # (the true series gives the real one above).
        rolling_1y_avg_pct=weighted("rolling_1y_avg_pct"),
        rolling_1y_pct_positive=None,
        fund_count=fund_count,
        funds_with_metrics=funds_with_metrics,
        as_of=rm.as_of,
        risk_band_basis="average fund volatility",
    )


def risk_payload(r: PortfolioRisk, portfolio_id: str) -> dict:
    """C3 free `portfolio.risk` — a risk band + volatility + max-drawdown/recovery, with
    `risk_band_basis` naming which series they're actually based on. M2.3 (resolves B88): once the
    portfolio's own daily valuation series is long enough (`load_portfolio_risk`), these are the
    TRUE portfolio figures (`risk_band_basis` = "portfolio return series"); below that row count
    they fall back to the value-weighted AVERAGE fund volatility (an upper-bound proxy,
    `risk_band_basis` = "average fund volatility") with `max_drawdown_pct`/`recovery_months`
    honestly None (the client renders 'coming soon'). `_vol_band` applies the SAME thresholds
    either way — a band over volatility_pct, basis-agnostic."""
    return {
        "portfolio_id": portfolio_id,
        "risk_band": _vol_band(r.volatility_pct),
        "risk_band_basis": r.risk_band_basis,
        "volatility_pct": r.volatility_pct,
        "max_drawdown_pct": r.max_drawdown_pct,
        "recovery_months": r.recovery_months,
        "fund_count": r.fund_count,
        "funds_with_metrics": r.funds_with_metrics,
        "as_of": r.as_of,
    }


def risk_advanced_payload(r: PortfolioRisk, portfolio_id: str) -> dict:
    """C3 plus `portfolio.risk_advanced` — Sharpe/Sortino/rolling-return stats. M2.3 (resolves
    B88): Sharpe/Sortino/rolling_1y_pct_positive are the TRUE portfolio figures once the valuation
    series is long enough (see `load_portfolio_risk`'s `risk_band_basis`); below that they're
    honestly None (rolling_1y_avg_pct still comes from the value-weighted fallback — returns
    aggregate by weight, so that average stays defensible even pre-series). alpha/beta need a
    benchmark return series (ADR-0033b, out of scope) → still None ('coming soon'). No DhanRadar
    composite, ever."""
    return {
        "portfolio_id": portfolio_id,
        "sharpe_ratio": r.sharpe_ratio,
        "sortino_ratio": r.sortino_ratio,
        "rolling_1y_avg_pct": r.rolling_1y_avg_pct,
        "rolling_1y_pct_positive": r.rolling_1y_pct_positive,
        "alpha": None,
        "beta": None,
        "as_of": r.as_of,
    }


# --- M2.1: pure-from-holdings analytics (allocation / concentration / diversification) ------------
#
# All three are hand-built #2-safe payloads from `load_portfolio_read_model` (current value = units ×
# latest NAV). The user's OWN allocation %, holding weights and ₹ values are #2-EXEMPT calculated facts
# (§13) — DOM-allowed; only the DhanRadar COMPOSITE score is forbidden, and none is ever selected here.
# concentration/diversification emit a factual BAND WORD (never a raw seed score) — the SAME shape as C3
# `risk_band` (B87 gates a SCORED concept, not a rule-table band; precedented by risk, not triggered).


def _value_buckets(rm: PortfolioReadModel, attr: str) -> list[dict]:
    """Value-weighted buckets over `current_value`, grouped by holding attribute `attr` (category|amc).
    Returns ``[{bucket, value, weight_pct}]`` sorted by weight desc. Empty when total value is 0. The
    bucket ₹ and % are the user's OWN numbers (§13 #2-exempt) — no DhanRadar composite."""
    totals: dict[str, float] = {}
    for h in rm.holdings:
        bucket = getattr(h, attr) or "Uncategorized"
        totals[bucket] = totals.get(bucket, 0.0) + h.current_value
    total = sum(totals.values())
    if total <= 0:
        return []
    rows = [
        {"bucket": b, "value": round(v, 2), "weight_pct": round(v / total * 100.0, 2)}
        for b, v in totals.items()
    ]
    rows.sort(key=lambda r: r["weight_pct"], reverse=True)
    return rows


def allocation_payload(rm: PortfolioReadModel, portfolio_id: str, by: str = "category") -> dict:
    """`portfolio.allocation` — value-weighted split of the holdings by `category` (default) or `amc`.
    bucket/value/weight_pct are the user's OWN calculated facts (§13, DOM-allowed). `by=sector|cap` are
    DATA-STARVED → empty buckets (the client renders 'coming soon'). No DhanRadar composite."""
    attr = "amc" if by == "amc" else "category"
    buckets = _value_buckets(rm, attr) if by in ("category", "amc") else []
    return {
        "portfolio_id": portfolio_id,
        "by": by,
        "buckets": buckets,
        "total_value": round(rm.total_value, 2),
        "fund_count": len(rm.holdings),
        "as_of": rm.as_of,
    }


# Top single-holding weight (%) → a factual concentration band (a spread descriptor, NOT advice and NOT
# a composite score). v1 heuristic for retail MF portfolios.
# ponytail: top-weight thresholds; upgrade to an HHI/effective-N basis if it misreads in practice.
_CONC_BANDS = ((15.0, "low"), (30.0, "moderate"), (50.0, "high"))


def _concentration_band(top_weight_pct: float | None, fund_count: int) -> str | None:
    """Largest holding's % of total value → concentration band (low|moderate|high|very_high). A single
    fund → very_high. None when the portfolio is empty."""
    if fund_count == 0 or top_weight_pct is None:
        return None
    if fund_count == 1:
        return "very_high"
    for ceiling, band in _CONC_BANDS:
        if top_weight_pct < ceiling:
            return band
    return "very_high"


def concentration_payload(rm: PortfolioReadModel, portfolio_id: str) -> dict:
    """`portfolio.concentration` — how much value sits in the largest fund / fund house. top_fund/top_amc
    weights and the by_amc breakdown are the user's OWN % (§13, DOM-allowed); `band` is a factual
    descriptor. Funds are aggregated by ISIN across folios. No DhanRadar composite is ever selected."""
    total = rm.total_value
    by_amc = _value_buckets(rm, "amc")

    fund_rows: list[dict] = []
    if total > 0:
        agg: dict[str, tuple[str, float]] = {}
        for h in rm.holdings:
            name, val = agg.get(h.isin, (h.scheme_name, 0.0))
            agg[h.isin] = (name, val + h.current_value)
        fund_rows = sorted(
            ({"name": n, "weight_pct": round(v / total * 100.0, 2)} for n, v in agg.values()),
            key=lambda r: r["weight_pct"],
            reverse=True,
        )

    top_fund = fund_rows[0] if fund_rows else None
    top_amc = (
        {"name": by_amc[0]["bucket"], "weight_pct": by_amc[0]["weight_pct"]} if by_amc else None
    )
    band = _concentration_band(top_fund["weight_pct"] if top_fund else None, len(rm.holdings))
    return {
        "portfolio_id": portfolio_id,
        "band": band,
        "top_fund": top_fund,
        "top_amc": top_amc,
        "by_amc": [{"name": r["bucket"], "weight_pct": r["weight_pct"]} for r in by_amc],
        "fund_count": len(rm.holdings),
        "amc_count": len(by_amc),
        "as_of": rm.as_of,
    }


def _diversification_band(cat_weights_pct: list[float], fund_count: int) -> str | None:
    """Category spread → a diversification band (low|medium|high). Derived from the effective number of
    categories (1/HHI over the category-weight fractions) plus the top-category weight — both the user's
    OWN allocation. A rule-table descriptor (high = well spread), NOT a DhanRadar score. None when empty."""
    if fund_count == 0 or not cat_weights_pct:
        return None
    if fund_count == 1:
        return "low"
    fractions = [w / 100.0 for w in cat_weights_pct]
    hhi = sum(f * f for f in fractions)
    eff_n = (1.0 / hhi) if hhi > 0 else 0.0
    top = max(cat_weights_pct)
    if eff_n < 1.5 or top >= 70.0:
        return "low"
    if eff_n < 2.5 or top >= 50.0:
        return "medium"
    return "high"


def diversification_payload(rm: PortfolioReadModel, portfolio_id: str) -> dict:
    """`portfolio.diversification` — a band/word read of how widely the holdings are spread across
    categories (#2: band only, the rule-table inputs are the user's own counts/% — DOM-allowed). The raw
    spread measure is never serialized (same shape as C3 `risk_band`). No DhanRadar composite."""
    cats = _value_buckets(rm, "category")
    cat_weights = [c["weight_pct"] for c in cats]
    band = _diversification_band(cat_weights, len(rm.holdings))
    top = cats[0] if cats else None
    return {
        "portfolio_id": portfolio_id,
        "band": band,
        "category_count": len(cats),
        "top_category": top["bucket"] if top else None,
        "top_category_pct": top["weight_pct"] if top else None,
        "fund_count": len(rm.holdings),
        "as_of": rm.as_of,
    }


# --- M2.2: portfolio.valuation_series and day-change -------------------------

_MAX_VALUATION_DAYS = 1095  # hard cap: ~3 years of daily points


async def load_day_change(db: AsyncSession, portfolio_id: str) -> tuple[float, float | None] | None:
    """Bottom-up day change (§39.1/§39.5) — Σ units × (NAV_latest − NAV_prev) over the portfolio's
    CURRENT holdings, using the two most-recent NAV dates per ISIN from mf_nav_history. This is the
    RTA/consumer-app method: it reads only today's holdings + NAV history, never a stored valuation
    snapshot, so it is immune BY CONSTRUCTION to a re-upload composition change (the RCA 2026-07-02
    −85% incident — the OLD 2-row-snapshot method compared two different portfolios) and to a same-day
    flow (a SIP purchase never distorts it, because `invested` never enters the formula at all — the
    old flow-adjustment patch it replaces is retired, §39.5). Also removes the "2 rows needed" cold
    start: it works from day one, as soon as 2 NAV dates exist for at least one holding.

    pct = change / Σ(units × NAV_prev) × 100 (None when that denominator is 0). Returns None when the
    portfolio has no holdings, or when EVERY holding has fewer than 2 NAV dates (a holding with <2 NAV
    dates simply doesn't contribute — partial coverage across holdings is fine). Both numbers are the
    user's OWN calculated change — DOM-allowed (#2-exempt user money). RLS-scoped: the caller must set
    app.user_id before calling (the router does this via the same session used for _owned_portfolio_id).
    Active positions only (`units > 0`) — a zero-unit (fully-redeemed) row contributes 0 to the change
    anyway, so filtering it out just skips a useless NAV lookup.
    """
    pid = uuid.UUID(portfolio_id)
    holdings = (
        await db.execute(
            select(MfUserHolding.isin, MfUserHolding.units).where(
                MfUserHolding.portfolio_id == pid, MfUserHolding.units > 0
            )
        )
    ).all()
    if not holdings:
        return None

    isins = [h.isin for h in holdings]
    # ONE batched query for every holding's two most-recent NAV dates (never per-ISIN, never per-day).
    # The 30-day bound keeps the window function on recent (uncompressed) Timescale chunks — this is
    # a hot request-path read; a fund with no NAV in 30 days is honestly excluded, not scanned for.
    nav_rows = (
        await db.execute(
            text(
                "SELECT isin, nav FROM ("
                "  SELECT isin, nav, "
                "         ROW_NUMBER() OVER (PARTITION BY isin ORDER BY nav_date DESC) AS rn"
                "  FROM mf.mf_nav_history WHERE isin = ANY(:isins)"
                "    AND nav_date >= CURRENT_DATE - INTERVAL '30 days'"
                ") ranked WHERE rn <= 2 ORDER BY isin, rn"
            ),
            {"isins": isins},
        )
    ).all()
    navs_by_isin: dict[str, list[float]] = {}
    for r in nav_rows:
        navs_by_isin.setdefault(r.isin, []).append(float(r.nav))

    change = 0.0
    prev_value = 0.0
    covered = False
    for h in holdings:
        pair = navs_by_isin.get(h.isin)
        if not pair or len(pair) < 2:
            continue  # <2 NAV dates for this ISIN — honestly excluded, not fabricated
        nav_latest, nav_prev = pair[0], pair[1]
        units = float(h.units or 0)
        change += units * (nav_latest - nav_prev)
        prev_value += units * nav_prev
        covered = True
    if not covered:
        return None
    pct = (change / prev_value * 100.0) if prev_value else None
    return change, pct


# --- M2.3: windowed (e.g. 1Y) XIRR + per-holding XIRR — unblocked by the transaction ledger --------


async def load_windowed_xirr(
    db: AsyncSession,
    portfolio_id: str,
    end_value: float,
    days: int = 365,
) -> tuple[float, int] | None:
    """Windowed XIRR (e.g. "1Y XIRR") from the daily-valuation series + the ledger's real capital
    flows inside the window. Window start = today − `days`. The START value is the LATEST
    `mf_portfolio_daily_values` row ON OR BEFORE that date; if the series doesn't reach back that
    far, the EARLIEST row is used instead and the window honestly SHRINKS to match (never a
    fabricated full year). `end_value` is the caller's already-computed live total_value (the read
    model has it — not re-derived here). Flows are the ledger's B65-signed rows with a non-zero
    amount (the SAME basis as the lifetime XIRR — dividend payouts included) and `txn_date`
    strictly after the start row's date, summed per date (a multi-txn day is one flow).

    Returns (xirr_pct, actual_window_days); None when:
    - the valuation series is empty (cold start — no daily-valuation row at all)
    - `end_value` <= 0
    - the actual window is < 30 days (too short to annualise honestly)
    - the underlying solver can't find a root (delegated to `windowed_xirr`/`xirr`)
    """
    pid = uuid.UUID(portfolio_id)
    today = datetime.date.today()
    window_start = today - datetime.timedelta(days=days)

    start_row = (
        await db.execute(
            select(MfPortfolioDailyValue.valuation_date, MfPortfolioDailyValue.total_value)
            .where(
                MfPortfolioDailyValue.portfolio_id == pid,
                MfPortfolioDailyValue.valuation_date <= window_start,
            )
            .order_by(MfPortfolioDailyValue.valuation_date.desc())
            .limit(1)
        )
    ).first()
    if start_row is None:
        # Series doesn't reach back `days` — fall back to the earliest row (shrunk window).
        start_row = (
            await db.execute(
                select(MfPortfolioDailyValue.valuation_date, MfPortfolioDailyValue.total_value)
                .where(MfPortfolioDailyValue.portfolio_id == pid)
                .order_by(MfPortfolioDailyValue.valuation_date.asc())
                .limit(1)
            )
        ).first()
    if start_row is None:
        return None  # cold start — no valuation series yet

    start_date, start_value = start_row.valuation_date, float(start_row.total_value)
    actual_window_days = (today - start_date).days
    if end_value <= 0 or actual_window_days < 30:
        return None

    # Flow basis = every non-zero signed amount — the SAME rule the lifetime XIRR uses
    # (tasks/mf.py builds its cashflows from `t.amount if t.amount`, no type filter): a
    # dividend payout is a real investor inflow and belongs in a money-weighted return.
    # (_CAPITAL_FLOW_TYPES stays the rule for `invested`, which is a capital measure.)
    flow_rows = (
        await db.execute(
            select(MfPortfolioTransaction.txn_date, func.sum(MfPortfolioTransaction.amount))
            .where(
                MfPortfolioTransaction.portfolio_id == pid,
                MfPortfolioTransaction.txn_date > start_date,
                MfPortfolioTransaction.amount != 0,
            )
            .group_by(MfPortfolioTransaction.txn_date)
        )
    ).all()
    flows = [CashFlow(when=r[0], amount=float(r[1])) for r in flow_rows]

    rate = windowed_xirr(start_value, start_date, flows, end_value, today)
    if rate is None:
        return None
    return rate, actual_window_days


async def load_holdings_xirr(
    db: AsyncSession,
    portfolio_id: str,
    current_values: dict[tuple[str, str], float],
) -> dict[tuple[str, str], float | None]:
    """Per-holding XIRR (M2.3) — ONE ledger query grouped by (isin, folio_number); `instrument_id` IS
    the ISIN for asset_class='mf' (`dhanradar.mf.cas` writes `instrument_id: p.isin`). Each holding's
    own real B65-signed flows (every non-zero amount — the SAME basis as the lifetime XIRR, so a
    dividend payout counts as the investor inflow it is) + a pseudo-terminal inflow of its CURRENT
    value (from `current_values` — the read model's already-computed figure, never re-derived here)
    dated today. Reuses `xirr()` — no new root-finder.

    A holding with no ledger rows maps to None (honest "not enough history"), never a fabricated 0%.
    """
    pid = uuid.UUID(portfolio_id)
    today = datetime.date.today()

    rows = (
        await db.execute(
            select(
                MfPortfolioTransaction.instrument_id,
                MfPortfolioTransaction.folio_number,
                MfPortfolioTransaction.txn_date,
                MfPortfolioTransaction.amount,
            ).where(
                MfPortfolioTransaction.portfolio_id == pid,
                MfPortfolioTransaction.amount != 0,
            )
        )
    ).all()

    flows_by_holding: dict[tuple[str, str], list[CashFlow]] = {}
    for r in rows:
        key = (r.instrument_id, r.folio_number)
        flows_by_holding.setdefault(key, []).append(CashFlow(when=r.txn_date, amount=float(r.amount)))

    result: dict[tuple[str, str], float | None] = {}
    for key, current_value in current_values.items():
        flows = flows_by_holding.get(key)
        if not flows:
            result[key] = None
            continue
        result[key] = xirr([*flows, CashFlow(when=today, amount=current_value)])
    return result


async def load_portfolio_valuation_series(
    db: AsyncSession,
    portfolio_id: str,
    days: int = 90,
) -> list[ValuationPoint]:
    """Read the stored daily valuation series for a portfolio.

    Returns up to ``days`` most-recent points ordered ascending by date.
    Empty list when no rows exist yet (cold-start; the Celery task fills this).
    ``days`` is capped at _MAX_VALUATION_DAYS (~3 years).
    """
    pid = uuid.UUID(portfolio_id)
    n = min(max(days, 1), _MAX_VALUATION_DAYS)

    rows = (
        await db.execute(
            select(MfPortfolioDailyValue)
            .where(MfPortfolioDailyValue.portfolio_id == pid)
            .order_by(MfPortfolioDailyValue.valuation_date.desc())
            .limit(n)
        )
    ).scalars().all()

    # Reverse so result is ascending by date (oldest first).
    return [
        ValuationPoint(
            valuation_date=r.valuation_date,
            total_value=float(r.total_value),
            total_invested=float(r.total_invested),
        )
        for r in reversed(rows)
    ]


async def load_ledger_flows_by_date(
    db: AsyncSession, portfolio_id: str
) -> dict[datetime.date, float] | None:
    """The ledger's REAL net cash flow per date — money into the portfolio positive =
    Σ(−amount) over every non-zero B65 row, dividend payouts included (the same basis as
    XIRR, PR #436). The ONE flow source for every flow-adjusted computation (true risk,
    the TWR index): the invested-delta fallback only tracks CAPITAL types, so a
    dividend-payout day would otherwise read as a fake loss. None when the ledger is
    empty → callers fall back to the invested-delta (equivalent there)."""
    pid = uuid.UUID(portfolio_id)
    flow_rows = (
        await db.execute(
            select(MfPortfolioTransaction.txn_date, func.sum(-MfPortfolioTransaction.amount))
            .where(
                MfPortfolioTransaction.portfolio_id == pid,
                MfPortfolioTransaction.amount != 0,
            )
            .group_by(MfPortfolioTransaction.txn_date)
        )
    ).all()
    return {r[0]: float(r[1]) for r in flow_rows} or None


async def load_first_investment_date(
    db: AsyncSession, portfolio_id: str, series: list[ValuationPoint]
) -> datetime.date | None:
    """The portfolio's earliest ledger transaction date (PR-C money/TWR view) — anchors the FE's
    "All" window and its age-based adaptive period-pill ladder. Falls back to the first row of
    ``series`` (already loaded by the caller — no extra query) when the ledger has no rows yet, e.g.
    a portfolio seeded before the transaction-ledger rollout. None only when BOTH are empty
    (no ledger, no valuation series — a genuine cold start)."""
    pid = uuid.UUID(portfolio_id)
    earliest = await db.scalar(
        select(func.min(MfPortfolioTransaction.txn_date)).where(
            MfPortfolioTransaction.portfolio_id == pid
        )
    )
    if earliest is not None:
        return earliest
    return series[0].valuation_date if series else None


def valuation_series_payload(
    points: list[ValuationPoint],
    portfolio_id: str,
    first_investment_date: datetime.date | None = None,
    flows_by_date: dict[datetime.date, float] | None = None,
) -> dict:
    """`portfolio.valuation_series` payload.

    ``points`` are the owner's own calculated numbers (total_value, total_invested) — DOM-allowed,
    #2-exempt (serialization.py note). `twr_index` (PR-C) is the flow-neutral wealth index
    (`valuation.twr_index_series`, base 100.0 at the FIRST row of `points`) — a deposit/redemption
    never moves it, so it is the correct series for a "your return" line; unlike `value`, a big
    lump-sum deposit does NOT inflate it (the founder-reported +212% fake-gain bug this fixes).
    ``flows_by_date`` (`load_ledger_flows_by_date`) is the ledger's real per-date cash flow — the
    SAME basis the true-risk math uses (payouts included); None falls back to the invested-delta.
    `first_investment_date` is the portfolio's earliest ledger date (`load_first_investment_date`)
    — the FE clamps its "All" window there and derives its adaptive period-pill ladder from the
    resulting age; None only for a portfolio with neither ledger rows nor a valuation series yet.
    No DhanRadar composite score anywhere.
    """
    twr_by_date = dict(twr_index_series(points, flows_by_date=flows_by_date))
    return {
        "portfolio_id": portfolio_id,
        "point_count": len(points),
        "first_investment_date": (
            first_investment_date.isoformat() if first_investment_date else None
        ),
        "points": [
            {
                "date": p.valuation_date.isoformat(),
                "value": p.total_value,
                "invested": p.total_invested,
                "twr_index": round(twr_by_date.get(p.valuation_date, 100.0), 4),
            }
            for p in points
        ],
    }
