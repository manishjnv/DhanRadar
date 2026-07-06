"""`fund.changes` — the What-Changed diff engine (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md
§10.6, §17 W2).

Pure, DB-independent detector functions (unit-testable without a worker/DB — mirrors the
`tasks/mf.py` convention of factoring pure mapping helpers out of the Celery pipeline) plus
the request-time summary-sentence templates. The nightly `fund_events_refresh` pipeline
(`dhanradar.tasks.mf`) reads `mf_fund_ranks` / `expense_ratio_history` / `mf_fund_constituents`
and calls these functions to decide what to upsert into `mf.mf_fund_events`.

FACTS ONLY (non-neg #1): every payload and summary sentence carries old/new values and a
direction word — never an advisory verb (buy/sell/hold/switch/avoid/caution).
"""

from __future__ import annotations

from datetime import date

# Thresholds (§10.6) — one place, reused by the pipeline and its tests.
_RANK_DELTA_MIN = 3
_WEIGHT_DELTA_MIN_PP = 1.0
_AUM_CHANGE_MIN_PCT = 5.0
MAX_EVENTS_PER_FUND = 4  # one per event_type — the full type set below is exactly 4
EVENT_TYPES: tuple[str, ...] = ("rank_change", "ter_change", "holding_change", "aum_change")


def _quartile(rank: int, total: int) -> int:
    """Which quartile (1=best..4=worst) `rank` (1-indexed) falls into within `total`."""
    if total <= 0:
        return 1
    pct = (rank - 1) / total
    if pct < 0.25:
        return 1
    if pct < 0.5:
        return 2
    if pct < 0.75:
        return 3
    return 4


def detect_rank_change(
    *, old_rank: int, old_total: int, new_rank: int, new_total: int
) -> dict | None:
    """Emit when |Δrank| >= 3 OR the fund's category-percentile quartile crossed a
    boundary between the two as_of_dates. `direction` is "up" (rank number got smaller —
    better) / "down" (worse) / "flat" (same rank number, only the quartile boundary moved
    because `total` changed)."""
    delta = old_rank - new_rank  # positive = improved
    quartile_crossed = _quartile(old_rank, old_total) != _quartile(new_rank, new_total)
    if abs(delta) < _RANK_DELTA_MIN and not quartile_crossed:
        return None
    direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
    return {
        "old_rank": old_rank,
        "new_rank": new_rank,
        "total": new_total,
        "direction": direction,
    }


def detect_ter_change(*, old_ter: float, new_ter: float, effective_date: date) -> dict | None:
    """Emit whenever the last two `expense_ratio_history` rows differ."""
    if old_ter == new_ter:
        return None
    return {
        "old_ter": round(old_ter, 3),
        "new_ter": round(new_ter, 3),
        "effective_date": effective_date.isoformat(),
    }


def detect_aum_change(
    *, old_aum_crore: float, new_aum_crore: float, as_of_month: date
) -> dict | None:
    """Emit when the month-over-month AUM % change is >= 5% in either direction.

    `direction` is "up" (AUM grew) / "down" (AUM shrank). Facts only — no advisory
    framing (a growing/shrinking AUM is not itself good or bad).
    """
    if old_aum_crore == 0:
        return None
    pct_change = (new_aum_crore - old_aum_crore) / old_aum_crore * 100
    if abs(pct_change) < _AUM_CHANGE_MIN_PCT:
        return None
    return {
        "old_aum_crore": round(old_aum_crore, 2),
        "new_aum_crore": round(new_aum_crore, 2),
        "pct_change": round(pct_change, 2),
        "direction": "up" if pct_change > 0 else "down",
    }


def detect_holding_change(*, old_holdings: list[dict], new_holdings: list[dict]) -> dict | None:
    """Single largest |Δweight| >= 1.0pp among constituents present in BOTH months.

    `old_holdings` / `new_holdings`: `[{"name": str, "weight_pct": float | None}, ...]` for
    one fund, one `as_of_month` each. A name that only appears in one month (new entrant /
    dropped holding) has no baseline to diff and is skipped — never fabricated as 0%.
    """
    old_by_name = {
        h["name"]: h["weight_pct"] for h in old_holdings if h.get("weight_pct") is not None
    }
    best: tuple[str, float, float] | None = None
    best_delta = 0.0
    for h in new_holdings:
        new_w = h.get("weight_pct")
        name = h["name"]
        if new_w is None or name not in old_by_name:
            continue
        old_w = old_by_name[name]
        delta = abs(new_w - old_w)
        if delta > best_delta:
            best_delta = delta
            best = (name, old_w, new_w)
    if best is None or best_delta < _WEIGHT_DELTA_MIN_PP:
        return None
    name, old_w, new_w = best
    return {
        "name": name,
        "old_weight_pct": round(old_w, 1),
        "new_weight_pct": round(new_w, 1),
    }


def cap_fund_events(events: list[dict]) -> list[dict]:
    """Defensive cap (§10.6): at most one event per `event_type`, at most
    `MAX_EVENTS_PER_FUND` total, per fund per run — even if a caller ever double-detects
    the same type. `events` are dicts with an `"event_type"` key; first-seen wins."""
    seen: set[str] = set()
    capped: list[dict] = []
    for ev in events:
        et = ev["event_type"]
        if et in seen:
            continue
        seen.add(et)
        capped.append(ev)
        if len(capped) >= MAX_EVENTS_PER_FUND:
            break
    return capped


# ---------------------------------------------------------------------------
# Request-time summary sentences (§17 W2 endpoint contract) — templated from the
# stored `payload`, never stored themselves, so a copy fix never needs a backfill.
# Facts only, <=14 words, no advisory verb (test_fund_events.py asserts this).
# ---------------------------------------------------------------------------


def _summary_rank_change(p: dict) -> str:
    return f"Category rank moved from {p['old_rank']} to {p['new_rank']} of {p['total']}."


def _summary_ter_change(p: dict) -> str:
    return f"Expense ratio changed from {p['old_ter']:.2f}% to {p['new_ter']:.2f}%."


def _summary_holding_change(p: dict) -> str:
    return (
        f"Largest holding shift: {p['name']} "
        f"{p['old_weight_pct']:.1f}% → {p['new_weight_pct']:.1f}%."
    )


def _summary_aum_change(p: dict) -> str:
    return (
        f"AUM changed from ₹{p['old_aum_crore']:.2f}cr to "
        f"₹{p['new_aum_crore']:.2f}cr ({p['pct_change']:+.1f}%)."
    )


_SUMMARY_TEMPLATES = {
    "rank_change": _summary_rank_change,
    "ter_change": _summary_ter_change,
    "holding_change": _summary_holding_change,
    "aum_change": _summary_aum_change,
}


def summarize_event(event_type: str, payload: dict) -> str:
    """One plain factual sentence for an event row — the endpoint's `summary` field."""
    template = _SUMMARY_TEMPLATES.get(event_type)
    if template is None:
        return "This fund had a tracked change."
    return template(payload)
