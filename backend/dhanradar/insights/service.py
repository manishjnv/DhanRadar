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
    FundPairOverlap,
    MoodContextResponse,
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

def _fund_pair_observation(
    name_a: str,
    name_b: str,
    overlap_pct: float,
    shared_names: list[str] | None = None,
) -> str:
    """Return an observational (non-advisory) description of fund pair overlap.

    If shared_names is provided the observation is constituent-level (actual holdings).
    Otherwise it falls back to the category-level approximation.
    """
    if shared_names is not None:
        # Constituent-level: factual shared-holding observation
        if not shared_names:
            return (
                f"{name_a} and {name_b} have no holdings in common in the "
                "latest available monthly disclosure."
            )
        top = shared_names[:3]
        names_str = ", ".join(top)
        suffix = f" and {len(shared_names) - 3} others" if len(shared_names) > 3 else ""
        return (
            f"{name_a} and {name_b} share {len(shared_names)} holding"
            f"{'s' if len(shared_names) != 1 else ''} in common "
            f"({overlap_pct:.1f}% overlap by weight): {names_str}{suffix}."
        )
    # Category-level approximation (fallback)
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
# DB-backed aggregation
#
# NB: `portfolio.concentration` moved to the A3 boundary in M2.1 — see
# `dhanradar.mf.portfolio_read.concentration_payload` + `insights/router.py`. The old
# `get_concentration` / `_concentration_context` (raw Pydantic, bypassing the boundary) were removed.
# `get_overlap` stays here (data-starved; constituent logic kept for when that feed lands).
# ---------------------------------------------------------------------------

_CONSTITUENT_COMPLETENESS = "constituent_data"


def _compute_constituent_overlap(
    constituents: dict[str, list[tuple[str | None, str, float]]],
) -> dict[tuple[str, str], tuple[float, list[str]]]:
    """Compute pairwise stock-level overlap from constituent holdings.

    Args:
        constituents: isin → list of (constituent_isin, constituent_name, weight_pct)

    Returns:
        (isin_a, isin_b) → (overlap_pct, shared_constituent_names sorted by min-weight desc)

    overlap_pct = Σ min(weight_A, weight_B) for all shared constituent_isin values.
    Only constituents with a non-null constituent_isin are matched — name-only rows
    are excluded from the overlap calculation (matching by name is ambiguous).
    """
    result: dict[tuple[str, str], tuple[float, list[str]]] = {}
    isins = list(constituents.keys())
    for i in range(len(isins)):
        for j in range(i + 1, len(isins)):
            isin_a, isin_b = isins[i], isins[j]
            # Build constituent_isin → (name, weight) maps; skip null-isin rows
            map_a = {
                c_isin: (name, w)
                for c_isin, name, w in constituents[isin_a]
                if c_isin is not None
            }
            map_b = {
                c_isin: (name, w)
                for c_isin, name, w in constituents[isin_b]
                if c_isin is not None
            }
            shared = set(map_a) & set(map_b)
            if not shared:
                result[(isin_a, isin_b)] = (0.0, [])
                continue
            items = sorted(
                [(cid, min(map_a[cid][1], map_b[cid][1]), map_a[cid][0]) for cid in shared],
                key=lambda x: x[1],
                reverse=True,
            )
            overlap_pct = round(sum(w for _, w, _ in items), 2)
            shared_names = [name for _, _, name in items]
            result[(isin_a, isin_b)] = (overlap_pct, shared_names)
    return result


async def get_overlap(db: Any, user_id: str, portfolio_id: str) -> OverlapResponse:
    """
    Build the overlap response for the given portfolio.

    - Verifies portfolio belongs to user (IDOR guard → ValueError on mismatch).
    - Reads holdings + fund metadata.
    - If mf_fund_constituents data covers ≥2 portfolio funds: computes actual
      stock-level pairwise overlap (sum of min(weight_A, weight_B) for shared
      constituent_isin values). data_completeness = "constituent_data".
    - Fallback when constituent data absent/covers <2 funds: distributes
      category allocation equally among co-category funds (existing behavior).
      data_completeness = "complete" (legacy).
    - Cold-start / single-fund / empty → valid 200 with empty lists.
    """
    from sqlalchemy import func as sqlfunc
    from sqlalchemy import select

    from dhanradar.models.mf import MfFund, MfFundConstituent, MfPortfolio, MfUserHolding

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

    # Build category_distribution (always present regardless of overlap method)
    category_distribution = [
        CategoryOverlap(
            category=cat,
            allocation_pct=pct,
            fund_count=len(category_to_funds.get(cat, [])),
            observation=_category_observation(cat, pct, len(category_to_funds.get(cat, []))),
        )
        for cat, pct in sorted(alloc.items(), key=lambda x: x[1], reverse=True)
    ]

    # ------------------------------------------------------------------
    # Constituent-level overlap (preferred path — ADR-0033(a))
    # Query the latest as_of_month for each portfolio ISIN from the
    # mf_fund_constituents table. If ≥2 funds have constituent data,
    # compute actual stock-level overlap; otherwise fall back to category.
    # ------------------------------------------------------------------
    fund_pairs: list[FundPairOverlap] = []
    completeness: str

    # For each portfolio ISIN, find the most recent disclosure month
    latest_months_result = await db.execute(
        select(MfFundConstituent.isin, sqlfunc.max(MfFundConstituent.as_of_month).label("latest"))
        .where(MfFundConstituent.isin.in_(isins))
        .group_by(MfFundConstituent.isin)
    )
    latest_months: dict[str, object] = {
        r.isin: r.latest for r in latest_months_result.fetchall()
    }

    covered_isins = list(latest_months.keys())

    if len(covered_isins) >= 2:
        # Fetch constituents filtered to each ISIN's own latest disclosure month.
        # tuple_(isin, as_of_month).in_(pairs) is cleaner than a LATERAL JOIN.
        from sqlalchemy import tuple_ as sql_tuple
        isin_month_pairs = [(isin, latest_months[isin]) for isin in covered_isins]
        filtered_result = await db.execute(
            select(
                MfFundConstituent.isin,
                MfFundConstituent.constituent_isin,
                MfFundConstituent.constituent_name,
                MfFundConstituent.weight_pct,
            ).where(
                sql_tuple(MfFundConstituent.isin, MfFundConstituent.as_of_month).in_(
                    isin_month_pairs
                )
            )
        )
        # Rebuild from the filtered result
        constituent_rows = {isin: [] for isin in covered_isins}
        for r in filtered_result.fetchall():
            constituent_rows[r.isin].append(
                (r.constituent_isin, r.constituent_name, float(r.weight_pct or 0.0))
            )

        # Only include ISINs that actually have constituent rows
        constituent_rows = {k: v for k, v in constituent_rows.items() if v}

        if len(constituent_rows) >= 2:
            overlap_map = _compute_constituent_overlap(constituent_rows)
            all_isins = list(constituent_rows.keys())
            for i in range(len(all_isins)):
                for j in range(i + 1, len(all_isins)):
                    isin_a, isin_b = all_isins[i], all_isins[j]
                    overlap_pct, shared_names = overlap_map.get((isin_a, isin_b), (0.0, []))
                    name_a = fund_meta.get(isin_a, {}).get("name", isin_a)
                    name_b = fund_meta.get(isin_b, {}).get("name", isin_b)
                    fund_pairs.append(
                        FundPairOverlap(
                            fund_a_isin=isin_a,
                            fund_a_name=name_a,
                            fund_b_isin=isin_b,
                            fund_b_name=name_b,
                            overlap_pct=overlap_pct,
                            observation=_fund_pair_observation(
                                name_a, name_b, overlap_pct, shared_names
                            ),
                        )
                    )
            completeness = _CONSTITUENT_COMPLETENESS
            logger.info(
                "overlap: constituent path — covered=%d/%d funds",
                len(constituent_rows),
                len(isins),
            )
        else:
            # Covered ISINs found but no actual rows after month filter — fall back
            fund_pairs, completeness = _category_fund_pairs(
                category_to_funds, alloc, fund_meta
            )
    else:
        # Constituent data absent — fall back to category-level
        fund_pairs, completeness = _category_fund_pairs(
            category_to_funds, alloc, fund_meta
        )

    fund_count = len(isins)
    cat_count = len(alloc)
    summary = (
        f"Your portfolio contains {fund_count} "
        f"{'fund' if fund_count == 1 else 'funds'} "
        f"across {cat_count} {'category' if cat_count == 1 else 'categories'}."
    )

    return OverlapResponse(
        portfolio_id=portfolio_id,
        as_of_date=as_of_date_str,
        fund_pairs=fund_pairs,
        category_distribution=category_distribution,
        observation_summary=summary,
        data_completeness=completeness,
        **disc,
    )


def _category_fund_pairs(
    category_to_funds: dict[str, list[str]],
    alloc: dict[str, float],
    fund_meta: dict[str, dict[str, str]],
) -> tuple[list[FundPairOverlap], str]:
    """Build fund pairs using category-level overlap approximation (fallback path)."""
    fund_pairs: list[FundPairOverlap] = []
    for cat, cat_isins in category_to_funds.items():
        if len(cat_isins) < 2:
            continue
        cat_alloc_pct = alloc.get(cat, 0.0)
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
    completeness = _COMPLETE_COMPLETENESS if fund_pairs or category_to_funds else _EMPTY_COMPLETENESS
    return fund_pairs, completeness


# ---------------------------------------------------------------------------
# Portfolio Fit (item 1, Fund Detail P2) — a VIEWED fund vs. the user's OWN
# holdings, aggregated to a single overlap figure (not the pairwise-among-
# held-funds shape get_overlap returns). Observational only — see
# _portfolio_fit_observation's docstring for the compliance framing rule.
# ---------------------------------------------------------------------------

_NO_CONSTITUENT_DATA_COMPLETENESS = "no_constituent_data"


def _portfolio_fit_observation(
    overlap_pct: float | None, category_allocation_pct: float | None
) -> str:
    """Factual, non-advisory description of how a viewed fund relates to the user's
    OWN holdings. NEVER a verdict ("good fit"/"avoid"/"diversify") and NEVER a
    suggestion ("consider"/"should"/"you may want to") — states only what the
    numbers are, mirroring _category_observation / _fund_pair_observation's framing
    discipline. Compliance-critical copy — flag for review on any change.
    """
    parts: list[str] = []
    if category_allocation_pct is not None:
        parts.append(
            f"{category_allocation_pct:.1f}% of your portfolio's value is already in "
            "this fund's category."
        )
    if overlap_pct is not None:
        parts.append(
            f"This fund's disclosed holdings overlap with your existing funds' "
            f"holdings by {overlap_pct:.1f}% (by weight, where both sides have "
            "disclosure data)."
        )
    if not parts:
        return "Not enough disclosed-holdings data yet to compare this fund with your portfolio."
    return " ".join(parts)


async def get_portfolio_fit(db: Any, user_id: str, portfolio_id: str, isin: str) -> dict:
    """`fund.fit` (item 1) — how a VIEWED fund (`isin`) relates to the user's own
    holdings in `portfolio_id`. Independent facts, never combined into a verdict:
      - category_allocation_pct / fund_count_in_category: % of the user's portfolio
        value already in the viewed fund's own scheme category, and how many of the
        user's own held funds share that category (reuses category_allocation()'s
        underlying fund_categories map — no second query for the count).
      - overlap_pct: portfolio-value-weighted average of each held fund's stock-
        level overlap with the viewed fund's latest disclosed holdings (adapts
        _compute_constituent_overlap's pairwise math to a one-vs-many aggregate).
        Only held funds that themselves have constituent data are included in the
        weighted average; excluded funds are never estimated or scaled for (§8.4).
      - overlap (top 3, 2026-07-06 P2): the SAME per-fund pairwise overlap the
        aggregate above sums over — individually retained (not reimplemented),
        sorted desc, capped at 3. Zero-overlap funds are omitted (not informative).
      - overlap_coverage (2026-07-06 P2): honest completeness signal — True only
        when at least one held fund actually had usable constituent data to
        compare against (mirrors data_completeness == constituent_data).
        Constituent disclosures only exist for a handful of top-10 AMCs today, so
        most portfolios will read False — surfaced explicitly rather than left
        for the client to infer from an empty overlap list.

    Same 200-with-empty-shape / IDOR contract as get_overlap: malformed portfolio_id
    or uid -> empty shape; portfolio not owned by user -> ValueError (caller maps to
    404); no holdings -> empty shape. The viewed fund itself is excluded from its own
    overlap computation if already held.
    """
    from sqlalchemy import func as sqlfunc
    from sqlalchemy import select
    from sqlalchemy import tuple_ as sql_tuple

    from dhanradar.models.mf import MfFund, MfFundConstituent, MfPortfolio, MfUserHolding

    uid = _parse_uid(user_id)
    try:
        pid = UUID(portfolio_id)
    except (ValueError, TypeError):
        pid = None

    def _shape(
        completeness: str,
        observation: str,
        *,
        overlap_pct: float | None = None,
        category_allocation_pct: float | None = None,
        fund_count_in_category: int | None = None,
        overlap: list[dict[str, Any]] | None = None,
    ) -> dict:
        return {
            "portfolio_id": portfolio_id,
            "viewed_isin": isin,
            "overlap_pct": overlap_pct,
            "category_allocation_pct": category_allocation_pct,
            "fund_count_in_category": fund_count_in_category,
            "overlap": overlap or [],
            "overlap_coverage": completeness == _CONSTITUENT_COMPLETENESS,
            "data_completeness": completeness,
            "observation": observation,
        }

    if uid is None or pid is None:
        return _shape(_EMPTY_COMPLETENESS, "No portfolio data available.")

    port_result = await db.execute(
        select(MfPortfolio).where(MfPortfolio.id == pid, MfPortfolio.user_id == uid)
    )
    if port_result.scalar_one_or_none() is None:
        raise ValueError("portfolio_not_found")

    holdings_result = await db.execute(
        select(MfUserHolding.isin, MfUserHolding.invested_amount).where(
            MfUserHolding.portfolio_id == pid, MfUserHolding.user_id == uid
        )
    )
    rows = holdings_result.fetchall()
    if not rows:
        return _shape(_EMPTY_COMPLETENESS, "No holdings found in this portfolio yet.")

    invested_by_isin: dict[str, float] = {}
    for r in rows:
        invested_by_isin[r.isin] = invested_by_isin.get(r.isin, 0.0) + float(
            r.invested_amount or 0.0
        )
    total_invested = sum(invested_by_isin.values())
    if total_invested <= 0:
        return _shape(_EMPTY_COMPLETENESS, "No holdings found in this portfolio yet.")

    viewed_fund = await db.get(MfFund, isin)
    viewed_category = viewed_fund.category if viewed_fund else None

    category_allocation_pct: float | None = None
    fund_count_in_category: int | None = None
    if viewed_category:
        held_isins_all = list(invested_by_isin.keys())
        fund_meta_result = await db.execute(
            select(MfFund.isin, MfFund.category).where(MfFund.isin.in_(held_isins_all))
        )
        fund_categories = {r.isin: r.category for r in fund_meta_result.fetchall()}
        cat_value = sum(
            v for i, v in invested_by_isin.items() if fund_categories.get(i) == viewed_category
        )
        category_allocation_pct = round(cat_value / total_invested * 100, 2)
        fund_count_in_category = sum(
            1 for i in held_isins_all if fund_categories.get(i) == viewed_category
        )

    # Overlap: exclude the viewed fund from its own comparison if already held.
    held_isins = [i for i in invested_by_isin if i != isin]
    if not held_isins:
        return _shape(
            _NO_CONSTITUENT_DATA_COMPLETENESS,
            _portfolio_fit_observation(None, category_allocation_pct),
            category_allocation_pct=category_allocation_pct,
            fund_count_in_category=fund_count_in_category,
        )

    viewed_month = (
        await db.execute(
            select(sqlfunc.max(MfFundConstituent.as_of_month)).where(MfFundConstituent.isin == isin)
        )
    ).scalar_one_or_none()
    if viewed_month is None:
        return _shape(
            _NO_CONSTITUENT_DATA_COMPLETENESS,
            _portfolio_fit_observation(None, category_allocation_pct),
            category_allocation_pct=category_allocation_pct,
            fund_count_in_category=fund_count_in_category,
        )

    viewed_rows = (
        await db.execute(
            select(MfFundConstituent.constituent_isin, MfFundConstituent.weight_pct).where(
                MfFundConstituent.isin == isin, MfFundConstituent.as_of_month == viewed_month
            )
        )
    ).all()
    viewed_map = {
        r.constituent_isin: float(r.weight_pct or 0.0) for r in viewed_rows if r.constituent_isin
    }
    if not viewed_map:
        return _shape(
            _NO_CONSTITUENT_DATA_COMPLETENESS,
            _portfolio_fit_observation(None, category_allocation_pct),
            category_allocation_pct=category_allocation_pct,
            fund_count_in_category=fund_count_in_category,
        )

    latest_months_result = await db.execute(
        select(MfFundConstituent.isin, sqlfunc.max(MfFundConstituent.as_of_month).label("latest"))
        .where(MfFundConstituent.isin.in_(held_isins))
        .group_by(MfFundConstituent.isin)
    )
    latest_months = {r.isin: r.latest for r in latest_months_result.fetchall()}
    if not latest_months:
        return _shape(
            _NO_CONSTITUENT_DATA_COMPLETENESS,
            _portfolio_fit_observation(None, category_allocation_pct),
            category_allocation_pct=category_allocation_pct,
            fund_count_in_category=fund_count_in_category,
        )

    isin_month_pairs = [(h, latest_months[h]) for h in latest_months]
    filtered_result = await db.execute(
        select(
            MfFundConstituent.isin,
            MfFundConstituent.constituent_isin,
            MfFundConstituent.weight_pct,
        ).where(
            sql_tuple(MfFundConstituent.isin, MfFundConstituent.as_of_month).in_(isin_month_pairs)
        )
    )
    held_maps: dict[str, dict[str, float]] = {}
    for r in filtered_result.fetchall():
        if r.constituent_isin is None:
            continue
        held_maps.setdefault(r.isin, {})[r.constituent_isin] = float(r.weight_pct or 0.0)

    # Held funds' display names for the top-3 breakdown (2026-07-06 P2) — only queried for
    # funds that actually reached held_maps (constituent data present); a name-less/unresolved
    # fund falls back to its own ISIN, never blank.
    held_names: dict[str, str] = {}
    if held_maps:
        name_result = await db.execute(
            select(MfFund.isin, MfFund.fund_name_short, MfFund.scheme_name).where(
                MfFund.isin.in_(list(held_maps.keys()))
            )
        )
        held_names = {
            r.isin: (r.fund_name_short or r.scheme_name or r.isin) for r in name_result.fetchall()
        }

    weighted_sum = 0.0
    weight_total = 0.0
    per_fund_overlap: list[dict[str, Any]] = []
    for h_isin, cmap in held_maps.items():
        shared = set(cmap) & set(viewed_map)
        pair_overlap_pct = round(sum(min(cmap[c], viewed_map[c]) for c in shared), 2)
        w = invested_by_isin.get(h_isin, 0.0)
        weighted_sum += pair_overlap_pct * w
        weight_total += w
        if pair_overlap_pct > 0:
            per_fund_overlap.append(
                {"holding_name": held_names.get(h_isin, h_isin), "overlap_pct": pair_overlap_pct}
            )

    if weight_total <= 0:
        return _shape(
            _NO_CONSTITUENT_DATA_COMPLETENESS,
            _portfolio_fit_observation(None, category_allocation_pct),
            category_allocation_pct=category_allocation_pct,
            fund_count_in_category=fund_count_in_category,
        )

    overlap_pct = round(weighted_sum / weight_total, 2)
    per_fund_overlap.sort(key=lambda e: e["overlap_pct"], reverse=True)
    return _shape(
        _CONSTITUENT_COMPLETENESS,
        _portfolio_fit_observation(overlap_pct, category_allocation_pct),
        overlap_pct=overlap_pct,
        category_allocation_pct=category_allocation_pct,
        fund_count_in_category=fund_count_in_category,
        overlap=per_fund_overlap[:3],
    )


# ---------------------------------------------------------------------------
# Mood-context helpers (pure — no I/O)
# ---------------------------------------------------------------------------

_REGIME_LABELS: dict[str, str] = {
    "extreme_fear": "Extreme Fear",
    "fear": "Fear",
    "neutral": "Neutral",
    "greed": "Greed",
    "extreme_greed": "Extreme Greed",
    "insufficient_data": "Insufficient Data",
    "data_unavailable": "Data Unavailable",
}


def _regime_display(regime: str) -> str:
    """Return a human-readable label for a regime string, safe for unknown values."""
    return _REGIME_LABELS.get(regime, regime.replace("_", " ").title())


# Band taxonomy governed by ADR-0032 — descriptive, non-advisory; thresholds provisional v1.
def _concentration_band(fund_count: int, top_pct: float) -> str:
    """
    Derive a public-safe concentration band from fund count and top-category %.

    Banding thresholds (educational description — never prescriptive):
      empty    — no holdings
      high     — top category >= 70% OR only 1 fund
      moderate — top category 40–69%
      low      — top category < 40% with 2+ funds
    """
    if fund_count == 0:
        return "empty"
    if fund_count == 1 or top_pct >= 70.0:
        return "high"
    if top_pct >= 40.0:
        return "moderate"
    return "low"


def _build_observations(
    regime: str,
    regime_as_of: str | None,
    fund_count: int,
    concentration_band: str,
) -> list[str]:
    """
    Build the three deterministic, SEBI-compliant observation strings.

    Templates are fixed — no LLM, no advisory verbs, no direction prediction.
    Exactly three observations are always returned (contract from spec).
    """
    # Observation 1 — regime read
    if regime == "data_unavailable":
        obs1 = (
            "Market mood data is currently unavailable; "
            "the read below covers only your portfolio's structure."
        )
    else:
        date_str = regime_as_of or "unknown date"
        label = _regime_display(regime)
        obs1 = (
            f"Market mood is currently {label} — an educational read of overall "
            f"market conditions as of {date_str}."
        )

    # Observation 2 — portfolio structure
    if fund_count > 0:
        obs2 = (
            f"Your portfolio holds {fund_count} "
            f"{'fund' if fund_count == 1 else 'funds'}; "
            f"its concentration reads {concentration_band} based on category mix."
        )
    else:
        obs2 = (
            "No scored holdings yet — upload a CAS statement to see "
            "your portfolio's structure here."
        )

    # Observation 3 — always present independence disclaimer
    obs3 = (
        "Portfolio structure and market mood are independent reads — "
        "neither is a signal to act. "
        "Mood describes conditions; it does not predict direction."
    )

    # Independence disclaimer placed between the mood and structure reads so the
    # regime↔concentration pairing can never be read adjacently without the
    # "not a signal to act" line between them (Compliance review F2).
    return [obs1, obs3, obs2]


# ---------------------------------------------------------------------------
# Mood-context service
# ---------------------------------------------------------------------------

async def get_mood_context(
    db: Any,
    user_id: str,
    portfolio_id: str,
) -> MoodContextResponse:
    """
    Build the mood-context response for the given portfolio.

    - Verifies portfolio belongs to user (IDOR guard → ValueError on mismatch).
    - Reads current mood via mood.service public read path (no raw mood-table SQL here).
    - Derives concentration band from existing concentration internals (same isin_value logic).
    - Cold-start / empty portfolio → valid 200 with honest empty read.
    - No new migration required — reads only existing mf.* tables.
    """
    from sqlalchemy import select

    from dhanradar.models.mf import MfFund, MfPortfolio, MfUserHolding

    uid = _parse_uid(user_id)
    try:
        pid = UUID(portfolio_id)
    except (ValueError, TypeError):
        pid = None

    disc = _safe_disclosure()

    # Fetch current mood — always succeeds (returns data_unavailable sentinel on miss)
    from dhanradar.mood.service import get_latest, unavailable_public

    mood_row = await get_latest(db)
    mood = mood_row if mood_row is not None else unavailable_public()
    regime = mood.regime
    regime_as_of = mood.snapshot_date if mood.snapshot_date else None

    # Malformed inputs → empty but valid response (no 500)
    if uid is None or pid is None:
        observations = _build_observations(regime, regime_as_of, 0, "empty")
        return MoodContextResponse(
            portfolio_id=portfolio_id,
            regime=regime,
            regime_as_of=regime_as_of or None,
            fund_count=0,
            concentration_band="empty",
            top_category=None,
            observations=observations,
            **disc,
        )

    # IDOR guard: portfolio must exist AND belong to this user
    port_result = await db.execute(
        select(MfPortfolio).where(MfPortfolio.id == pid, MfPortfolio.user_id == uid)
    )
    portfolio = port_result.scalar_one_or_none()
    if portfolio is None:
        raise ValueError("portfolio_not_found")

    # Load holdings (same query as concentration)
    holdings_result = await db.execute(
        select(
            MfUserHolding.isin,
            MfUserHolding.invested_amount,
        ).where(
            MfUserHolding.portfolio_id == pid,
            MfUserHolding.user_id == uid,
        )
    )
    rows = holdings_result.fetchall()

    if not rows:
        observations = _build_observations(regime, regime_as_of, 0, "empty")
        return MoodContextResponse(
            portfolio_id=portfolio_id,
            regime=regime,
            regime_as_of=regime_as_of or None,
            fund_count=0,
            concentration_band="empty",
            top_category=None,
            observations=observations,
            **disc,
        )

    isins = list({r.isin for r in rows})

    # Resolve fund metadata (same as concentration)
    fund_meta_result = await db.execute(
        select(MfFund.isin, MfFund.category).where(MfFund.isin.in_(isins))
    )
    fund_meta: dict[str, str] = {
        r.isin: r.category or "Uncategorized"
        for r in fund_meta_result.fetchall()
    }

    # Compute value per ISIN (same proxy as concentration)
    isin_value: dict[str, float] = {}
    for r in rows:
        v = float(r.invested_amount) if r.invested_amount else 0.0
        isin_value[r.isin] = isin_value.get(r.isin, 0.0) + v

    total_value = sum(isin_value.values())
    fund_count = len(isins)

    # Derive concentration band using the banding helper (reuses concentration logic)
    if total_value == 0.0:
        # Holdings exist but cost basis not yet available — treat as empty for banding
        band = "empty"
        top_category = None
    else:
        # Top-category % (value-weighted, same math as the analytics concentration payload)
        cat_value: dict[str, float] = {}
        for isin, val in isin_value.items():
            cat = fund_meta.get(isin, "Uncategorized")
            cat_value[cat] = cat_value.get(cat, 0.0) + val

        top_cat, top_val = max(cat_value.items(), key=lambda x: x[1])
        top_pct = top_val / total_value * 100
        band = _concentration_band(fund_count, top_pct)
        top_category = top_cat

    observations = _build_observations(regime, regime_as_of, fund_count, band)

    return MoodContextResponse(
        portfolio_id=portfolio_id,
        regime=regime,
        regime_as_of=regime_as_of or None,
        fund_count=fund_count,
        concentration_band=band,
        top_category=top_category,
        observations=observations,
        **disc,
    )
