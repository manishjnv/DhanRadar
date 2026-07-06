"""
DhanRadar — Portfolio Intelligence router (Plan Group 3).

Mounted at `/api/v1` (no extra prefix).
Paths:
  GET /api/v1/portfolio/{portfolio_id}/overlap          (raw Pydantic — data-starved, untouched)
  GET /api/v1/portfolio/{portfolio_id}/holdings         (C1, A3 envelope)
  GET /api/v1/portfolio/{portfolio_id}/summary          (C2, A3 envelope)
  GET /api/v1/portfolio/{portfolio_id}/risk             (C3, A3 envelope)
  GET /api/v1/portfolio/{portfolio_id}/allocation       (M2.1, A3 envelope)
  GET /api/v1/portfolio/{portfolio_id}/concentration    (M2.1, A3 envelope)
  GET /api/v1/portfolio/{portfolio_id}/diversification  (M2.1, A3 envelope)
  GET /api/v1/portfolio/{portfolio_id}/transactions     (P1, A3 envelope)

Auth: cookie RS256 JWT only (`current_user_or_anonymous` → 401 if anonymous).
IDOR: user sees ONLY their own portfolios — service raises ValueError on mismatch → 404.
No advisory verbs in any response copy. Disclosure bundle on every response (non-neg #9).
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_db
from dhanradar.deps import RequireConsent, UserContext, current_user_or_anonymous
from dhanradar.insights import service
from dhanradar.insights.schemas import MoodContextResponse, OverlapResponse
from dhanradar.mf.portfolio_read import (
    allocation_payload,
    basis_coverage_pct,
    classify_holdings,
    concentration_payload,
    covered_value_and_coverage_pct,
    diversification_payload,
    hero_integrity_checks,
    holdings_payload,
    load_active_holding_flows,
    load_day_change,
    load_first_investment_date,
    load_holdings_day_change,
    load_holdings_elss_lockin,
    load_holdings_xirr,
    load_latest_nav_date,
    load_ledger_flows_by_date,
    load_portfolio_read_model,
    load_portfolio_risk,
    load_portfolio_transactions,
    load_portfolio_valuation_series,
    load_portfolio_xirr,
    load_windowed_xirr,
    portfolio_wt_avg_days,
    reinvested_dividend_cost,
    risk_advanced_payload,
    risk_payload,
    summary_payload,
    transactions_payload,
    valuation_series_payload,
)
from dhanradar.mf.projection import ENGINE_VERSION
from dhanradar.mf.serialization import RequestCtx, is_tier_withheld, serialize_concept
from dhanradar.mf.taxonomy import ELSS_CATEGORY
from dhanradar.models.auth import User
from dhanradar.models.mf import MfPortfolio

logger = logging.getLogger(__name__)

router = APIRouter(tags=["portfolio-intelligence"])

# Block 0.12 — DPDP data-processing gate (fail-closed 403). Every route in this file
# serves personal analytics derived from the user's own uploaded CAS holdings — the
# SAME purpose CAS upload itself requires (mf/router.py's `_require_mf_consent`).
# Called explicitly (not Depends()) right after `_require_auth`, preserving the
# existing 401-then-403 ordering (RequireConsent itself also 401s an anonymous
# caller, but every route here already 401s first via `_require_auth`).
_require_mf_consent = RequireConsent("mf_analytics")


def _require_auth(user: UserContext) -> None:
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")


@router.get(
    "/portfolio/{portfolio_id}/overlap",
    response_model=OverlapResponse,
)
async def portfolio_overlap(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OverlapResponse:
    """
    Factual fund-overlap observations for the user's own portfolio.

    Cold-start / single-fund / no holdings → valid 200 with empty lists, never 404.
    Another user's portfolio_id → 404 (portfolio_not_found).
    Anonymous → 401.
    """
    _require_auth(user)
    await _require_mf_consent(user=user, db=db)
    try:
        return await service.get_overlap(db, user.user_id, portfolio_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")


async def _owned_portfolio_id(db: AsyncSession, portfolio_id: str, user_id: str) -> uuid.UUID:
    """The portfolio UUID iff it belongs to user_id; 404 otherwise (also 404 on a malformed UUID — never
    leaks existence). RLS is the second layer."""
    try:
        pid = uuid.UUID(portfolio_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")
    owned = await db.scalar(
        select(MfPortfolio.id).where(
            MfPortfolio.id == pid, MfPortfolio.user_id == uuid.UUID(user_id)
        )
    )
    if owned is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")
    return pid


@router.get("/portfolio/{portfolio_id}/holdings")
async def portfolio_holdings(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """C1 `holdings.list` — the owner's holdings, enriched (fund name/category, latest-NAV current value)
    and served THROUGH the serialization boundary (§10 layer 8). Each fund carries its educational label +
    confidence band (DOM-allowed) — NEVER the unified_score (hand-built payload + the A3 #2 scrub backstop).
    `invested_amount` is ledger net-invested (B86). `xirr_pct` per holding is M2.3's per-fund XIRR (None
    when the ledger has no history for it — honest, never fabricated). `day_change`/`day_change_pct`
    (CAMS-parity) are the per-fund today's ₹/% move (`load_holdings_day_change`) — None until 2 recent
    NAV dates exist for that ISIN. `lockin` (P2, net new) is the ELSS/tax-saver per-lot lock-in block —
    present only for holdings whose category is the ELSS canonical leaf (`ELSS_CATEGORY`), else null.
    Anonymous → 401; another user's portfolio → 404.
    """
    _require_auth(user)
    await _require_mf_consent(user=user, db=db)
    await _owned_portfolio_id(db, portfolio_id, user.user_id)
    rm = await load_portfolio_read_model(db, portfolio_id)
    current_values = {(h.isin, h.folio_number): h.current_value for h in rm.holdings}
    xirr_map = await load_holdings_xirr(db, portfolio_id, current_values)
    day_change_map = await load_holdings_day_change(db, portfolio_id)
    elss_keys = {(h.isin, h.folio_number) for h in rm.holdings if h.category == ELSS_CATEGORY}
    lockin_map = await load_holdings_elss_lockin(db, portfolio_id, elss_keys)
    return serialize_concept(
        "holdings.list",
        holdings_payload(rm, portfolio_id, xirr_map, day_change_map, lockin_map),
        RequestCtx(tier=user.tier),
        source="cas",
        engine_version=ENGINE_VERSION,
    )


@router.get("/portfolio/{portfolio_id}/transactions")
async def portfolio_transactions(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
    isin: Annotated[str | None, Query(pattern="^[A-Z0-9]{12}$")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """P1 `holding.transactions` — the owner's append-only ledger, newest-first, optionally scoped to
    one fund (`isin`) — the Fund Detail page's Transactions section (FUND_DETAIL_DATA_ARCHITECTURE_PLAN
    §5 row 18, §8). Mirrors the holdings route's auth/IDOR pattern exactly: cookie-auth only
    (401 anonymous), owner-scoped (404 for another user's portfolio_id or a malformed one), served
    THROUGH the A3 boundary — hand-built, ledger-fact-only payload (no DhanRadar composite, ever).
    `limit` is capped at 200 server-side regardless of what's requested; `offset` is simple pagination
    (feeds the frontend's "view all N" affordance via the response's `total`). No cache — personal,
    ledger-fresh on every call.
    """
    _require_auth(user)
    await _require_mf_consent(user=user, db=db)
    await _owned_portfolio_id(db, portfolio_id, user.user_id)
    rows, total = await load_portfolio_transactions(
        db, portfolio_id, isin=isin, limit=limit, offset=offset
    )
    return serialize_concept(
        "holding.transactions",
        transactions_payload(rows, total, portfolio_id, isin, limit, offset),
        RequestCtx(tier=user.tier),
        source="cas",
    )


@router.get("/portfolio/{portfolio_id}/fit")
async def portfolio_fit(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
    isin: Annotated[str, Query(pattern="^[A-Z0-9]{12}$")],
) -> dict:
    """`fund.fit` (item 1) — how the VIEWED fund (`isin`, required) relates to the
    user's own holdings in `portfolio_id`: category allocation already held in that
    fund's category (+ how many held funds share it), a portfolio-value-weighted
    stock-level overlap with the viewed fund's disclosed holdings (+ the same
    per-fund overlaps individually, top 3), and an honest `overlap_coverage` flag
    for whether any held fund actually had disclosure data to compare against.
    OBSERVATION ONLY — never a verdict, never a suggestion (§14.3 compliance
    reframe; see insights.service._portfolio_fit_observation). Mirrors the overlap
    route's auth/IDOR pattern: cookie-auth only (401 anonymous), owner-scoped (404
    for another user's portfolio_id, a malformed one, or an unknown portfolio).
    Cold-start / no holdings / no disclosure data on either side -> valid 200 with
    nulled figures, never 404 for those cases.
    """
    _require_auth(user)
    await _require_mf_consent(user=user, db=db)
    try:
        payload = await service.get_portfolio_fit(db, user.user_id, portfolio_id, isin)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")
    return serialize_concept(
        "fund.fit",
        payload,
        RequestCtx(tier=user.tier),
        source="cas",
    )


@router.get("/portfolio/{portfolio_id}/summary")
async def portfolio_summary(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """C2 `portfolio.summary` — the owner's value/invested/gain/XIRR (their own DOM-allowed numbers) + an
    overall data-confidence band, served THROUGH the boundary. HAND-BUILT: no portfolio composite score and
    no invented verdict label (#1/#2). `total_invested` is ledger net-invested (B86). `xirr_1y_pct` +
    `xirr_1y_window_days` are M2.3's windowed XIRR (None on cold-start or a too-short window — the client
    only labels it "1Y" when the window is >= 360 days). `day_change_as_of` (2026-07-04) is the calendar
    date `day_change`/`day_change_pct` are anchored to — `load_day_change`'s guard against AMFI's
    staggered ~23:30 IST NAV ingest blending two different funds' two different trading days into one
    number; None whenever day_change itself is None.

    CAMS-parity (2026-07-03): `xirr_pct` is now `load_portfolio_xirr` — ledger-based, over the ACTIVE
    holdings' full flow history + live value (replaces the stale upload-time snapshot number). `cost_value`/
    `gain_vs_cost`/`gain_vs_cost_pct` and `wt_avg_days` come from ONE shared active-holdings ledger read
    (`load_active_holding_flows`) feeding `reinvested_dividend_cost` + `portfolio_wt_avg_days`. 401/404 as
    above.

    Fix 2b (2026-07-04 XIRR-basis-break incident, founder-reported 237.83%): `load_portfolio_xirr`'s
    terminal is now `covered_value` — Σ current_value over only the ACTIVE holdings `active_flows`
    actually has ledger rows for (`covered_value_and_coverage_pct`, no extra query) — never the full
    `rm.total_value`, which used to credit the solver with a return on a ledger-less holding's (a
    holdings-only source, e.g. a KFin consolidated PDF) value it never saw a flow for. `xirr_coverage_pct`
    surfaces the honest % of value that basis covers whenever it's a meaningful shortfall (None = full
    coverage, or no XIRR at all).

    ADR-0039 (hero data-integrity layer, 2026-07-04): the same `covered_value`/`active_keys` now also
    fix `xirr_1y` (flows filtered to active keys — a closed position's flow no longer leaks into the
    window — AND the same covered-value terminal, not raw `total_value`) and feed
    `wt_avg_days_coverage_pct` (wt_avg_days is inherently ledger-only, so it shares xirr's covered
    basis). `classify_holdings` upgrades each holding's `data_state` to the TRUE ledger_backed/
    stated_only split now that `active_flows`' keys are known (a pure Python reclassification — no
    second query). `day_change_coverage_pct` mirrors the same pattern over `load_day_change`'s own
    covered-ISIN set. `valuation_as_of` is the NAV pricing anchor (day-change's anchor date, else the
    latest on-file NAV date — `load_latest_nav_date`, only queried on that cold/stale fallback path).
    Finally `hero_integrity_checks` runs a pure consistency tripwire over the assembled payload and
    logs (never blocks) a single structured `hero.integrity` warning if anything looks inconsistent.
    """
    _require_auth(user)
    await _require_mf_consent(user=user, db=db)
    await _owned_portfolio_id(db, portfolio_id, user.user_id)
    rm = await load_portfolio_read_model(db, portfolio_id)
    active_keys = {(h.isin, h.folio_number) for h in rm.holdings}
    active_flows = await load_active_holding_flows(db, portfolio_id, active_keys)
    current_value_by_key = {(h.isin, h.folio_number): h.current_value for h in rm.holdings}
    covered_value, xirr_coverage_pct = covered_value_and_coverage_pct(
        current_value_by_key, set(active_flows), rm.total_value
    )
    # ADR-0039 Rule 1 post-step — now that the ledger-flow keys are known, upgrade each holding's
    # data_state from the load-time 'ledger_backed' default to the true ledger_backed/stated_only split.
    rm = classify_holdings(rm, set(active_flows))

    dc = await load_day_change(
        db, portfolio_id
    )  # (bottom-up ₹, pct, anchor nav_date, covered isins) or None
    xirr_1y = await load_windowed_xirr(db, portfolio_id, covered_value, active_keys=active_keys)
    xirr_pct = await load_portfolio_xirr(db, portfolio_id, covered_value, active_keys)
    # No XIRR at all (no active flows) → no coverage caveat either; nothing to caveat around.
    if xirr_pct is None:
        xirr_coverage_pct = None
    today = datetime.date.today()
    wt_avg_days = portfolio_wt_avg_days(active_flows, today)
    # wt_avg_days is computed ONLY from active_flows (ledger-backed holdings) — the SAME covered_value
    # basis as XIRR, independent of whether the XIRR solver itself found a root.
    wt_avg_days_coverage_pct = (
        basis_coverage_pct(covered_value, rm.total_value) if wt_avg_days is not None else None
    )
    reinvested_cost = reinvested_dividend_cost(active_flows)

    day_change_coverage_pct: int | None = None
    valuation_as_of: str | None = None
    if dc is not None:
        covered_isins = dc[3]
        value_by_isin: dict[str, float] = {}
        for h in rm.holdings:
            value_by_isin[h.isin] = value_by_isin.get(h.isin, 0.0) + h.current_value
        dc_covered_value = sum(v for isin, v in value_by_isin.items() if isin in covered_isins)
        day_change_coverage_pct = basis_coverage_pct(dc_covered_value, rm.total_value)
        valuation_as_of = dc[2].isoformat()
    else:
        latest_nav_date = await load_latest_nav_date(db, [h.isin for h in rm.holdings])
        valuation_as_of = latest_nav_date.isoformat() if latest_nav_date else None

    # Owner's own CAS-captured name (hero polish, 2026-07-04) — their own name to their own
    # session, DPDP-fine. Never their investor_pan (not selected here at all).
    investor_name = await db.scalar(
        select(User.full_name).where(User.id == uuid.UUID(user.user_id))
    )
    payload = summary_payload(
        rm,
        portfolio_id,
        dc[0] if dc else None,
        dc[1] if dc else None,
        xirr_1y,
        xirr_pct=xirr_pct,
        xirr_coverage_pct=xirr_coverage_pct,
        wt_avg_days=wt_avg_days,
        reinvested_cost=reinvested_cost,
        day_change_as_of=dc[2].isoformat() if dc else None,
        investor_name=investor_name,
        wt_avg_days_coverage_pct=wt_avg_days_coverage_pct,
        day_change_coverage_pct=day_change_coverage_pct,
        valuation_as_of=valuation_as_of,
    )
    # ADR-0039 Rule 5 — pure consistency tripwire; logs, never blocks.
    failed_checks = hero_integrity_checks(rm, payload)
    if failed_checks:
        logger.warning("hero.integrity: portfolio=%s failed=%s", portfolio_id, failed_checks)
    return serialize_concept(
        "portfolio.summary",
        payload,
        RequestCtx(tier=user.tier),
        source="computed",
        engine_version=ENGINE_VERSION,
    )


@router.get("/portfolio/{portfolio_id}/risk")
async def portfolio_risk(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
    advanced: bool = False,
) -> dict:
    """C3 `portfolio.risk` (free) — the portfolio's risk band + value-weighted volatility / max-drawdown
    (standard ratios, DOM-allowed) served THROUGH the boundary. `?advanced=true` serves
    `portfolio.risk_advanced` (plus: Sharpe/Sortino/rolling); A3 withholds it for a free caller → HTTP 402
    (the client renders the upgrade state). The DhanRadar risk COMPOSITE is NEVER selected (hand-built;
    standard ratios only). Anonymous → 401; another user's portfolio → 404.
    """
    _require_auth(user)
    await _require_mf_consent(user=user, db=db)
    await _owned_portfolio_id(db, portfolio_id, user.user_id)
    r = await load_portfolio_risk(db, portfolio_id)
    if advanced:
        env = serialize_concept(
            "portfolio.risk_advanced",
            risk_advanced_payload(r, portfolio_id),
            RequestCtx(tier=user.tier),
            source="computed",
            engine_version=ENGINE_VERSION,
        )
        if is_tier_withheld(env):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="tier_upgrade_required"
            )
        return env
    return serialize_concept(
        "portfolio.risk",
        risk_payload(r, portfolio_id),
        RequestCtx(tier=user.tier),
        source="computed",
        engine_version=ENGINE_VERSION,
    )


@router.get("/portfolio/{portfolio_id}/allocation")
async def portfolio_allocation(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
    by: str = "category",
) -> dict:
    """M2.1 `portfolio.allocation` — the owner's value-weighted split by `category` (default) or `amc`,
    served THROUGH the A3 boundary. bucket/value/weight_pct are the user's own calculated facts (§13,
    DOM-allowed); no DhanRadar composite is selected (hand-built). `by=sector|cap` → empty buckets
    ('coming soon', data-starved). Anonymous → 401; another user's portfolio → 404.
    """
    _require_auth(user)
    await _require_mf_consent(user=user, db=db)
    await _owned_portfolio_id(db, portfolio_id, user.user_id)
    rm = await load_portfolio_read_model(db, portfolio_id)
    return serialize_concept(
        "portfolio.allocation",
        allocation_payload(rm, portfolio_id, by),
        RequestCtx(tier=user.tier),
        source="computed",
        engine_version=ENGINE_VERSION,
    )


@router.get("/portfolio/{portfolio_id}/concentration")
async def portfolio_concentration(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """M2.1 `portfolio.concentration` — top-fund / top-AMC weights + an indicative concentration band,
    served THROUGH the A3 boundary (was previously a raw Pydantic response bypassing it). Weights are the
    user's own % (§13, DOM-allowed); the band is a factual descriptor — no DhanRadar composite (hand-built).
    Cold-start / single-fund / no holdings → 200 with null top/empty list. 401/404 as above.
    """
    _require_auth(user)
    await _require_mf_consent(user=user, db=db)
    await _owned_portfolio_id(db, portfolio_id, user.user_id)
    rm = await load_portfolio_read_model(db, portfolio_id)
    return serialize_concept(
        "portfolio.concentration",
        concentration_payload(rm, portfolio_id),
        RequestCtx(tier=user.tier),
        source="computed",
        engine_version=ENGINE_VERSION,
    )


@router.get("/portfolio/{portfolio_id}/diversification")
async def portfolio_diversification(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """M2.1 `portfolio.diversification` — a band/word read of how widely the holdings spread across
    categories, served THROUGH the A3 boundary. #2: band word only — the raw spread measure never
    serializes (same shape as C3 `risk_band`); the category count/top-category % are the user's own
    facts (DOM-allowed). No DhanRadar composite. Anonymous → 401; another user's portfolio → 404.
    """
    _require_auth(user)
    await _require_mf_consent(user=user, db=db)
    await _owned_portfolio_id(db, portfolio_id, user.user_id)
    rm = await load_portfolio_read_model(db, portfolio_id)
    return serialize_concept(
        "portfolio.diversification",
        diversification_payload(rm, portfolio_id),
        RequestCtx(tier=user.tier),
        source="computed",
        engine_version=ENGINE_VERSION,
    )


@router.get(
    "/portfolio/{portfolio_id}/mood-context",
    response_model=MoodContextResponse,
)
async def portfolio_mood_context(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MoodContextResponse:
    """
    Educational mood-context read: current market regime + portfolio structure summary.

    Surfaces THREE deterministic observation strings — no LLM, no advisory verbs,
    no numeric scores. Mood describes conditions; it does not predict direction.

    Cold-start / empty portfolio → valid 200 with honest empty read, never 404.
    Another user's portfolio_id → 404 (portfolio_not_found).
    Anonymous → 401.
    """
    _require_auth(user)
    await _require_mf_consent(user=user, db=db)
    try:
        return await service.get_mood_context(db, user.user_id, portfolio_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")


@router.get("/portfolio/{portfolio_id}/valuation-series")
async def portfolio_valuation_series(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 90,
) -> dict:
    """M2.2 `portfolio.valuation_series` — the owner's daily portfolio total value series.

    Returns up to `days` most-recent data points (default 90, max ~10 years = 3650).
    Each point: {date, value, invested, twr_index} — the owner's OWN calculated numbers
    (DOM-allowed, #2-exempt). `twr_index` (PR-C) is the flow-neutral wealth index anchored to
    `points[0]` — when `days` truncates the series (a caller requesting less than the full ~10y
    window), the index anchors to the first RETURNED row, not the portfolio's absolute start;
    every current FE caller requests the full window (`?days=3650`), so this never truncates in
    practice. `first_investment_date` is the ledger's earliest date (falls back to the first
    row of `points` when the ledger is empty). Empty `points` list on cold-start (no daily
    valuations computed yet — the nightly Celery task fills this). Anonymous → 401; another
    user's portfolio → 404.
    """
    _require_auth(user)
    await _require_mf_consent(user=user, db=db)
    await _owned_portfolio_id(db, portfolio_id, user.user_id)
    points = await load_portfolio_valuation_series(db, portfolio_id, days=days)
    first_investment_date = await load_first_investment_date(db, portfolio_id, points)
    # Real ledger flows for the TWR index — the same basis as the true-risk math (payouts
    # included); None (empty ledger) → the invested-delta fallback inside the payload.
    flows_by_date = await load_ledger_flows_by_date(db, portfolio_id)
    return serialize_concept(
        "portfolio.valuation_series",
        valuation_series_payload(points, portfolio_id, first_investment_date, flows_by_date),
        RequestCtx(tier=user.tier),
        source="computed",
        engine_version=ENGINE_VERSION,
    )
