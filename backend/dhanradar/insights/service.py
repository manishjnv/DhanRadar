"""
DhanRadar — Portfolio Intelligence service (Plan Group 3).

Reads canonical holdings from `mf.mf_user_holdings` + fund metadata from
`mf.mf_funds`, assembles snapshot.Holding objects, then delegates to the
existing pure math in `dhanradar.mf.snapshot` (reuse, no reinvention).

Mandate: OBSERVE, MEASURE, ANALYZE — NEVER ADVISE.
All framing text produced here is factual ("X% is in Y category") — never prescriptive.

Module isolation: reads only `mf.*` tables. No writes. No cross-module JOINs
into scoring/billing internals. `unified_score` is never selected.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from dhanradar.insights.schemas import (
    CategoryOverlap,
    ConcentrationItem,
    ConcentrationResponse,
    FundPairOverlap,
    OverlapResponse,
)
from dhanradar.mf.snapshot import category_allocation
from dhanradar.scoring.engine.schemas import (
    DISCLAIMER_VERSION,
    DISCLOSURE_BUNDLE,
    NOT_ADVICE,
)

logger = logging.getLogger(__name__)

_EMPTY_COMPLETENESS = "empty"
_PARTIAL_COMPLETENESS = "partial"
_COMPLETE_COMPLETENESS = "complete"


def _parse_uid(user_id: str) -> UUID | None:
    if not isinstance(user_id, str) or user_id == "anonymous":
        return None
    try:
        return UUID(user_id)
    except (ValueError, TypeError):
        return None


def _safe_disclosure() -> dict[str, str]:
    return {
        "disclosure": DISCLOSURE_BUNDLE,
        "not_advice": NOT_ADVICE,
        "disclaimer_version": DISCLAIMER_VERSION,
    }


# ---------------------------------------------------------------------------
# Overlap framing helpers (pure — no I/O)
# ---------------------------------------------------------------------------

def _fund_pair_observation(name_a: str, name_b: str, overlap_pct: float) -> str:
    if overlap_pct >= 60:
        return (
            f"{name_a} and {name_b} are in the same category and account for "
            f"a significant shared allocation ({overlap_pct:.0f}% of total value)."
        )
    if overlap_pct >= 30:
        return (
            f"{name_a} and {name_b} are in the same category and share "
            f"moderate allocation overlap ({overlap_pct:.0f}% of total value)."
        )
    return (
        f"{name_a} and {name_b} are in the same category with "
        f"a small shared allocation ({overlap_pct:.0f}% of total value)."
    )


def _category_observation(category: str, pct: float, fund_count: int) -> str:
    if fund_count > 1:
        return (
            f"{fund_count} funds in your portfolio are in the {category} category, "
            f"accounting for {pct:.1f}% of total value."
        )
    return (
        f"1 fund in your portfolio is in the {category} category, "
        f"accounting for {pct:.1f}% of total value."
    )


# ---------------------------------------------------------------------------
# Concentration framing helpers (pure — no I/O)
# ---------------------------------------------------------------------------

def _concentration_context(dimension: str, name: str, pct: float) -> str:
    """Return an educational context line — factual, never prescriptive."""
    if dimension == "category":
        return (
            f"{pct:.1f}% of your portfolio's current value is in {name} funds. "
            "Category concentration reflects the share of holdings in a single fund type."
        )
    if dimension == "amc":
        return (
            f"{pct:.1f}% of your portfolio's current value is managed by {name}. "
            "AMC concentration shows how much of your holdings is with one fund house."
        )
    # fund dimension
    return (
        f"{name} represents {pct:.1f}% of your portfolio's current value. "
        "Fund concentration shows the weight of a single scheme in the overall portfolio."
    )


# ---------------------------------------------------------------------------
# DB-backed aggregation
# ---------------------------------------------------------------------------

async def get_overlap(db: Any, user_id: str, portfolio_id: str) -> OverlapResponse:
    """
    Build the overlap response for the given portfolio.

    - Verifies portfolio belongs to user (IDOR guard → ValueError on mismatch).
    - Reads holdings + fund metadata.
    - Delegates allocation math to snapshot.category_allocation.
    - Cold-start / single-fund / empty → valid 200 with empty lists.
    """
    from sqlalchemy import select

    from dhanradar.models.mf import MfFund, MfPortfolio, MfUserHolding

    uid = _parse_uid(user_id)
    try:
        pid = UUID(portfolio_id)
    except (ValueError, TypeError):
        pid = None

    disc = _safe_disclosure()

    # Malformed inputs → empty but valid response (no 500)
    if uid is None or pid is None:
        return OverlapResponse(
            portfolio_id=portfolio_id,
            as_of_date=None,
            fund_pairs=[],
            category_distribution=[],
            observation_summary="No portfolio data available.",
            data_completeness=_EMPTY_COMPLETENESS,
            **disc,
        )

    # IDOR guard: portfolio must exist AND belong to this user
    port_result = await db.execute(
        select(MfPortfolio).where(MfPortfolio.id == pid, MfPortfolio.user_id == uid)
    )
    portfolio = port_result.scalar_one_or_none()
    if portfolio is None:
        raise ValueError("portfolio_not_found")

    # Load holdings
    holdings_result = await db.execute(
        select(
            MfUserHolding.isin,
            MfUserHolding.units,
            MfUserHolding.invested_amount,
            MfUserHolding.as_of_date,
        ).where(
            MfUserHolding.portfolio_id == pid,
            MfUserHolding.user_id == uid,
        )
    )
    rows = holdings_result.fetchall()

    if not rows:
        return OverlapResponse(
            portfolio_id=portfolio_id,
            as_of_date=None,
            fund_pairs=[],
            category_distribution=[],
            observation_summary="No holdings found in this portfolio yet.",
            data_completeness=_EMPTY_COMPLETENESS,
            **disc,
        )

    # Resolve fund metadata
    isins = list({r.isin for r in rows})
    fund_meta_result = await db.execute(
        select(MfFund.isin, MfFund.scheme_name, MfFund.category, MfFund.amc_name).where(
            MfFund.isin.in_(isins)
        )
    )
    fund_meta: dict[str, dict[str, str]] = {
        r.isin: {
            "name": r.scheme_name or r.isin,
            "category": r.category or "Uncategorized",
            "amc": r.amc_name or "Unknown",
        }
        for r in fund_meta_result.fetchall()
    }

    as_of_dates = [r.as_of_date for r in rows if r.as_of_date is not None]
    as_of_date_str = max(as_of_dates).isoformat() if as_of_dates else None

    # Build snapshot Holding objects for category_allocation
    from dhanradar.mf.snapshot import Holding

    snapshot_holdings = []
    for r in rows:
        meta = fund_meta.get(r.isin, {"name": r.isin, "category": "Uncategorized", "amc": "Unknown"})
        snapshot_holdings.append(
            Holding(
                isin=r.isin,
                units=float(r.units) if r.units else 0.0,
                invested_amount=float(r.invested_amount) if r.invested_amount else 0.0,
                current_value=float(r.invested_amount) if r.invested_amount else 0.0,
                category=meta["category"],
                cashflows=[],
            )
        )

    # Category allocation (reuse snapshot math)
    alloc = category_allocation(snapshot_holdings)

    # Map category → ISINs in that category
    category_to_funds: dict[str, list[str]] = {}
    for isin in isins:
        cat = fund_meta.get(isin, {}).get("category", "Uncategorized")
        category_to_funds.setdefault(cat, []).append(isin)

    # Build category_distribution
    category_distribution = [
        CategoryOverlap(
            category=cat,
            allocation_pct=pct,
            fund_count=len(category_to_funds.get(cat, [])),
            observation=_category_observation(cat, pct, len(category_to_funds.get(cat, []))),
        )
        for cat, pct in sorted(alloc.items(), key=lambda x: x[1], reverse=True)
    ]

    # Fund pairs in the same category (observable category-level overlap)
    fund_pairs: list[FundPairOverlap] = []
    for cat, cat_isins in category_to_funds.items():
        if len(cat_isins) < 2:
            continue
        cat_alloc_pct = alloc.get(cat, 0.0)
        # Distribute category allocation equally among co-category funds (honest observable estimate)
        per_fund_pct = round(cat_alloc_pct / len(cat_isins), 2)
        for i in range(len(cat_isins)):
            for j in range(i + 1, len(cat_isins)):
                isin_a = cat_isins[i]
                isin_b = cat_isins[j]
                name_a = fund_meta.get(isin_a, {}).get("name", isin_a)
                name_b = fund_meta.get(isin_b, {}).get("name", isin_b)
                fund_pairs.append(
                    FundPairOverlap(
                        fund_a_isin=isin_a,
                        fund_a_name=name_a,
                        fund_b_isin=isin_b,
                        fund_b_name=name_b,
                        overlap_pct=per_fund_pct,
                        observation=_fund_pair_observation(name_a, name_b, per_fund_pct),
                    )
                )

    fund_count = len(isins)
    cat_count = len(alloc)
    summary = (
        f"Your portfolio contains {fund_count} "
        f"{'fund' if fund_count == 1 else 'funds'} "
        f"across {cat_count} {'category' if cat_count == 1 else 'categories'}."
    )
    completeness = _COMPLETE_COMPLETENESS if fund_count > 0 else _EMPTY_COMPLETENESS

    return OverlapResponse(
        portfolio_id=portfolio_id,
        as_of_date=as_of_date_str,
        fund_pairs=fund_pairs,
        category_distribution=category_distribution,
        observation_summary=summary,
        data_completeness=completeness,
        **disc,
    )


async def get_concentration(db: Any, user_id: str, portfolio_id: str) -> ConcentrationResponse:
    """
    Build the concentration response for the given portfolio.

    - Verifies portfolio belongs to user (IDOR guard → ValueError on mismatch).
    - Computes category, AMC, and per-fund concentration as factual percentages.
    - Educational context line per item — never prescriptive.
    - Cold-start / single-fund / empty → valid 200 with empty lists.
    """
    from sqlalchemy import select

    from dhanradar.models.mf import MfFund, MfPortfolio, MfUserHolding

    uid = _parse_uid(user_id)
    try:
        pid = UUID(portfolio_id)
    except (ValueError, TypeError):
        pid = None

    disc = _safe_disclosure()

    if uid is None or pid is None:
        return ConcentrationResponse(
            portfolio_id=portfolio_id,
            as_of_date=None,
            by_category=[],
            by_amc=[],
            by_fund=[],
            observation_summary="No portfolio data available.",
            data_completeness=_EMPTY_COMPLETENESS,
            **disc,
        )

    port_result = await db.execute(
        select(MfPortfolio).where(MfPortfolio.id == pid, MfPortfolio.user_id == uid)
    )
    portfolio = port_result.scalar_one_or_none()
    if portfolio is None:
        raise ValueError("portfolio_not_found")

    holdings_result = await db.execute(
        select(
            MfUserHolding.isin,
            MfUserHolding.units,
            MfUserHolding.invested_amount,
            MfUserHolding.as_of_date,
        ).where(
            MfUserHolding.portfolio_id == pid,
            MfUserHolding.user_id == uid,
        )
    )
    rows = holdings_result.fetchall()

    if not rows:
        return ConcentrationResponse(
            portfolio_id=portfolio_id,
            as_of_date=None,
            by_category=[],
            by_amc=[],
            by_fund=[],
            observation_summary="No holdings found in this portfolio yet.",
            data_completeness=_EMPTY_COMPLETENESS,
            **disc,
        )

    isins = list({r.isin for r in rows})
    fund_meta_result = await db.execute(
        select(MfFund.isin, MfFund.scheme_name, MfFund.category, MfFund.amc_name).where(
            MfFund.isin.in_(isins)
        )
    )
    fund_meta: dict[str, dict[str, str]] = {
        r.isin: {
            "name": r.scheme_name or r.isin,
            "category": r.category or "Uncategorized",
            "amc": r.amc_name or "Unknown",
        }
        for r in fund_meta_result.fetchall()
    }

    as_of_dates = [r.as_of_date for r in rows if r.as_of_date is not None]
    as_of_date_str = max(as_of_dates).isoformat() if as_of_dates else None

    # Compute value per ISIN (use invested_amount as best-effort proxy when no live NAV)
    isin_value: dict[str, float] = {}
    for r in rows:
        v = float(r.invested_amount) if r.invested_amount else 0.0
        isin_value[r.isin] = isin_value.get(r.isin, 0.0) + v

    total_value = sum(isin_value.values())

    if total_value == 0.0:
        return ConcentrationResponse(
            portfolio_id=portfolio_id,
            as_of_date=as_of_date_str,
            by_category=[],
            by_amc=[],
            by_fund=[],
            observation_summary="Holdings exist but cost basis is not yet available.",
            data_completeness=_PARTIAL_COMPLETENESS,
            **disc,
        )

    # --- By category ---
    cat_value: dict[str, float] = {}
    for isin, val in isin_value.items():
        cat = fund_meta.get(isin, {}).get("category", "Uncategorized")
        cat_value[cat] = cat_value.get(cat, 0.0) + val

    by_category = sorted(
        [
            ConcentrationItem(
                name=cat,
                allocation_pct=round(v / total_value * 100, 2),
                context=_concentration_context("category", cat, round(v / total_value * 100, 2)),
            )
            for cat, v in cat_value.items()
        ],
        key=lambda x: x.allocation_pct,
        reverse=True,
    )

    # --- By AMC ---
    amc_value: dict[str, float] = {}
    for isin, val in isin_value.items():
        amc = fund_meta.get(isin, {}).get("amc", "Unknown")
        amc_value[amc] = amc_value.get(amc, 0.0) + val

    by_amc = sorted(
        [
            ConcentrationItem(
                name=amc,
                allocation_pct=round(v / total_value * 100, 2),
                context=_concentration_context("amc", amc, round(v / total_value * 100, 2)),
            )
            for amc, v in amc_value.items()
        ],
        key=lambda x: x.allocation_pct,
        reverse=True,
    )

    # --- By fund ---
    by_fund = sorted(
        [
            ConcentrationItem(
                name=fund_meta.get(isin, {}).get("name", isin),
                allocation_pct=round(val / total_value * 100, 2),
                context=_concentration_context(
                    "fund",
                    fund_meta.get(isin, {}).get("name", isin),
                    round(val / total_value * 100, 2),
                ),
            )
            for isin, val in isin_value.items()
        ],
        key=lambda x: x.allocation_pct,
        reverse=True,
    )

    fund_count = len(isins)
    amc_count = len(amc_value)
    cat_count = len(cat_value)
    summary = (
        f"Your portfolio spans {amc_count} {'AMC' if amc_count == 1 else 'AMCs'} "
        f"and {fund_count} {'fund' if fund_count == 1 else 'funds'} "
        f"across {cat_count} {'category' if cat_count == 1 else 'categories'}."
    )

    return ConcentrationResponse(
        portfolio_id=portfolio_id,
        as_of_date=as_of_date_str,
        by_category=by_category,
        by_amc=by_amc,
        by_fund=by_fund,
        observation_summary=summary,
        data_completeness=_COMPLETE_COMPLETENESS,
        **disc,
    )
