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
from dataclasses import dataclass, replace

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
    # ADR-0039 Rule 1 — classified at load time from signals already loaded (zero new storage).
    # data_state:  'ledger_backed' | 'stated_only' | 'unpriced' | 'placeholder'. Defaults to
    #   'ledger_backed' (the read model's FIRST pass has no ledger-flow knowledge yet — see
    #   `_classify_holding` / `classify_holdings`); other callers (holdings.list, risk, allocation,
    #   concentration, diversification) never call the post-step, so this default IS their state.
    # value_basis: 'live_nav' (a recent NAV priced it) | 'cost_fallback' (avg_cost_nav fallback) |
    #   'none' (neither — current_value is 0).
    data_state: str = "ledger_backed"
    value_basis: str = "live_nav"


@dataclass(frozen=True)
class PortfolioReadModel:
    holdings: list[EnrichedHolding]
    total_invested: float
    total_value: float
    xirr_pct: float | None
    as_of: str | None


#: NAV staleness bound (ADR-0039 Rule 1) — matches `_active_holdings_nav_pairs`'s day-change window.
#: A holding with no NAV row inside this window is priced off `avg_cost_nav` (or not at all), never
#: an arbitrarily-old NAV masquerading as "current".
_NAV_STALENESS_DAYS = 30


def _classify_holding(
    isin: str,
    live_nav: float | None,
    avg_cost_nav: float | None,
    folio_number: str,
    covered_keys: set[tuple[str, str]] | None,
) -> tuple[str, str]:
    """ADR-0039 Rule 1 — one holding's `(data_state, value_basis)` from signals `load_portfolio_read_model`
    already has (zero new storage/queries). `live_nav` is the nav_map lookup AFTER the 30-day staleness
    bound (None = no recent NAV); `avg_cost_nav` is the holding's own stored fallback.

    `value_basis`: 'live_nav' (a recent NAV priced it) | 'cost_fallback' (falls back to avg_cost_nav) |
    'none' (neither — current_value is 0).

    `data_state`: checked in priority order — 'placeholder' (isin is an unresolved `CAMS:<code>`,
    regardless of pricing) > 'unpriced' (value_basis isn't live_nav) > ledger-flow presence.
    `covered_keys` is the router's `load_active_holding_flows` key set (every active holding with >= 1
    ledger row); None means the caller doesn't know it yet (the read model's first pass, before the
    router has queried flows) — every remaining holding defaults to 'ledger_backed' (`classify_holdings`
    upgrades this to 'stated_only' once covered_keys is known; other callers — holdings.list, risk,
    allocation, concentration, diversification — never call that post-step, so this default IS their
    state, identical to pre-ADR-0039 behaviour where no such distinction existed)."""
    if live_nav is not None:
        value_basis = "live_nav"
    elif avg_cost_nav is not None:
        value_basis = "cost_fallback"
    else:
        value_basis = "none"

    if isin.startswith("CAMS:"):
        return "placeholder", value_basis
    if value_basis != "live_nav":
        return "unpriced", value_basis
    if covered_keys is not None and (isin, folio_number) not in covered_keys:
        return "stated_only", value_basis
    return "ledger_backed", value_basis


def classify_holdings(
    rm: PortfolioReadModel, covered_keys: set[tuple[str, str]]
) -> PortfolioReadModel:
    """ADR-0039 Rule 1 post-step — the router calls this AFTER `load_active_holding_flows` (once it
    knows which `(isin, folio_number)` keys actually have ledger rows) and BEFORE payload assembly, to
    upgrade every holding still defaulted to 'ledger_backed' into its TRUE 'ledger_backed'/'stated_only'
    split. This avoids a second read-model query — the reclassification is pure Python over data already
    loaded. Placeholder/unpriced holdings are left unchanged (their state is isin/pricing-derived, not
    ledger-derived)."""
    reclassified = [
        replace(
            h,
            data_state=(
                "ledger_backed" if (h.isin, h.folio_number) in covered_keys else "stated_only"
            ),
        )
        if h.data_state == "ledger_backed"
        else h
        for h in rm.holdings
    ]
    return replace(rm, holdings=reclassified)


async def load_portfolio_read_model(
    db: AsyncSession,
    portfolio_id: str,
    covered_keys: set[tuple[str, str]] | None = None,
) -> PortfolioReadModel:
    """Load the owner's holdings (RLS-scoped) enriched with fund name/category + latest NAV + label/band,
    plus portfolio totals. `invested_amount` is read straight from `mf_user_holdings` = net-invested (B86).
    `unified_score` is never queried. Active positions only (`units > 0`) — a fully-redeemed (closed) folio
    from CAS stays a row in the DB but is hidden from this and every downstream view; its history lives in
    the transaction ledger, not here.

    ADR-0039: the NAV lookup is now bounded to the last `_NAV_STALENESS_DAYS` days (previously
    unbounded — an arbitrarily stale NAV row silently priced a holding as "current"). No recent NAV
    → `current_nav` falls back to `avg_cost_nav` (or None) and the holding classifies 'unpriced' /
    'cost_fallback' (`_classify_holding`). `covered_keys` (optional, backward-compatible — every OTHER
    caller of this function omits it and gets the SAME behaviour as before ADR-0039) is the router's
    ledger-flow key set; when given, a holding not in it classifies 'stated_only' instead of the
    'ledger_backed' default. Most callers can't supply it on this first pass (chicken-and-egg: the
    flow query itself needs this function's `active_keys` first) — `classify_holdings` is the
    post-step that upgrades the classification once the router has it."""
    pid = uuid.UUID(portfolio_id)

    holdings = (
        (
            await db.execute(
                select(MfUserHolding).where(
                    MfUserHolding.portfolio_id == pid, MfUserHolding.units > 0
                )
            )
        )
        .scalars()
        .all()
    )
    isins = [h.isin for h in holdings]

    nav_map: dict[str, float] = {}
    fund_meta: dict[str, MfFund] = {}
    if isins:
        nav_rows = await db.execute(
            text(
                "SELECT DISTINCT ON (isin) isin, nav FROM mf.mf_nav_history"
                " WHERE isin = ANY(:isins) AND nav_date >= CURRENT_DATE - INTERVAL '30 days'"
                " ORDER BY isin, nav_date DESC"
            ),
            {"isins": isins},
        )
        nav_map = {r.isin: float(r.nav) for r in nav_rows}
        fund_meta = {
            f.isin: f
            for f in (await db.execute(select(MfFund).where(MfFund.isin.in_(isins))))
            .scalars()
            .all()
        }

    # Educational label/band only — UserFundScore.unified_score is deliberately NOT selected.
    score_rows = (
        (await db.execute(select(UserFundScore).where(UserFundScore.portfolio_id == pid)))
        .scalars()
        .all()
    )
    score_map = {s.isin: s for s in score_rows}

    enriched: list[EnrichedHolding] = []
    total_invested = 0.0
    total_value = 0.0
    max_as_of: str | None = None
    for h in holdings:
        nav = nav_map.get(h.isin)  # already bounded to _NAV_STALENESS_DAYS above
        avg_cost_nav = float(h.avg_cost_nav) if h.avg_cost_nav is not None else None
        current_nav = nav if nav is not None else avg_cost_nav
        units = float(h.units or 0)
        current_value = units * current_nav if current_nav is not None else 0.0
        invested = float(h.invested_amount or 0)  # net-invested (B86)
        fund = fund_meta.get(h.isin)
        score = score_map.get(h.isin)
        as_of = h.as_of_date.isoformat() if h.as_of_date else None
        folio_number = h.folio_number or ""
        data_state, value_basis = _classify_holding(
            h.isin, nav, avg_cost_nav, folio_number, covered_keys
        )

        total_invested += invested
        total_value += current_value
        if as_of and (max_as_of is None or as_of > max_as_of):
            max_as_of = as_of

        enriched.append(
            EnrichedHolding(
                isin=h.isin,
                scheme_name=(fund.fund_name_short or fund.scheme_name) if fund else h.isin,
                category=(fund.sebi_category or fund.category) if fund else None,
                folio_number=folio_number,
                units=units,
                invested=invested,
                current_nav=current_nav,
                current_value=current_value,
                label=score.verb_label if score else None,
                confidence_band=score.confidence_band if score else None,
                as_of=as_of,
                amc=(fund.amc_name if fund else None),
                data_state=data_state,
                value_basis=value_basis,
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
    day_change_map: dict[str, tuple[float, float | None]] | None = None,
) -> dict:
    """C1 `holdings.list` payload — explicit safe fields only; no score. label/band are the educational
    outputs the client renders as StatusTag/BandRing. `xirr_map` (M2.3, keyed by isin+folio_number) is
    the per-holding XIRR from `load_holdings_xirr`; None (honest) for a holding it doesn't cover — the
    user's OWN return, DOM-allowed (#2-exempt). `day_change_map` (CAMS-parity, keyed by isin, from
    `load_holdings_day_change`) is the per-fund today's ₹ move + pct — None/None for a holding with
    fewer than 2 recent NAV dates (honest, matches the portfolio-level `day_change` contract)."""
    xirr_map = xirr_map or {}
    day_change_map = day_change_map or {}
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
                "xirr_pct": xirr_map.get(
                    (h.isin, h.folio_number)
                ),  # M2.3 — None when no ledger history
                "day_change": day_change_map.get(h.isin, (None, None))[0],
                "day_change_pct": day_change_map.get(h.isin, (None, None))[1],
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
    xirr_pct: float | None = None,
    xirr_coverage_pct: int | None = None,
    wt_avg_days: int | None = None,
    reinvested_cost: float = 0.0,
    day_change_as_of: str | None = None,
    investor_name: str | None = None,
    wt_avg_days_coverage_pct: int | None = None,
    day_change_coverage_pct: int | None = None,
    valuation_as_of: str | None = None,
) -> dict:
    """C2 `portfolio.summary` payload — the user's own calculated facts (value/invested/gain/XIRR, all
    DOM-allowed #2-exempt user numbers) + an overall data-confidence band + today's value change.
    NO portfolio composite score and NO invented verdict label (that stays a future portfolio.health concept,
    rule-table-derived). `day_change`/`day_change_pct` are the owner's OWN bottom-up daily move
    (Σ units × ΔNAV from load_day_change, §39.1) — None when no holding has 2 NAV dates yet. The pct
    is computed server-side from the SAME NAV pairs as the ₹ change (the live summary total is a
    different base — don't recompute client-side). `xirr_1y` is `load_windowed_xirr`'s (pct, actual_days)
    (M2.3) — None on cold-start or a too-short window; `xirr_1y_window_days` lets the client refuse to
    label a shrunk window "1Y" (§ FE: only render when >= 360 days).

    CAMS-parity (2026-07-03): `xirr_pct` is now the caller's ledger-based `load_portfolio_xirr` result
    (over the ACTIVE holdings' full flow history + live value) — NOT `rm.xirr_pct` (the stale upload-time
    snapshot number this replaces; that field is no longer read here). `cost_value` = `total_invested`
    (out-of-pocket cash, B86) + `reinvested_cost` (Σ units × nav_or_price over active dividend_reinvest
    rows — CAMS counts a reinvested payout as cost, our net-invested doesn't) — the CAMS-comparable "Cost
    value". `gain_vs_cost`/`gain_vs_cost_pct` are the value-vs-that-cost pair (None pct when cost_value is
    0); `gain`/`gain_pct`/`total_invested` stay the ORIGINAL cash-basis figures — both bases coexist by
    design, never conflated. The hero mini-chart's chip row now renders these SAME live numbers (no
    longer the stored daily-series' last point — one card, one truth, founder-reported 2026-07-03).
    `wt_avg_days` (CAMS "Wt.Avg.Days") is the caller's `portfolio_wt_avg_days` result — a capital-weighted
    average holding period in days, None when no active holding has remaining cost. `day_change_as_of`
    is `load_day_change`'s anchor `nav_date` (ISO string) — the single calendar date `day_change`/
    `day_change_pct` are actually as-of (§ AMFI stages NAV ingest ~23:30 IST; different funds' latest
    NAV can land on different days, so this tells the client which day "today's gain" really covers).
    None whenever day_change itself is None. `investor_name` (2026-07-04, founder-reported hero
    polish) is the caller's already-loaded `auth.users.full_name` for the OWNER's own session
    (DPDP-fine, own name to own session) — None until a CAS upload has captured it
    (`_store_or_validate_identity`). Their `investor_pan` is NEVER passed in or serialized here.

    `xirr_coverage_pct` (Fix 2b, 2026-07-04 XIRR-basis-break incident) is the caller's
    `covered_value_and_coverage_pct` result — the integer % of `total_value` that `xirr_pct`'s ledger
    flows actually explain. None (the common case: full ledger coverage, or no XIRR at all) omits the
    caveat; a partial-coverage portfolio (some holdings ledger-backed, some ledger-less) gets an
    honest number so the client can caveat the XIRR chip instead of silently overstating it.

    ADR-0039 additions (2026-07-04, the hero data-integrity layer):
      `value_priced_pct` — computed HERE from `rm.holdings` (no router wiring needed): the integer %
        of `total_value` carried by holdings priced off a LIVE nav (`value_basis == 'live_nav'`);
        None once it rounds to 100 (nothing to caveat) or `total_value` is 0. A stale/unpriced holding
        (no NAV inside the 30-day bound — `load_portfolio_read_model`) lowers this instead of silently
        inflating `total_value` off an old NAV.
      `invested_missing_count` — count of active holdings with no positive invested amount (a
        holdings-only source that never captured cost) — always present (0 when none), so the FE can
        gate its "some funds missing cost" hint on `> 0`.
      `gain_pct`/`gain_vs_cost_pct` — FIXED sign-flip: None whenever their denominator is <= 0, not
        just == 0 (a NEGATIVE net-invested — a data anomaly, not a real state — used to pass the old
        truthy check and silently flip the sign of an otherwise-correct gain).
      `wt_avg_days_coverage_pct`/`day_change_coverage_pct` — the caller's coverage-% for those two
        metrics (same `basis_coverage_pct` math as `xirr_coverage_pct`, over each metric's OWN covered
        value) — None when that metric is itself None, or coverage is full.
      `valuation_as_of` — the caller's NAV-anchor date used for PRICING (day-change's anchor date when
        available, else the latest on-file NAV date across the holdings) — distinct from the existing
        `as_of` (the statement date) and never conflated with it."""
    gain = rm.total_value - rm.total_invested
    gain_pct = (gain / rm.total_invested * 100.0) if rm.total_invested > 0 else None
    cost_value = rm.total_invested + reinvested_cost
    gain_vs_cost = rm.total_value - cost_value
    gain_vs_cost_pct = (gain_vs_cost / cost_value * 100.0) if cost_value > 0 else None
    bands = [h.confidence_band for h in rm.holdings if h.confidence_band]

    priced_value = sum(h.current_value for h in rm.holdings if h.value_basis == "live_nav")
    value_priced_pct: int | None = None
    if rm.total_value > 0:
        pct = round(priced_value / rm.total_value * 100.0)
        value_priced_pct = None if pct >= 100 else pct
    invested_missing_count = sum(1 for h in rm.holdings if h.invested <= 0 and h.units > 0)

    return {
        "portfolio_id": portfolio_id,
        "total_value": rm.total_value,
        "value_priced_pct": value_priced_pct,  # ADR-0039 — % of total_value on a live NAV; None = 100%
        "total_invested": rm.total_invested,  # net-invested cash basis (B86) — unchanged
        "invested_missing_count": invested_missing_count,  # ADR-0039 — active holdings with no cost
        "cost_value": cost_value,  # CAMS-comparable: cash invested + reinvested payout cost
        "gain": gain,
        "gain_pct": gain_pct,
        "gain_vs_cost": gain_vs_cost,
        "gain_vs_cost_pct": gain_vs_cost_pct,
        "xirr_pct": xirr_pct,  # ledger-based, active-holdings-only (load_portfolio_xirr) — CAMS-parity
        "xirr_coverage_pct": xirr_coverage_pct,  # Fix 2b — % of value xirr_pct covers; None = full
        "xirr_1y_pct": xirr_1y[0]
        if xirr_1y
        else None,  # M2.3 — windowed XIRR, DOM-allowed (#2-exempt)
        "xirr_1y_window_days": xirr_1y[1]
        if xirr_1y
        else None,  # actual days covered (may be < 365)
        "wt_avg_days": wt_avg_days,  # CAMS "Wt.Avg.Days" — capital-weighted avg holding period
        "wt_avg_days_coverage_pct": wt_avg_days_coverage_pct,  # ADR-0039 — % of value wt_avg_days covers
        "day_change": day_change,  # user's own daily ₹ change — DOM-allowed (#2-exempt); None until ≥2 valuation rows
        "day_change_pct": day_change_pct,  # same two rows as day_change; None with it
        "day_change_as_of": day_change_as_of,  # ISO date the anchor above covers; None with day_change
        "day_change_coverage_pct": day_change_coverage_pct,  # ADR-0039 — % of value day_change covers
        "fund_count": len(rm.holdings),
        "funds_scored": len(bands),
        "confidence_band": _portfolio_confidence_band(bands),
        "as_of": rm.as_of,
        "valuation_as_of": valuation_as_of,  # ADR-0039 — NAV pricing anchor date, distinct from as_of
        "investor_name": investor_name,  # owner's own CAS-captured name, DPDP-fine; PAN never included
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
            for m in (await db.execute(select(MfFundMetrics).where(MfFundMetrics.isin.in_(isins))))
            .scalars()
            .all()
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

_MAX_VALUATION_DAYS = 3650  # hard cap: ~10 years of daily points


async def _active_holdings_nav_pairs(
    db: AsyncSession, portfolio_id: str
) -> tuple[list[tuple[str, float]], dict[str, list[tuple[datetime.date, float]]]] | None:
    """Shared plumbing for `load_day_change` / `load_holdings_day_change`: the portfolio's ACTIVE
    (`units > 0`) holdings + each ISIN's two most-recent (nav_date, nav) pairs — latest first, bounded
    to the last 30 days (keeps the window function on recent, uncompressed Timescale chunks — this is
    a hot request-path read; a fund with no NAV in 30 days is honestly excluded, not scanned for).
    `nav_date` is returned (not just `nav`) so a caller can tell which calendar day each fund's NAVs
    actually belong to — needed to anchor "today's gain" to a single date (§ AMFI staggers NAV ingest
    around 23:30 IST, so different funds can update at different times; see `_day_change_anchor`).
    Returns `(holdings, navs_by_isin)`, or None when the portfolio has no active holdings at all."""
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
    # ONE batched query for every holding's two most-recent (nav_date, nav) pairs (never per-ISIN).
    nav_rows = (
        await db.execute(
            text(
                "SELECT isin, nav_date, nav FROM ("
                "  SELECT isin, nav_date, nav, "
                "         ROW_NUMBER() OVER (PARTITION BY isin ORDER BY nav_date DESC) AS rn"
                "  FROM mf.mf_nav_history WHERE isin = ANY(:isins)"
                "    AND nav_date >= CURRENT_DATE - INTERVAL '30 days'"
                ") ranked WHERE rn <= 2 ORDER BY isin, rn"
            ),
            {"isins": isins},
        )
    ).all()
    navs_by_isin: dict[str, list[tuple[datetime.date, float]]] = {}
    for r in nav_rows:
        navs_by_isin.setdefault(r.isin, []).append((r.nav_date, float(r.nav)))
    return [(h.isin, float(h.units or 0)) for h in holdings], navs_by_isin


def _day_change_anchor(
    navs_by_isin: dict[str, list[tuple[datetime.date, float]]],
) -> datetime.date | None:
    """The date-anchor safeguard (founder-reported 2026-07-03): AMFI stages NAV ingest around
    23:30 IST, so during that window different funds' `mf_nav_history` latest row can land on
    different calendar dates. The anchor is the MAX latest `nav_date` across every ISIN that has
    at least one NAV row in the 30-day window; only a fund whose OWN latest date equals the anchor
    may contribute two-most-recent NAVs to a day-change figure — a fund still one NAV behind is
    honestly excluded rather than blended with a different fund's different day (the exact two-day
    blend this anchor exists to prevent). None when no ISIN has any NAV row at all."""
    dates = [navs[0][0] for navs in navs_by_isin.values() if navs]
    return max(dates) if dates else None


async def load_day_change(
    db: AsyncSession, portfolio_id: str
) -> tuple[float, float | None, datetime.date, frozenset[str]] | None:
    """Bottom-up day change (§39.1/§39.5) — Σ units × (NAV_latest − NAV_prev) over the portfolio's
    CURRENT holdings, using the two most-recent NAV dates per ISIN from mf_nav_history. This is the
    RTA/consumer-app method: it reads only today's holdings + NAV history, never a stored valuation
    snapshot, so it is immune BY CONSTRUCTION to a re-upload composition change (the RCA 2026-07-02
    −85% incident — the OLD 2-row-snapshot method compared two different portfolios) and to a same-day
    flow (a SIP purchase never distorts it, because `invested` never enters the formula at all — the
    old flow-adjustment patch it replaces is retired, §39.5). Also removes the "2 rows needed" cold
    start: it works from day one, as soon as 2 NAV dates exist for at least one holding.

    Date-anchored (2026-07-04, founder-reported): AMFI's nightly ingest lands different funds' NAVs
    at different times around 23:30 IST, so the per-ISIN "two most recent dates" can point at two
    DIFFERENT calendar days for two different funds during that window. `_day_change_anchor` picks the
    single latest date any covered ISIN has reached; only a fund whose own latest NAV date equals that
    anchor contributes — a fund still one day behind is excluded (same honest-skip shape as the <2-dates
    rule below), so "today's gain" never silently blends two different trading days.

    pct = change / Σ(units × NAV_prev) × 100 (None when that denominator is 0). Returns None when the
    portfolio has no holdings, or when EVERY holding has fewer than 2 NAV dates / isn't at the anchor
    date (partial coverage across holdings is fine — only funds AT the anchor contribute). Both ₹
    numbers are the user's OWN calculated change — DOM-allowed (#2-exempt user money); the 3rd tuple
    element is the anchor `nav_date` itself (an "as of" display fact, not a score). RLS-scoped: the
    caller must set app.user_id before calling (the router does this via the same session used for
    _owned_portfolio_id). Active positions only (`units > 0`) — a zero-unit (fully-redeemed) row
    contributes 0 to the change anyway, so filtering it out just skips a useless NAV lookup. Shares its
    SQL + pairing logic with `load_holdings_day_change` via `_active_holdings_nav_pairs` (CAMS-parity,
    per-fund today's G/L).

    ADR-0039: the 4th tuple element is the set of ISINs that actually contributed (2 NAV dates AND at
    the anchor) — the router's `day_change_coverage_pct` basis, so a partial-coverage day change (some
    holdings unpriced/behind the anchor) can carry an honest caveat instead of implying full coverage.
    """
    pair = await _active_holdings_nav_pairs(db, portfolio_id)
    if pair is None:
        return None
    holdings, navs_by_isin = pair
    anchor = _day_change_anchor(navs_by_isin)
    if anchor is None:
        return None

    change = 0.0
    prev_value = 0.0
    covered_isins: set[str] = set()
    for isin, units in holdings:
        navs = navs_by_isin.get(isin)
        if not navs or len(navs) < 2 or navs[0][0] != anchor:
            continue  # <2 NAV dates, or this fund hasn't reached the anchor date yet — honest skip
        nav_latest, nav_prev = navs[0][1], navs[1][1]
        change += units * (nav_latest - nav_prev)
        prev_value += units * nav_prev
        covered_isins.add(isin)
    if not covered_isins:
        return None
    pct = (change / prev_value * 100.0) if prev_value else None
    return change, pct, anchor, frozenset(covered_isins)


async def load_holdings_day_change(
    db: AsyncSession, portfolio_id: str
) -> dict[str, tuple[float, float | None]]:
    """Per-holding today's G/L (CAMS-parity) — the SAME bounded two-latest-NAV window AND the SAME
    date-anchor filter as `load_day_change` (shared via `_active_holdings_nav_pairs` /
    `_day_change_anchor`), split per ISIN instead of summed: `{isin: (₹ change, pct)}`. pct is None
    when the previous-NAV value is 0. A holding with fewer than 2 NAV dates in the last 30 days, OR
    whose own latest NAV date is behind the portfolio's anchor date (AMFI's staggered ~23:30 IST
    ingest — see `load_day_change`), is simply absent from the dict (honest partial coverage). A
    portfolio can't hold the same ISIN active in two folios today (B94/#441 dedup); if it ever does,
    whichever folio's row is processed last wins the dict entry and the client (which keys the
    holdings table off ISIN) applies that same value to both rows.
    """
    pair = await _active_holdings_nav_pairs(db, portfolio_id)
    if pair is None:
        return {}
    holdings, navs_by_isin = pair
    anchor = _day_change_anchor(navs_by_isin)
    if anchor is None:
        return {}

    result: dict[str, tuple[float, float | None]] = {}
    for isin, units in holdings:
        navs = navs_by_isin.get(isin)
        if not navs or len(navs) < 2 or navs[0][0] != anchor:
            continue
        nav_latest, nav_prev = navs[0][1], navs[1][1]
        change = units * (nav_latest - nav_prev)
        prev_value = units * nav_prev
        pct = (change / prev_value * 100.0) if prev_value else None
        result[isin] = (change, pct)
    return result


async def load_latest_nav_date(db: AsyncSession, isins: list[str]) -> datetime.date | None:
    """ADR-0039 `valuation_as_of` fallback — the most recent `mf_nav_history` date across `isins`,
    UNBOUNDED (unlike the 30-day pricing bound `load_portfolio_read_model` applies) since this is a
    DISPLAY fact ("as of when did we last see ANY price for these funds"), not a pricing decision.
    Only called when `load_day_change` has no anchor (every holding is unpriced/stale/cold) —
    the common case anchors `valuation_as_of` on `load_day_change`'s own nav_date directly, no extra
    query. None when `isins` is empty or none of them has ever had a NAV row."""
    if not isins:
        return None
    return await db.scalar(
        text("SELECT MAX(nav_date) FROM mf.mf_nav_history WHERE isin = ANY(:isins)"),
        {"isins": isins},
    )


# --- M2.3: windowed (e.g. 1Y) XIRR + per-holding XIRR — unblocked by the transaction ledger --------


async def load_windowed_xirr(
    db: AsyncSession,
    portfolio_id: str,
    end_value: float,
    days: int = 365,
    active_keys: set[tuple[str, str]] | None = None,
) -> tuple[float, int] | None:
    """Windowed XIRR (e.g. "1Y XIRR") from the daily-valuation series + the ledger's real capital
    flows inside the window. Window start = today − `days`. The START value is the LATEST
    `mf_portfolio_daily_values` row ON OR BEFORE that date; if the series doesn't reach back that
    far, the EARLIEST row is used instead and the window honestly SHRINKS to match (never a
    fabricated full year). `end_value` is the caller's already-computed terminal value (the read
    model has it — not re-derived here). Flows are the ledger's B65-signed rows with a non-zero
    amount (the SAME basis as the lifetime XIRR — dividend payouts included) and `txn_date`
    strictly after the start row's date, summed per date (a multi-txn day is one flow).

    ADR-0039 (two mandated fixes): `active_keys` — optional, backward-compatible (None = the
    original unfiltered behaviour every existing caller/test still gets) — when given, flows are
    filtered to the portfolio's ACTIVE `(instrument_id, folio_number)` keys BEFORE grouping by date,
    so a CLOSED position's flow no longer leaks into the window (it used to: the query summed every
    row for the portfolio+date regardless of whether that holding is still held). The router also
    now passes `end_value` = the SAME covered live-priced basis `load_portfolio_xirr` uses (never the
    raw `total_value`) — a caller-side fix, no change needed here for that half.

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
    if active_keys is None:
        # Original unfiltered path — every existing caller/test that doesn't pass active_keys.
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
    else:
        # ADR-0039 — select ungrouped so a closed holding's rows can be dropped BEFORE summing by date.
        rows = (
            await db.execute(
                select(
                    MfPortfolioTransaction.instrument_id,
                    MfPortfolioTransaction.folio_number,
                    MfPortfolioTransaction.txn_date,
                    MfPortfolioTransaction.amount,
                ).where(
                    MfPortfolioTransaction.portfolio_id == pid,
                    MfPortfolioTransaction.txn_date > start_date,
                    MfPortfolioTransaction.amount != 0,
                )
            )
        ).all()
        by_date: dict[datetime.date, float] = {}
        for r in rows:
            if (r.instrument_id, r.folio_number) not in active_keys:
                continue
            by_date[r.txn_date] = by_date.get(r.txn_date, 0.0) + float(r.amount)
        flows = [CashFlow(when=d, amount=amt) for d, amt in by_date.items()]

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
        flows_by_holding.setdefault(key, []).append(
            CashFlow(when=r.txn_date, amount=float(r.amount))
        )

    result: dict[tuple[str, str], float | None] = {}
    for key, current_value in current_values.items():
        flows = flows_by_holding.get(key)
        if not flows:
            result[key] = None
            continue
        result[key] = xirr([*flows, CashFlow(when=today, amount=current_value)])
    return result


# --- CAMS-parity: ledger-based lifetime XIRR / Wt.Avg.Days / dual cost basis (2026-07-03) ----------
#
# CAMS ("Consolidated Account Statement", the RTA app most investors already reconcile against)
# computes these three over the CURRENT (active) folios' full ledger history, not the whole ledger —
# a closed (fully-redeemed) position's flows are excluded. `active_keys` is always
# `{(h.isin, h.folio_number) for h in rm.holdings}` from an already `units > 0`-filtered
# `PortfolioReadModel` (`load_portfolio_read_model`), so "active" here means exactly what it means
# everywhere else in this module.

#: One (instrument_id, folio_number) -> its ledger rows as (txn_date, amount, txn_type, units,
#: nav_or_price) — the shared shape `load_active_holding_flows` returns and `portfolio_wt_avg_days`/
#: `reinvested_dividend_cost` consume.
_GroupedFlows = dict[tuple[str, str], list[tuple[datetime.date, float, str, float, float | None]]]


async def load_portfolio_xirr(
    db: AsyncSession,
    portfolio_id: str,
    covered_value: float,
    active_keys: set[tuple[str, str]],
) -> float | None:
    """Ledger-based lifetime XIRR (CAMS-parity) — replaces the stale upload-time snapshot number the
    summary used to surface (`rm.xirr_pct`, frozen at whatever the last CAS import computed, e.g. the
    founder-reported −29.25% vs CAMS's live 8.68%). Flows = every non-zero-amount ledger row whose
    `(instrument_id, folio_number)` is one of the portfolio's ACTIVE holdings (`active_keys`) — a
    closed position's flow history is EXCLUDED (the CAMS-comparable basis; reopening it is a future
    'closed positions' feature, not this one). `dividend_reinvest` rows carry `amount=0` so the
    non-zero filter already drops them — correct, they're an internal unit bump, not external cash.

    `covered_value` (Fix 2b, 2026-07-04 XIRR-basis-break incident) is a pseudo-terminal inflow dated
    today — but it must be the caller's Σ current_value over only the ACTIVE holdings that actually
    HAVE ledger flows, never the portfolio's full `total_value`. A ledger-less holding (a holdings-only
    source, e.g. a KFin consolidated PDF with no transaction section) contributes NO flow here, so a
    terminal built from the FULL live total would credit the solver with a return on money it never
    saw leave the ledger — the founder-reported 237.83% inflation this fixes. Reuses `xirr()` — no new
    root-finder. None when there are no active flows or the solver can't find a root."""
    if not active_keys:
        return None
    pid = uuid.UUID(portfolio_id)
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
    flows = [
        CashFlow(when=r.txn_date, amount=float(r.amount))
        for r in rows
        if (r.instrument_id, r.folio_number) in active_keys
    ]
    if not flows:
        return None
    today = datetime.date.today()
    return xirr([*flows, CashFlow(when=today, amount=covered_value)])


async def load_active_holding_flows(
    db: AsyncSession,
    portfolio_id: str,
    active_keys: set[tuple[str, str]],
) -> _GroupedFlows:
    """One query for the Wt.Avg.Days + dual-cost-basis pair (CAMS-parity) — every ledger row
    belonging to the portfolio's ACTIVE holdings (`active_keys`), grouped by
    `(instrument_id, folio_number)`. Each row is `(txn_date, amount, txn_type, units, nav_or_price)`.
    Feeds `portfolio_wt_avg_days` (per-holding FIFO, summed before dividing) and
    `reinvested_dividend_cost` (Σ units × nav_or_price over `dividend_reinvest` rows) — both need the
    SAME active-holdings slice, one DB round trip. A closed (fully-redeemed) position's rows are
    excluded (its key isn't in `active_keys`) — that history stays in the ledger for a future
    closed-positions view."""
    if not active_keys:
        return {}
    pid = uuid.UUID(portfolio_id)
    rows = (
        await db.execute(
            select(
                MfPortfolioTransaction.instrument_id,
                MfPortfolioTransaction.folio_number,
                MfPortfolioTransaction.txn_date,
                MfPortfolioTransaction.amount,
                MfPortfolioTransaction.txn_type,
                MfPortfolioTransaction.units,
                MfPortfolioTransaction.nav_or_price,
            ).where(MfPortfolioTransaction.portfolio_id == pid)
        )
    ).all()
    grouped: _GroupedFlows = {}
    for r in rows:
        key = (r.instrument_id, r.folio_number)
        if key not in active_keys:
            continue
        grouped.setdefault(key, []).append(
            (
                r.txn_date,
                float(r.amount),
                r.txn_type,
                float(r.units),
                float(r.nav_or_price) if r.nav_or_price is not None else None,
            )
        )
    return grouped


def basis_coverage_pct(covered_value: float, total_value: float) -> int | None:
    """ADR-0039 — shared coverage-% math, extracted from Fix 2b's threshold so `xirr_coverage_pct`,
    `wt_avg_days_coverage_pct`, and `day_change_coverage_pct` all use ONE rule for "is this coverage
    gap worth a caveat". None when `covered_value` is >= ~99% of `total_value` (full/near-full
    coverage — a negligible rounding-noise gap needs no caveat) or `total_value` <= 0 (nothing to
    divide by); otherwise the integer % of `total_value` that `covered_value` represents."""
    if total_value <= 0 or covered_value >= total_value * 0.99:
        return None
    return round(covered_value / total_value * 100.0)


def covered_value_and_coverage_pct(
    current_value_by_key: dict[tuple[str, str], float],
    covered_keys: set[tuple[str, str]],
    total_value: float,
) -> tuple[float, int | None]:
    """Fix 2b helper (2026-07-04 XIRR-basis-break incident) — the router's one-line glue between
    `load_active_holding_flows`'s grouped keys (`covered_keys` = every active holding with >= 1
    ledger flow — no extra query) and `load_portfolio_xirr`'s `covered_value` terminal.

    Returns `(covered_value, xirr_coverage_pct)`:
      - `covered_value` = Σ `current_value_by_key` over `covered_keys` — the terminal
        `load_portfolio_xirr` must use so the XIRR solver is never credited a return on a
        ledger-less holding's value it never saw a flow for.
      - `xirr_coverage_pct` = `basis_coverage_pct(covered_value, total_value)` — the summary
        payload's honest caveat (never fabricated, never silently swallowed)."""
    covered_value = sum(v for k, v in current_value_by_key.items() if k in covered_keys)
    return covered_value, basis_coverage_pct(covered_value, total_value)


# ADR-0039 FIFO fix — the walk used to key PURELY on amount sign (`amount < 0` opens a lot,
# `amount > 0` consumes one). `dividend_payout` rows are B65-signed POSITIVE (investor-convention
# inflow, same sign as a redemption — see cas.py's CAMS txn-type table) but a payout doesn't reduce
# units or cost basis the way a redemption/switch_out does — walking it as a "redemption" silently
# consumed FIFO lots it had no business touching, understating Wt.Avg.Days. `txn_type` (already
# threaded through every flows tuple but previously ignored — the `_txn_type` name marked that) now
# disambiguates: only these two sets move lots; everything else (dividend_payout, dividend_reinvest
# — amount 0 anyway — or an unrecognised type) leaves lots untouched.
_LOT_OPEN_TYPES = frozenset({"purchase", "sip", "switch_in"})
_LOT_CONSUME_TYPES = frozenset({"redemption", "switch_out"})


def _fifo_remaining_cost_and_weighted_age(
    flows: list[tuple[datetime.date, float, str]], today: datetime.date
) -> tuple[float, float]:
    """FIFO lot walk — the shared innards of `weighted_avg_holding_days`, for ONE (instrument, folio)'s
    chronological ledger flows: a purchase/sip/switch_in (`_LOT_OPEN_TYPES`, amount < 0) opens a lot
    costed at `-amount` on `txn_date`; a redemption/switch_out (`_LOT_CONSUME_TYPES`, amount > 0)
    consumes the OLDEST lots' remaining cost first (partial consumption splits a lot). Any other
    txn_type — `dividend_payout` (a positive inflow but NOT a redemption — ADR-0039 fix) or
    `dividend_reinvest` (amount == 0, B65) — leaves lots untouched; it changes income or units, not
    cost.

    Returns `(Σ remaining_lot_cost, Σ remaining_lot_cost × age_days)` — the RAW pair, so a caller
    combining several holdings' lots into one portfolio figure sums these BEFORE dividing (dividing
    per-holding first and averaging the per-holding results would double-round and mis-weight small
    holdings against large ones — see `portfolio_wt_avg_days`)."""
    lots: list[tuple[float, datetime.date]] = []  # (remaining_cost, purchase_date), oldest-first
    for txn_date, amount, txn_type in sorted(flows, key=lambda f: f[0]):
        if txn_type in _LOT_OPEN_TYPES:
            lots.append((-amount, txn_date))
        elif txn_type in _LOT_CONSUME_TYPES:
            remaining = amount
            kept: list[tuple[float, datetime.date]] = []
            for cost, dt in lots:
                if remaining > 0:
                    consume = min(cost, remaining)
                    cost -= consume
                    remaining -= consume
                if cost > 0:
                    kept.append((cost, dt))
            lots = kept
        # else (dividend_payout / dividend_reinvest / unrecognised) — no cost / no lot effect.
    cost_sum = sum(c for c, _ in lots)
    weighted_sum = sum(c * (today - d).days for c, d in lots)
    return cost_sum, weighted_sum


def weighted_avg_holding_days(
    flows: list[tuple[datetime.date, float, str]], today: datetime.date
) -> int | None:
    """Capital-weighted average holding period in days (CAMS "Wt.Avg.Days") for one (instrument,
    folio)'s ledger flows — greedy FIFO lot accounting (`_fifo_remaining_cost_and_weighted_age`).
    Result = `round(Σ(remaining_lot_cost × age_days) / Σ(remaining_lot_cost))`; None when no cost
    remains (fully redeemed / empty input). For a MULTI-holding PORTFOLIO total, don't average this
    function's per-holding output across holdings — sum `_fifo_remaining_cost_and_weighted_age`'s raw
    pair first (`portfolio_wt_avg_days` does exactly that)."""
    cost_sum, weighted_sum = _fifo_remaining_cost_and_weighted_age(flows, today)
    if cost_sum <= 0:
        return None
    return round(weighted_sum / cost_sum)


def portfolio_wt_avg_days(
    grouped_flows: _GroupedFlows,
    today: datetime.date,
) -> int | None:
    """Portfolio-wide Wt.Avg.Days (CAMS-parity) — runs the FIFO lot walk PER `(instrument, folio)`
    group (a redemption in one holding must never consume another holding's purchase lots — the
    reason this can't just flatten every active flow into one list), then sums every group's raw
    `(remaining_cost, weighted_age)` pair BEFORE dividing once — a holding-level round-then-average
    would double-round and mis-weight small holdings against large ones. None when no active holding
    has any remaining cost (a fresh or fully-redeemed-active-set portfolio — shouldn't normally
    happen since 'active' already means units > 0, but stays honest rather than dividing by zero)."""
    cost_total = weighted_total = 0.0
    for flows in grouped_flows.values():
        three_tuples = [(f[0], f[1], f[2]) for f in flows]
        cost, weighted = _fifo_remaining_cost_and_weighted_age(three_tuples, today)
        cost_total += cost
        weighted_total += weighted
    return round(weighted_total / cost_total) if cost_total > 0 else None


def reinvested_dividend_cost(
    grouped_flows: _GroupedFlows,
) -> float:
    """CAMS "Cost value" add-on — Σ units × nav_or_price over the active holdings' `dividend_reinvest`
    rows (their ledger `amount` is 0 — units-only, cas.py — so this is the only place that cost is
    recovered). A row with a null/zero `nav_or_price` contributes 0 (graceful, never fabricated) —
    e.g. an older CAS statement that didn't print a reinvestment NAV."""
    total = 0.0
    for flows in grouped_flows.values():
        for _txn_date, _amount, txn_type, units, nav_or_price in flows:
            if txn_type == "dividend_reinvest" and nav_or_price:
                total += units * nav_or_price
    return total


async def load_portfolio_valuation_series(
    db: AsyncSession,
    portfolio_id: str,
    days: int = 90,
) -> list[ValuationPoint]:
    """Read the stored daily valuation series for a portfolio.

    Returns up to ``days`` most-recent points ordered ascending by date.
    Empty list when no rows exist yet (cold-start; the Celery task fills this).
    ``days`` is capped at _MAX_VALUATION_DAYS (~10 years).
    """
    pid = uuid.UUID(portfolio_id)
    n = min(max(days, 1), _MAX_VALUATION_DAYS)

    rows = (
        (
            await db.execute(
                select(MfPortfolioDailyValue)
                .where(MfPortfolioDailyValue.portfolio_id == pid)
                .order_by(MfPortfolioDailyValue.valuation_date.desc())
                .limit(n)
            )
        )
        .scalars()
        .all()
    )

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


# --- ADR-0039 Rule 5: serve-time consistency tripwire ------------------------------------------
#
# Pure — no DB, no I/O. The router runs this AFTER assembling the summary payload and logs a single
# structured `hero.integrity` warning listing whatever failed (never blocks serving — a wrong number
# already shipped once this fires; the point is making the NEXT blend regression visible in
# Grafana/logs the day it ships, not gating this request). Tolerances are small-money/rounding
# slack, not correctness holes — the underlying figures already round to 2dp / whole percents.

_MONEY_TOLERANCE = 0.05  # ₹ — covers float/Decimal rounding across the read-model boundary


def hero_integrity_checks(rm: PortfolioReadModel, payload: dict) -> list[str]:
    """ADR-0039 Rule 5 — the summary payload's consistency tripwire. Returns the list of FAILED check
    codes (empty = clean). Codes:
      - `total_value_mismatch` — `payload['total_value']` vs Σ `rm.holdings[].current_value`.
      - `coverage_out_of_range` — any `*_coverage_pct`/`value_priced_pct` key outside [0, 100].
      - `fund_count_mismatch` — `payload['fund_count']` vs `len(rm.holdings)`.
      - `placeholder_live_nav` — a 'placeholder' holding whose `value_basis` is 'live_nav' (an
        unresolved `CAMS:<code>` isin should never have matched a real NAV row).
      - `gain_mismatch` — `payload['gain']` vs `total_value − total_invested`.
    """
    failed: list[str] = []

    holdings_value = sum(h.current_value for h in rm.holdings)
    if abs(payload.get("total_value", 0.0) - holdings_value) >= _MONEY_TOLERANCE:
        failed.append("total_value_mismatch")

    for key in (
        "value_priced_pct",
        "xirr_coverage_pct",
        "wt_avg_days_coverage_pct",
        "day_change_coverage_pct",
    ):
        pct = payload.get(key)
        if pct is not None and not (0 <= pct <= 100):
            failed.append("coverage_out_of_range")
            break

    if payload.get("fund_count") != len(rm.holdings):
        failed.append("fund_count_mismatch")

    if any(h.data_state == "placeholder" and h.value_basis == "live_nav" for h in rm.holdings):
        failed.append("placeholder_live_nav")

    expected_gain = payload.get("total_value", 0.0) - payload.get("total_invested", 0.0)
    if abs(payload.get("gain", 0.0) - expected_gain) >= _MONEY_TOLERANCE:
        failed.append("gain_mismatch")

    return failed
