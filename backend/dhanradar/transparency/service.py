"""
DhanRadar — Transparency service (Plan Group 9 / PU2).

READ-ONLY over persisted tables. Never imports or modifies:
  scoring/engine/*, mf/signals.py, mf/scoring_bridge.py, mf/service.py,
  tasks/*, news/*, insights/*.

Confidence + label are consumed from already-persisted mf.user_fund_scores rows.
NAV freshness is derived from MAX(mf_nav_history.nav_date) per ISIN.
Holdings provenance is derived from mf_user_holdings.source + as_of_date.
unified_score is NEVER selected.

Driver derivation logic:
  The engine's live `flags` list (partial_coverage/stale/low_liquidity/
  provisional_model) IS now persisted to user_fund_scores (G10, migration 0022).
  We render honest qualitative drivers from those flags + confidence_band + NAV
  days-ago, and a directional "what would change this" guidance list (G10
  show-your-working). Both are EDUCATIONAL strings only — no numeric weight, score,
  threshold, or advice ever appears (non-neg #1 + #2). The internal `provisional_model`
  governance flag is deliberately NOT surfaced to users. Rows scored before 0022 have
  flags == NULL/[] and degrade gracefully to the confidence+freshness-only drivers.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.models.mf import (
    MfFund,
    MfNavHistory,
    MfPortfolio,
    MfUserHolding,
    UserFundScore,
)
from dhanradar.transparency.schemas import (
    DataSource,
    FreshnessMeta,
    FundTransparency,
    InsufficientDataRefusal,
    PortfolioTransparencyResponse,
)

logger = logging.getLogger(__name__)

# NAV age threshold (calendar days) above which we flag as stale.
_STALE_THRESHOLD_DAYS = 5

# Source display names — maps the raw `source` column value to a human label.
_HOLDING_SOURCE_NAMES: dict[str, str] = {
    "cas": "CAMS/KARVY CAS",
    "broker": "Broker Import",
    "manual": "Manual Entry",
}
_NAV_SOURCE_NAMES: dict[str, str] = {
    "amfi": "AMFI NAV Feed",
}


# ---------------------------------------------------------------------------
# Plain-language driver derivation (educational; never advisory)
# ---------------------------------------------------------------------------

# Engine flags we deliberately NEVER surface to users. `provisional_model` is an
# internal governance/activation tag (B6) — exposing it would confuse a retail reader
# about a model that is, from their perspective, live. `insufficient_data` is carried
# by the refusal block, not the driver list.
_INTERNAL_ONLY_FLAGS = frozenset({"provisional_model", "insufficient_data"})


def _derive_drivers(
    confidence_band: str, nav_days_ago: int | None, flags: list[str] | None
) -> list[str]:
    """
    Derive qualitative data-quality driver strings from persisted state.

    These are factual statements about coverage and freshness — EDUCATIONAL,
    never advisory. No buy/sell/hold/switch language anywhere. Now flag-aware
    (G10): when the engine recorded WHY confidence was capped (partial coverage,
    low liquidity), we say so honestly instead of only inferring from the band.
    """
    if confidence_band == "insufficient_data":
        return []  # refusal block carries the explanation, not drivers

    drivers: list[str] = []

    if confidence_band == "high":
        drivers.append(
            "Based on 24+ months of NAV history across all signal axes"
        )
    elif confidence_band == "medium":
        drivers.append(
            "Based on available history; category benchmark may be partially available"
        )
    elif confidence_band == "low":
        drivers.append(
            "Limited data coverage — label may update as more history accumulates"
        )

    flagset = set(flags or [])
    if "partial_coverage" in flagset:
        drivers.append(
            "Some signal axes had limited data — this label reflects the signals "
            "that were available"
        )
    if "low_liquidity" in flagset:
        drivers.append(
            "This fund trades less frequently, so liquidity-sensitive signals are "
            "weighted conservatively"
        )

    if nav_days_ago is not None and nav_days_ago > _STALE_THRESHOLD_DAYS:
        drivers.append(
            f"NAV data is {nav_days_ago} day(s) old — this label uses older price data"
        )

    return drivers


def _derive_what_would_change(
    confidence_band: str,
    nav_days_ago: int | None,
    is_stale: bool,
    flags: list[str] | None,
) -> list[str]:
    """
    G10 "what would change this" — directional, educational guidance on what would
    move the label or raise confidence.

    STRICTLY non-advisory and non-numeric: it explains the METHODOLOGY (how the
    category-relative label is formed, what raises confidence) so a reader can see the
    working. It NEVER tells the user to act (no buy/sell/switch), names a number, or
    states a threshold. Empty when confidence_band == insufficient_data (the refusal
    block already explains what data is missing).
    """
    if confidence_band == "insufficient_data":
        return []

    items: list[str] = []

    # Always: the core methodology in plain language — this is the "show your working".
    items.append(
        "This label is category-relative: a sustained change in how this fund's "
        "1-year and 3-year returns compare with its category peers can move it"
    )

    flagset = set(flags or [])

    # Confidence-raising paths (band + the specific reason it was capped).
    if confidence_band in ("low", "medium") or "partial_coverage" in flagset:
        items.append(
            "As more NAV and category history accumulate, the confidence band can rise"
        )
    if "low_liquidity" in flagset:
        items.append(
            "Higher trading liquidity for this fund would ease the conservative "
            "confidence cap applied to liquidity-sensitive signals"
        )
    if is_stale or (nav_days_ago is not None and nav_days_ago > _STALE_THRESHOLD_DAYS):
        items.append(
            "A fresher NAV would re-evaluate this label against the latest prices"
        )

    return items


def _build_refusal() -> InsufficientDataRefusal:
    """Standard PU2 refusal block. Educational framing — honesty signal, not error."""
    return InsufficientDataRefusal(
        reason=(
            "Not enough data to assess this fund yet \u2014 we won\u2019t guess."
        ),
        detail=(
            "A minimum of 14 months of NAV history and category peer data are "
            "needed for a reliable assessment. This label will update automatically "
            "as more data becomes available."
        ),
    )


# ---------------------------------------------------------------------------
# DB query helpers (read-only; unified_score never touched)
# ---------------------------------------------------------------------------

async def _fetch_score_rows(
    db: AsyncSession, portfolio_id: UUID
) -> list[tuple]:
    """
    Fetch latest score per ISIN for a portfolio.

    Returns list of (isin, confidence_band, verb_label, scored_at, model_version, flags).
    unified_score is deliberately excluded from the SELECT list (flags are qualitative
    string tags, not the numeric — safe to select, G10).
    """
    stmt = (
        select(
            UserFundScore.isin,
            UserFundScore.confidence_band,
            UserFundScore.verb_label,
            UserFundScore.scored_at,
            UserFundScore.model_version,
            UserFundScore.flags,
        )
        .where(UserFundScore.portfolio_id == portfolio_id)
        .order_by(UserFundScore.isin, UserFundScore.scored_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    # Deduplicate to latest per ISIN (query is ordered isin ASC, scored_at DESC).
    seen: set[str] = set()
    result = []
    for row in rows:
        if row.isin not in seen:
            seen.add(row.isin)
            result.append(row)
    return result


async def _fetch_fund_meta(
    db: AsyncSession, isins: list[str]
) -> dict[str, tuple[str, str | None]]:
    """Return {isin: (scheme_name, category)} from mf_funds."""
    if not isins:
        return {}
    stmt = select(MfFund.isin, MfFund.scheme_name, MfFund.category).where(
        MfFund.isin.in_(isins)
    )
    rows = (await db.execute(stmt)).all()
    return {r.isin: (r.scheme_name, r.category) for r in rows}


async def _fetch_latest_nav_dates(
    db: AsyncSession, isins: list[str]
) -> dict[str, date | None]:
    """Return {isin: max(nav_date)} from mf_nav_history."""
    if not isins:
        return {}
    stmt = (
        select(MfNavHistory.isin, func.max(MfNavHistory.nav_date).label("latest_nav"))
        .where(MfNavHistory.isin.in_(isins))
        .group_by(MfNavHistory.isin)
    )
    rows = (await db.execute(stmt)).all()
    return {r.isin: r.latest_nav for r in rows}


async def _fetch_holding_meta(
    db: AsyncSession, portfolio_id: UUID, isins: list[str]
) -> dict[str, tuple[str, date | None]]:
    """Return {isin: (source, as_of_date)} from mf_user_holdings (first row per isin)."""
    if not isins:
        return {}
    stmt = (
        select(MfUserHolding.isin, MfUserHolding.source, MfUserHolding.as_of_date)
        .where(
            MfUserHolding.portfolio_id == portfolio_id,
            MfUserHolding.isin.in_(isins),
        )
        .order_by(MfUserHolding.isin, MfUserHolding.updated_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    seen: set[str] = set()
    result: dict[str, tuple[str, date | None]] = {}
    for r in rows:
        if r.isin not in seen:
            seen.add(r.isin)
            result[r.isin] = (r.source, r.as_of_date)
    return result


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def get_portfolio_transparency(
    db: AsyncSession,
    portfolio_id: UUID,
    requesting_user_id: UUID,
) -> PortfolioTransparencyResponse | None:
    """
    Build the full transparency payload for a portfolio.

    Returns None when the portfolio does not exist or does not belong to the
    requesting user (caller must convert None → 404).

    Ownership check: we confirm mf_portfolios.user_id == requesting_user_id
    to prevent IDOR before reading any score data.
    unified_score is NEVER selected anywhere in this function.
    """
    # --- IDOR ownership check ---
    portfolio_row = (
        await db.execute(
            select(MfPortfolio.id, MfPortfolio.user_id).where(
                MfPortfolio.id == portfolio_id
            )
        )
    ).first()
    if portfolio_row is None or portfolio_row.user_id != requesting_user_id:
        return None

    # --- Fetch persisted score rows ---
    score_rows = await _fetch_score_rows(db, portfolio_id)
    isins = [r.isin for r in score_rows]

    # --- Bulk-fetch supporting data ---
    fund_meta, nav_dates, holding_meta = (
        await _fetch_fund_meta(db, isins),
        await _fetch_latest_nav_dates(db, isins),
        await _fetch_holding_meta(db, portfolio_id, isins),
    )

    today = datetime.now(tz=UTC).date()

    funds: list[FundTransparency] = []
    for row in score_rows:
        isin = row.isin
        scheme_name, category = fund_meta.get(isin, (isin, None))

        # Freshness
        latest_nav = nav_dates.get(isin)
        nav_days_ago: int | None = None
        is_stale = False
        if latest_nav is not None:
            nav_days_ago = (today - latest_nav).days
            is_stale = nav_days_ago > _STALE_THRESHOLD_DAYS

        holding_src, holding_as_of = holding_meta.get(isin, ("cas", None))
        freshness = FreshnessMeta(
            nav_as_of=latest_nav.isoformat() if latest_nav else None,
            nav_days_ago=nav_days_ago,
            is_stale=is_stale,
            holdings_as_of=holding_as_of.isoformat() if holding_as_of else None,
        )

        # Sources
        sources: list[DataSource] = []
        nav_src_name = _NAV_SOURCE_NAMES.get("amfi", "AMFI NAV Feed")
        if latest_nav is not None:
            sources.append(DataSource(name=nav_src_name, type="nav_data"))
        holding_src_name = _HOLDING_SOURCE_NAMES.get(holding_src, holding_src.capitalize())
        sources.append(DataSource(name=holding_src_name, type="holdings"))

        # Drivers + "what would change this" + refusal (G10). `row.flags` is NULL for
        # rows scored before migration 0022 → treated as [] (graceful degradation).
        row_flags = list(row.flags or [])
        drivers = _derive_drivers(row.confidence_band, nav_days_ago, row_flags)
        what_would_change = _derive_what_would_change(
            row.confidence_band, nav_days_ago, is_stale, row_flags
        )
        refusal = _build_refusal() if row.confidence_band == "insufficient_data" else None

        funds.append(
            FundTransparency(
                isin=isin,
                scheme_name=scheme_name,
                category=category,
                label=row.verb_label,
                confidence_band=row.confidence_band,
                drivers=drivers,
                what_would_change=what_would_change,
                refusal=refusal,
                sources=sources,
                freshness=freshness,
                scored_at=row.scored_at.isoformat() if row.scored_at else None,
                model_version=row.model_version,
            )
        )

    # Import disclosure constants read-only (B56-f1: same source as dashboard).
    # Late import to avoid circular: transparency → scoring/engine → (anything
    # that imports transparency). Same pattern as dashboard/service.py (B56-f1).
    # Read-only: DISCLOSURE_BUNDLE / NOT_ADVICE / DISCLAIMER_VERSION only.
    from dhanradar.scoring.engine.schemas import (  # noqa: PLC0415
        DISCLAIMER_VERSION,
        DISCLOSURE_BUNDLE,
        NOT_ADVICE,
    )

    return PortfolioTransparencyResponse(
        portfolio_id=str(portfolio_id),
        generated_at=datetime.now(tz=UTC).isoformat(),
        funds=funds,
        disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE,
        disclaimer_version=DISCLAIMER_VERSION,
    )
