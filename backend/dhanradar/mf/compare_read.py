"""
Compare fragment composer (COMPARE_LIVE_DATA_PLAN.md Waves C1 + C2).

Wave C1: get_compare_fragment assembles a per-ISIN fragment from existing read
  models: head · analytics (subset) · SIP (two fixed-safe illustrations) ·
  category medians · benchmark comparison (rebased 1Y series).

Wave C2 additions: composition (top-10 holdings + sector split) · people
  (manager summary + 5-year manager changes) · flows (category-level) · events
  (capped 5) · AMC facts · alternatives (peers, deduped/capped at bundle level).
  Also: pairwise holdings-overlap fragments (TTL 6h, pure helper below).

compose_compare_bundle_fragments gathers N cold ISINs concurrently using one
`SessionLocal` session per task (never the shared request `AsyncSession`) bounded
by a semaphore ≤ 4.  No raw composite score fields are selected.
"""

from __future__ import annotations

import asyncio
from statistics import median

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import SessionLocal
from dhanradar.mf.fund_events import derive_event_severity
from dhanradar.mf.fund_read import (
    _category_avg_returns,
    get_fund_analytics,
    get_fund_comparison,
    get_fund_composition,
    get_fund_events,
    get_fund_flows,
    get_fund_head,
    get_fund_peers,
    get_fund_people,
    get_fund_sip,
)
from dhanradar.models.mf import MfFund

_CMP_SIP_AMOUNT = 5_000  # fixed educational SIP amount
_CMP_BENCHMARK_WINDOW = "1y"
_CMP_OVERLAP_TTL = 21_600   # 6-hour TTL for mf:cmp:overlap:{a}:{b} Redis keys
_EVENTS_C2_CAP = 5           # cap events per fund on the compare surface

# Analytics fields safe for the compare surface (DOM-allowed standard ratios only;
# no composite score, no factor weights, no raw percentile numbers).
_ANALYTICS_FIELDS = (
    "sharpe_ratio",
    "sortino_ratio",
    "volatility_pct",
    "max_drawdown_pct",
    "rolling_1y_avg_pct",
    "rolling_1y_min_pct",
    "rolling_1y_max_pct",
    "rolling_1y_pct_positive",
    "rolling_3y_avg_pct",
    "rolling_3y_min_pct",
    "rolling_3y_max_pct",
    "rolling_3y_pct_positive",
)


# ---------------------------------------------------------------------------
# Pure overlap helper (Wave C2) — no DB, no async; directly unit-testable.
# ---------------------------------------------------------------------------

def compute_overlap_pct(holdings_a: list[dict], holdings_b: list[dict]) -> float:
    """Constituent intersection by weight: sum of min(w_a, w_b) for common names.

    Uses constituent name as the join key (weight_pct is the per-holding % of NAV
    as stored in mf_fund_constituents).  Rounded to 2 dp.  Returns 0.0 on empty.
    """
    weights_b: dict[str, float] = {
        h["name"]: h["weight_pct"]
        for h in holdings_b
        if h.get("name") and h.get("weight_pct") is not None
    }
    return round(
        sum(
            min(h["weight_pct"], weights_b[h["name"]])
            for h in holdings_a
            if h.get("name") and h.get("weight_pct") is not None and h["name"] in weights_b
        ),
        2,
    )


def build_pairwise_overlap(
    frag_a: dict | None,
    frag_b: dict | None,
    isin_a: str,
    isin_b: str,
) -> dict:
    """Build a pairwise overlap fragment or a no_data marker.

    HARD GUARD (COMPARE_LIVE_DATA_PLAN.md §Architecture): both funds MUST have
    coverage.holdings_count > 0 — never emit 0% for an uncovered fund pair.
    """
    if frag_a is None or frag_b is None:
        return {"no_data": True, "isin_a": isin_a, "isin_b": isin_b, "reason": "fund_not_found"}

    comp_a = frag_a.get("composition") or {}
    comp_b = frag_b.get("composition") or {}

    if comp_a.get("no_data") or comp_b.get("no_data"):
        return {"no_data": True, "isin_a": isin_a, "isin_b": isin_b, "reason": "insufficient_coverage"}

    cov_a = (comp_a.get("coverage") or {}).get("holdings_count", 0)
    cov_b = (comp_b.get("coverage") or {}).get("holdings_count", 0)
    if not cov_a or not cov_b:
        return {"no_data": True, "isin_a": isin_a, "isin_b": isin_b, "reason": "insufficient_coverage"}

    holdings_a = comp_a.get("holdings", [])
    holdings_b = comp_b.get("holdings", [])
    weights_a = {
        h["name"]: h.get("weight_pct")
        for h in holdings_a
        if h.get("name") and h.get("weight_pct") is not None
    }
    weights_b = {
        h["name"]: h.get("weight_pct")
        for h in holdings_b
        if h.get("name") and h.get("weight_pct") is not None
    }
    common_holdings = [
        {
            "name": name,
            "weight_a": weights_a[name],
            "weight_b": weights_b[name],
        }
        for name in set(weights_a).intersection(weights_b)
    ]
    common_holdings.sort(
        key=lambda item: min(item["weight_a"], item["weight_b"]), reverse=True
    )

    return {
        "isin_a": isin_a,
        "isin_b": isin_b,
        "overlap_pct": compute_overlap_pct(
            holdings_a,
            holdings_b,
        ),
        "common_holdings": common_holdings[:10],
        "as_of_month_a": comp_a.get("as_of_month"),
        "as_of_month_b": comp_b.get("as_of_month"),
        "basis": "top_holdings_weight",
    }


async def get_compare_fragment(session: AsyncSession, isin: str) -> dict | None:
    """Compose one C1+C2 compare fragment for *isin*; None if the fund does not exist."""
    head = await get_fund_head(session, isin)
    if head is None:
        return None

    # --- C1: head / analytics / category medians / SIP / benchmark ---
    analytics_raw = await get_fund_analytics(session, isin)
    category_avgs = await _category_avg_returns(session, head["sebi_category"])
    category_ter = await _category_median_ter(session, head["sebi_category"])
    comparison = await get_fund_comparison(session, isin, window=_CMP_BENCHMARK_WINDOW)
    sip_5y = await get_fund_sip(session, isin, amount=_CMP_SIP_AMOUNT, years=5)
    sip_10y = await get_fund_sip(session, isin, amount=_CMP_SIP_AMOUNT, years=10)

    analytics: dict = {}
    if analytics_raw is not None:
        for key in _ANALYTICS_FIELDS:
            analytics[key] = analytics_raw.get(key)

    benchmark: dict | None = None
    if comparison is not None:
        bench = comparison.get("series", {}).get("benchmark", {})
        benchmark = {
            "label": bench.get("label"),
            "is_fallback": bench.get("is_fallback", False),
            "points": bench.get("points", []),
            "window": _CMP_BENCHMARK_WINDOW,
        }

    # --- C2: composition ---
    comp_raw = await get_fund_composition(session, isin)
    composition: dict
    if not comp_raw or not comp_raw.get("holdings"):
        composition = {"no_data": True}
    else:
        composition = {
            "holdings": comp_raw["holdings"][:10],
            "sectors": comp_raw["sectors"],
            "as_of_month": comp_raw["as_of_month"],
            "coverage": comp_raw["coverage"],
        }

    # --- C2: people + AMC facts (from same get_fund_people call) ---
    people_result = await get_fund_people(session, isin)
    people: dict
    amc: dict
    if people_result is None:
        people = {"no_data": True}
        amc = {"no_data": True}
    else:
        people_payload, amc_payload = people_result
        amc = {
            "amc_name": amc_payload["amc_name"],
            "scheme_count": amc_payload["scheme_count"],
            "category_count": amc_payload["category_count"],
            "amc_level_aum_crore": None,
            "source_blocked": True,
        }
        if not people_payload["managers"]:
            people = {"no_data": True}
        else:
            people = {
                "managers": people_payload["managers"],
                "manager_changes_5y": people_payload["manager_changes_5y"],
            }

    # --- C2: flows (category-level; preserve scheme_category for frontend framing) ---
    flows_raw = await get_fund_flows(session, isin)
    flows: dict
    if not flows_raw or not flows_raw.get("points"):
        flows = {
            "points": [],
            "scheme_category": (flows_raw or {}).get("scheme_category"),
            "as_of_month": None,
            "source_blocked": True,
        }
    else:
        flows = {
            "points": flows_raw["points"],
            "scheme_category": flows_raw.get("scheme_category"),
            "as_of_month": flows_raw.get("as_of_month"),
        }

    # --- C2: events (capped at 5; event_type/as_of/summary/severity only) ---
    events_raw = await get_fund_events(session, isin)
    events: dict
    if not events_raw or not events_raw.get("events"):
        events = {"events": [], "source_blocked": True}
    else:
        capped = events_raw["events"][:_EVENTS_C2_CAP]
        events = {
            "events": [
                {
                    "event_type": e["event_type"],
                    "as_of": e["as_of"],
                    "summary": e["summary"],
                    "severity": derive_event_severity(e["event_type"], e.get("payload", {})),
                }
                for e in capped
            ]
        }

    # --- C2: alternatives (raw peers; dedup+cap applied at bundle serialisation) ---
    peers_raw = await get_fund_peers(session, isin)
    alternatives: dict
    if peers_raw is None:
        alternatives = {"peers": [], "no_data": True}
    else:
        alternatives = {"peers": peers_raw["peers"]}

    return {
        # C1 — head facts
        "isin": head["isin"],
        "scheme_name": head["scheme_name"],
        "fund_name_short": head["fund_name_short"],
        "amc_name": head["amc_name"],
        "sebi_category": head["sebi_category"],
        "category": head["category"],
        "plan_type": head["plan_type"],
        "option_type": head["option_type"],
        "launch_date": head["launch_date"],
        "expense_ratio_pct": head["expense_ratio_pct"],
        "is_segregated": head["is_segregated"],
        "verb_label": head["verb_label"],
        "confidence_band": head["confidence_band"],
        "category_rank": head["category_rank"],
        "category_total": head["category_total"],
        "return_3m_pct": head["return_3m_pct"],
        "return_6m_pct": head["return_6m_pct"],
        "return_1y_pct": head["return_1y_pct"],
        "return_3y_pct": head["return_3y_pct"],
        "return_5y_pct": head["return_5y_pct"],
        "nav_latest": head["nav_latest"],
        "nav_date": head["nav_date"],
        "nav_change_pct": head["nav_change_pct"],
        "aum_crore": head["aum_crore"],
        # C1 — analytics subset (DOM-allowed standard ratios; no composite score)
        **analytics,
        # C1 — category medians (p50 from mf_category_stats)
        "category_median_return_1y_pct": category_avgs["return_1y_pct"],
        "category_median_return_3y_pct": category_avgs["return_3y_pct"],
        "category_median_ter_pct": category_ter,
        # C1 — SIP illustrations (fixed safe amounts; deterministic, educational)
        "sip_5y": sip_5y,
        "sip_10y": sip_10y,
        # C1 — benchmark comparison (rebased 1Y series)
        "benchmark": benchmark,
        # C2 — depth fragments
        "composition": composition,
        "people": people,
        "flows": flows,
        "events": events,
        "amc": amc,
        "alternatives": alternatives,
    }


async def _category_median_ter(session: AsyncSession, sebi_category: str | None) -> float | None:
    """Return the current category TER median, withholding an empty cohort."""
    if not sebi_category:
        return None
    rows = (
        await session.execute(
            select(MfFund.expense_ratio_pct).where(
                MfFund.sebi_category == sebi_category,
                MfFund.expense_ratio_pct.is_not(None),
            )
        )
    ).scalars().all()
    return float(median([float(value) for value in rows])) if rows else None


async def compose_compare_bundle_fragments(cold_isins: list[str]) -> dict[str, dict | None]:
    """Concurrently compose fragments for *cold_isins*.

    One independent ``SessionLocal`` session per ISIN (never the shared request
    ``AsyncSession``).  Concurrency bounded by a per-call semaphore ≤ 4 per the
    architect review condition (COMPARE_LIVE_DATA_PLAN.md §Architecture).
    """
    sem = asyncio.Semaphore(4)

    async def _one(isin: str) -> tuple[str, dict | None]:
        async with sem:
            async with SessionLocal() as session:
                frag = await get_compare_fragment(session, isin)
        return isin, frag

    pairs = await asyncio.gather(*(_one(isin) for isin in cold_isins))
    return dict(pairs)
