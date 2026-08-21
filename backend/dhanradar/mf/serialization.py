"""The single serialization boundary (A3, UI_DATA_ARCHITECTURE_PLAN.md §5/§6/§7/§10 layer 8).

The ONE backend place that enforces non-negotiable #2 (no-numeric-in-DOM), visibility gating, and tier
gating, producing the `DataEnvelope` (§5) for every served concept. Defense-in-depth WITH RLS behind it:
RLS (I5) decides WHO sees WHOSE rows; this boundary decides WHAT framing (#2/visibility) and WHO PAID
(tier). They are complementary (§6) — neither replaces the other.

RULE: a concept payload reaches a client ONLY through `serialize_concept`. No endpoint re-implements the
gating; the I1/I2/tier fixtures red the build if a raw score leaks or a gate is bypassed.

BLOCKERS B87 (2026-07-04): the #2 numeric strip is now backed by a per-concept field ALLOWLIST
(`ALLOWED_FIELDS`) as the structural guarantee — a concept serves ONLY its declared top-level fields.
`FORBIDDEN_SCORE_KEYS` remains as a second tripwire layer underneath it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from dhanradar.deps import _PRO_RANK, _tier_rank
from dhanradar.mf.concepts import get_concept

#: Keys that carry a raw DhanRadar COMPOSITE score / factor weights / fair-value — NEVER serialized to
#: any client (non-neg #2). The user's OWN calculated numbers (units, invested_amount, current_value,
#: xirr, pnl, cagr) and ordinal rank are #2-EXEMPT (DOM-allowed calculated user facts, §13) and are NOT
#: here — only the DhanRadar composite is forbidden. NB: `factor_weights` (scoring internals), not bare
#: `weights` (allocation weights are a legitimate user %).
#:
#: This is a DENYLIST — it catches a raw-score key by KNOWN name. BLOCKERS B87 (implemented below via
#: `ALLOWED_FIELDS`) is now the structural guarantee — a concept may serve ONLY its declared top-level
#: fields, so a score emitted under a NOVEL key (e.g. `rating`, `percentile`) can no longer slip through
#: un-declared. This denylist stays a SECOND TRIPWIRE: even a key mistakenly added to a concept's
#: allowlist (human error) is still stripped here before it can reach a client. The I1 fixture guards
#: the known names; the B87 fixtures guard the allowlist/tripwire interaction.
FORBIDDEN_SCORE_KEYS: frozenset[str] = frozenset(
    {
        "unified_score",
        "score",
        "raw_score",
        "score_raw",
        "composite_score",
        "numeric_score",
        "factor_weights",
        "factor_scores",
        "fair_value",
        "fair_value_estimate",
    }
)

#: Leaf types accepted as #2-safe scalars (no nested keys a score could hide in). Any OTHER object
#: reaching the scrub (a set is descended; a Pydantic model / ORM Row / arbitrary object is REFUSED
#: fail-closed) — callers pass plain JSON so every key is visible to the scrub.
_SAFE_SCALARS = (str, int, float, bool, Decimal, date, datetime, time, UUID)


class MissingConceptAllowlist(RuntimeError):
    """Fail-closed (BLOCKERS B87): a concept reached `serialize_concept` with no entry in
    `ALLOWED_FIELDS` below. A concept can never ship un-allowlisted — add
    `"<concept_id>": frozenset({...})` to `ALLOWED_FIELDS`, listing every top-level field its payload
    legitimately serializes, before wiring an endpoint that serves it."""


#: BLOCKERS B87 — the structural #2 guarantee. Per-concept ALLOWLIST of serializable TOP-LEVEL payload
#: field names: `serialize_concept` keeps ONLY these keys for a concept, dropping anything else
#: silently — a field must be explicitly declared to reach a client, not merely absent from
#: `FORBIDDEN_SCORE_KEYS` (allowlist > denylist; the denylist above stays a tripwire regardless of what
#: is declared here). A concept with no entry raises `MissingConceptAllowlist` (fail-closed) — every
#: entry below is exactly the field set each concept's payload builder in `mf/portfolio_read.py` emits
#: today (parity-tested; zero behavior change). One concept per line — merge-friendly: a new concept
#: (e.g. a future `fund.*` concept) appends a line and never touches an existing one.
ALLOWED_FIELDS: dict[str, frozenset[str]] = {
    "holdings.list": frozenset({"portfolio_id", "holdings"}),
    "holding.transactions": frozenset({"portfolio_id", "isin", "count", "total", "limit", "offset", "transactions"}),
    "portfolio.summary": frozenset({"portfolio_id", "total_value", "value_priced_pct", "total_invested", "invested_missing_count", "cost_value", "gain", "gain_pct", "gain_vs_cost", "gain_vs_cost_pct", "xirr_pct", "xirr_coverage_pct", "xirr_1y_pct", "xirr_1y_window_days", "wt_avg_days", "wt_avg_days_coverage_pct", "day_change", "day_change_pct", "day_change_as_of", "day_change_coverage_pct", "fund_count", "funds_scored", "confidence_band", "as_of", "valuation_as_of", "investor_name"}),
    "portfolio.risk": frozenset({"portfolio_id", "risk_band", "risk_band_basis", "volatility_pct", "max_drawdown_pct", "recovery_months", "fund_count", "funds_with_metrics", "as_of"}),
    "portfolio.risk_advanced": frozenset({"portfolio_id", "sharpe_ratio", "sortino_ratio", "rolling_1y_avg_pct", "rolling_1y_pct_positive", "alpha", "beta", "as_of"}),
    "portfolio.allocation": frozenset({"portfolio_id", "by", "buckets", "total_value", "fund_count", "as_of"}),
    "portfolio.concentration": frozenset({"portfolio_id", "band", "top_fund", "top_amc", "by_amc", "fund_count", "amc_count", "as_of"}),
    "portfolio.diversification": frozenset({"portfolio_id", "band", "category_count", "top_category", "top_category_pct", "fund_count", "as_of"}),
    "portfolio.valuation_series": frozenset({"portfolio_id", "point_count", "first_investment_date", "points"}),
    "portfolio.score_raw": frozenset(),  # gated-never (registry) — nothing is ever allowed through, gated or not
    "fund.label": frozenset({"label"}),
    "fund.head": frozenset(
        {
            "isin",
            "scheme_name",
            "fund_name_short",
            "amc_name",
            "sebi_category",
            "category",
            "plan_type",
            "option_type",
            "idcw_frequency",
            "launch_date",
            "expense_ratio_pct",
            "is_segregated",
            "verb_label",
            "category_rank",
            "category_total",
            "rank_as_of",
            "return_3m_pct",
            "return_6m_pct",
            "return_1y_pct",
            "return_3y_pct",
            "return_5y_pct",
            "metrics_as_of",
            "nav_latest",
            "nav_date",
            "nav_change_pct",
            "confidence_band",
            "amc_level_aum_crore",
            "aum_crore",
            "aum_as_of",
        }
    ),
    "fund.nav_series": frozenset({"range", "points", "from", "to", "n_total"}),
    "fund.analytics": frozenset(
        {
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
            "alpha_1y",
            "beta_1y",
            "tracking_error_pct",
            "as_of",
            "volatility_percentile",
            "category_percentiles",
            "drawdown_series",
            "worst_fall_pct",
            "recovery_days",
            "calendar_year_returns",
        }
    ),
    "fund.rank_history": frozenset({"points"}),
    "fund.composition": frozenset({"holdings", "sectors", "cap_mix", "as_of_month", "coverage"}),
    "fund.flows": frozenset({"points", "scheme_category", "as_of_month"}),
    "fund.fit": frozenset(
        {
            "portfolio_id",
            "viewed_isin",
            "overlap_pct",
            "category_allocation_pct",
            "fund_count_in_category",
            "overlap",
            "overlap_coverage",
            "data_completeness",
            "observation",
        }
    ),
    "fund.people": frozenset({"managers", "manager_changes_5y"}),
    "fund.amc": frozenset({"amc_name", "scheme_count", "category_count"}),
    "fund.peers": frozenset({"peers"}),
    "fund.factors": frozenset({"factors", "confidence_band", "as_of"}),
    "fund.signals": frozenset({"contributing", "contradicting", "as_of"}),
    "fund.sip_illustration": frozenset(
        {
            "amount",
            "years",
            "months_invested",
            "total_invested",
            "final_value",
            "xirr_pct",
            "as_of",
            "assumptions",
        }
    ),
    "fund.health": frozenset({"lights", "as_of"}),
    "fund.changes": frozenset({"events"}),
    # Phase 1 leaderboard (docs/features/leaderboard-data-backend.md §5) — one entry
    # per board row SHAPE (a leaderboard payload isn't one flat concept, it's ~18
    # board shapes + a hero summary). See `serialize_leaderboard_response` below.
    "leaderboard.fund_row": frozenset(
        {
            "isin",
            "fund_name_short",
            "scheme_name",
            "amc_name",
            "sebi_category",
            "verb_label",
            "confidence_band",
            "category_rank",
            "category_total",
            "rank_delta",
            "riskometer",
            # Phase G (2026-08-16) — full return spectrum on the Top-100 table.
            "return_1d_pct",
            "return_1m_pct",
            "return_3m_pct",
            "return_1y_pct",
            "return_3y_pct",
            "return_5y_pct",
            "expense_ratio_pct",
            "aum_crore",
            "sharpe_ratio",
            "max_drawdown_pct",
            "metric_value",
            "metric_unit",
            "metric_category_avg",
        }
    ),
    "leaderboard.label_upgrade_row": frozenset(
        {
            "isin",
            "fund_name_short",
            "scheme_name",
            "amc_name",
            "sebi_category",
            "verb_label",
            "confidence_band",
            "category_rank",
            "category_total",
            "rank_delta",
            "riskometer",
            "return_1y_pct",
            "return_3y_pct",
            "return_5y_pct",
            "expense_ratio_pct",
            "aum_crore",
            "sharpe_ratio",
            "max_drawdown_pct",
            "metric_value",
            "metric_unit",
            "metric_category_avg",
            "label_from",
            "label_to",
        }
    ),
    "leaderboard.champion_row": frozenset({"category", "winner", "runner_up", "why"}),
    "leaderboard.category_flow_row": frozenset({"category", "net_flow_cr", "period_month"}),
    "leaderboard.amc_row": frozenset(
        {
            "amc_name",
            "fund_count",
            "top_quartile_count",
            "aum_crore",
            "oldest_launch",
            "index_fund_count",
        }
    ),
    "leaderboard.hero": frozenset(
        {"funds_ranked", "categories", "top_fund", "trending_category", "live_board_count"}
    ),
    # Phase 3b manager_facts (leaderboard-data-backend.md §9b) — a NEW row shape,
    # NOT a FundRow: factual per-manager aggregate only. No score, no success %,
    # no stars, no raw percentile number (percentile_word is the word-only band).
    "leaderboard.manager_row": frozenset(
        {"manager_name", "amc_name", "funds_count", "tenure_years", "percentile_word", "top_fund_name"}
    ),
    # Phase 3c ai_insights (leaderboard-data-backend.md §9b) — governed-gateway
    # educational cards. `text` + deterministic post-hoc `links` (entity links,
    # 2026-08-16) are the ONLY keys a row may carry; `links` additionally passes
    # the nested shape scrub in `_serialize_leaderboard_row` (fail-closed).
    "leaderboard.insight_row": frozenset({"text", "links"}),
    # WATCHLIST_LIVE_DATA_PLAN.md Wave 1 (2026-08-21) — one row shape for
    # GET /mf/watchlist/cards, same #2 bypass pattern as the leaderboard row
    # shapes above (public fund facts composed server-side per caller ISIN,
    # not a registry-gated concept — see serialize_watchlist_cards_response).
    "mf.watchlist_card": frozenset(
        {
            "isin",
            "scheme_name",
            "fund_name_short",
            "amc_name",
            "sebi_category",
            "category",
            "expense_ratio_pct",
            "risk_o_meter",
            "nav_latest",
            "nav_change_pct",
            "nav_sparkline",
            "return_1y_pct",
            "return_3y_pct",
            "return_5y_pct",
            "verb_label",
            "confidence_band",
            # Wave 2 (S07 Performance) — the fund's own category median 1Y/3Y
            # return (mf_category_stats.p50); no 5Y metric_key exists there.
            "category_return_1y_pct",
            "category_return_3y_pct",
        }
    ),
    # WATCHLIST_LIVE_DATA_PLAN.md Wave 2 (2026-08-21) — `GET /mf/watchlist/changes`
    # row shape (fund.changes batch composer). Facts only: event_type/as_of/
    # summary/severity, never a score.
    "mf.watchlist_change": frozenset(
        {
            "isin",
            "scheme_name",
            "fund_name_short",
            "event_type",
            "as_of",
            "summary",
            "severity",
        }
    ),
    # WATCHLIST_LIVE_DATA_PLAN.md Wave 2 (2026-08-21) — `GET /mf/watchlist/similar`
    # row shape (fund.peers batch composer). Same field set as `fund.peers` plus
    # `confidence_band`/`category`/`similar_to` — never a raw score.
    "mf.watchlist_similar": frozenset(
        {
            "isin",
            "scheme_name",
            "fund_name_short",
            "amc_name",
            "category",
            "sebi_category",
            "verb_label",
            "confidence_band",
            "return_1y_pct",
            "return_3y_pct",
            "expense_ratio_pct",
            "similar_to",
        }
    ),
    # WATCHLIST_LIVE_DATA_PLAN.md Wave 3 (2026-08-21) — `GET /mf/watchlist/summary`
    # per-item row shape (governed AI-gateway consumer, `mf/watchlist_ai.py`). Each
    # summary/insight item is wrapped `{"text": str}` before this allowlist runs so
    # a poisoned dict (e.g. a smuggled numeric/score key) is stripped down to plain
    # text — see `serialize_watchlist_ai_response` below.
    "mf.watchlist_ai_item": frozenset({"text"}),
    # COMPARE_LIVE_DATA_PLAN.md Wave C1 (2026-08-21) — `GET /mf/compare/bundle`
    # row shapes. Three nested shapes + one top-level wrapper, each independently
    # allowlisted so the benchmark series is never embedded raw (architect condition).
    "mf.compare_benchmark": frozenset({"label", "is_fallback", "points", "window"}),
    "mf.compare_sip": frozenset(
        {"amount", "years", "months_invested", "total_invested", "final_value", "xirr_pct", "as_of", "assumptions"}
    ),
    "mf.compare_fragment": frozenset(
        {
            # head fields
            "isin", "scheme_name", "fund_name_short", "amc_name",
            "sebi_category", "category", "plan_type", "option_type",
            "launch_date", "expense_ratio_pct", "is_segregated",
            "verb_label", "confidence_band", "category_rank", "category_total",
            "return_3m_pct", "return_6m_pct", "return_1y_pct", "return_3y_pct", "return_5y_pct",
            "nav_latest", "nav_date", "nav_change_pct", "aum_crore",
            # analytics subset (DOM-allowed standard ratios + rolling returns)
            "sharpe_ratio", "sortino_ratio", "volatility_pct", "max_drawdown_pct",
            "rolling_1y_avg_pct", "rolling_1y_min_pct", "rolling_1y_max_pct", "rolling_1y_pct_positive",
            "rolling_3y_avg_pct", "rolling_3y_min_pct", "rolling_3y_max_pct", "rolling_3y_pct_positive",
            # category medians
            "category_median_return_1y_pct", "category_median_return_3y_pct", "category_median_ter_pct",
            # SIP illustrations (nested mf.compare_sip shape, scrubbed separately)
            "sip_5y", "sip_10y",
            # benchmark comparison (nested mf.compare_benchmark shape, scrubbed separately)
            "benchmark",
        }
    ),
    "mf.compare_bundle": frozenset({"isins", "fragments", "as_of"}),
}

#: Entity-link isin shape (2026-08-16) — read-boundary re-validation of the same
#: rule the writer (`leaderboard_insights._LINK_ISIN_RE`) enforces, so a poisoned
#: DB row can never smuggle a path segment into an /mf/fund/{isin} href.
_INSIGHT_LINK_ISIN_RE = re.compile(r"^[A-Z0-9]{12}$")

#: Maps a leaderboard `board_key` to the `ALLOWED_FIELDS` entry its rows are shaped
#: like (Phase 1, §5). Every board wired by `dhanradar.tasks.mf.leaderboard_refresh`
#: must have an entry here — `serialize_leaderboard_response` fail-closes
#: (`MissingConceptAllowlist`) on any board_key absent from this map, same as an
#: un-allowlisted concept above.
_LEADERBOARD_ROW_CONCEPT: dict[str, str] = {
    "top100": "leaderboard.fund_row",
    "perf_1y": "leaderboard.fund_row",
    "perf_3y": "leaderboard.fund_row",
    "perf_5y": "leaderboard.fund_row",
    "risk_lowest": "leaderboard.fund_row",
    "risk_drawdown": "leaderboard.fund_row",
    "risk_sharpe": "leaderboard.fund_row",
    "value_ter": "leaderboard.fund_row",
    "value_efficiency": "leaderboard.fund_row",
    "value_index": "leaderboard.fund_row",
    "movers_up": "leaderboard.fund_row",
    "movers_down": "leaderboard.fund_row",
    "top10_entries": "leaderboard.fund_row",
    "aum_growth": "leaderboard.fund_row",
    "label_upgrades": "leaderboard.label_upgrade_row",
    "champions": "leaderboard.champion_row",
    "category_inflows": "leaderboard.category_flow_row",
    "amc_facts": "leaderboard.amc_row",
    # Phase 2 (migration 0081, leaderboard-data-backend.md §8) — 5 new boards,
    # all plain FundRow shapes (the new metric travels via metric_value only).
    "wealth_creator": "leaderboard.fund_row",
    "sip_3y": "leaderboard.fund_row",
    "sip_5y": "leaderboard.fund_row",
    "sip_consistency": "leaderboard.fund_row",
    # D4 (2026-08-16) — published-rule beginner rail, S6 4th slot.
    "sip_beginner": "leaderboard.fund_row",
    "risk_recovery": "leaderboard.fund_row",
    # Phase 3a/3b (leaderboard-data-backend.md §9b) — 6 new boards.
    "hidden_gems": "leaderboard.fund_row",
    "future_leaders": "leaderboard.fund_row",
    "momentum": "leaderboard.fund_row",
    "quality": "leaderboard.fund_row",
    "ai_spotlight": "leaderboard.fund_row",
    "manager_facts": "leaderboard.manager_row",
    # Phase 3c (leaderboard-data-backend.md §9b) — S17 AI insight cards.
    "ai_insights": "leaderboard.insight_row",
    # V3 (founder 2026-08-16) — three-lenses board, plain FundRow shape (the
    # three lens metrics are already allowlisted fund_row fields).
    "three_lens": "leaderboard.fund_row",
}


def _apply_allowlist(concept_id: str, data: Any) -> Any:
    """BLOCKERS B87 — keep ONLY `ALLOWED_FIELDS[concept_id]`'s top-level keys; every other key is
    silently dropped. Fail-closed: an un-declared concept raises `MissingConceptAllowlist` naming the
    fix. A non-dict payload passes through unchanged (nothing to allowlist against; `_assert_no_forbidden`
    already ran on it above and still guards it)."""
    if not isinstance(data, dict):
        return data
    try:
        allowed = ALLOWED_FIELDS[concept_id]
    except KeyError:
        raise MissingConceptAllowlist(
            f"concept '{concept_id}' has no field allowlist — add "
            f'`"{concept_id}": frozenset({{...}})` to ALLOWED_FIELDS in mf/serialization.py, listing '
            "its serializable top-level fields, before serving it (BLOCKERS B87)"
        ) from None
    return {k: v for k, v in data.items() if k in allowed}


#: Top-level payload fields that carry per-dimension BAND dicts. Their leaves must be band
#: WORDS — the engine's typed dataclass guarantees this today, but that is a Python-type trust
#: boundary, not a runtime one. This assertion makes it structural at the serving seam: a future
#: engine/read-path change that puts a numeric (or any non-band value) into one of these dicts
#: 500s here instead of reaching an anonymous client (2026-07-05 W2-A adversarial-review
#: condition; complements — never replaces — the allowlist + denylist above).
_BAND_DICT_FIELDS: tuple[str, ...] = ("factors", "confidence_factors")
_BAND_WORDS: frozenset[str] = frozenset({"high", "medium", "low"})


def _assert_band_dicts(data: Any) -> None:
    """Fail-closed: every leaf of a band-dict field must be a band WORD (raises, never strips)."""
    if not isinstance(data, dict):
        return
    for field in _BAND_DICT_FIELDS:
        value = data.get(field)
        if value is None or not isinstance(value, dict):
            continue
        for k, v in value.items():
            if not (isinstance(v, str) and v in _BAND_WORDS):
                raise RuntimeError(
                    f"#2 boundary: band-dict field '{field}' key '{k}' carries a non-band value "
                    f"({type(v).__name__}) — only {sorted(_BAND_WORDS)} may reach a client"
                )


@dataclass(frozen=True)
class RequestCtx:
    """Per-request gating context.

    tier         — the caller's resolved tier (the paywall axis).
    gate_enabled — a gated concept is served ONLY if its §31 flag is EXPLICITLY enabled (admin/ops).
                   Default False → a gated concept is withheld (fail-closed). Money can NEVER set this.
    refused      — a runtime compliance refusal (e.g. scoring confidence < 0.30 → insufficient_data) →
                   the concept exists but is withheld with reason `refused`.
    """

    tier: str = "free"
    gate_enabled: bool = False
    refused: str | None = None


def _scrub(value: Any) -> Any:
    """Recursively drop FORBIDDEN_SCORE_KEYS from dicts/lists/sets — the #2 numeric-strip backstop."""
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if k not in FORBIDDEN_SCORE_KEYS}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_scrub(v) for v in value]
    return value


def _assert_no_forbidden(value: Any) -> None:
    """Hard fail-closed guard (raises — not `assert`, which `-O` strips): a #2 leak must 500, never reach
    the DOM. Also REFUSES any non-plain-JSON value (a Pydantic model, ORM Row, arbitrary object) the scrub
    can't see inside — callers pass plain dict/list/scalar so every key is scrubbable (review finding 2)."""
    if isinstance(value, dict):
        leaked = FORBIDDEN_SCORE_KEYS & value.keys()
        if leaked:
            raise RuntimeError(
                f"#2 violation: forbidden score key(s) {sorted(leaked)} at the boundary"
            )
        for v in value.values():
            _assert_no_forbidden(v)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for v in value:
            _assert_no_forbidden(v)
    elif value is not None and not isinstance(value, _SAFE_SCALARS):
        raise RuntimeError(
            f"#2 boundary: non-plain value of type {type(value).__name__} reached serialize_concept; "
            "pass plain JSON (dict/list/scalar) so the scrub can see every key"
        )


def serialize_concept(
    concept_id: str,
    data: Any,
    ctx: RequestCtx,
    *,
    as_of: str | None = None,
    is_stale: bool = False,
    source: str | None = None,
    disclaimer_version: str | None = None,
    engine_version: str | None = None,
    quality: float | None = None,
) -> dict[str, Any]:
    """Wrap a concept payload in the governance envelope (§5), enforcing IN ORDER:

      1. #2 NUMERIC STRIP (headline) — ALWAYS, before any decision: a raw DhanRadar score/weight/
         fair-value can never reach a client (recursive scrub + a fail-closed assertion), THEN the B87
         per-concept field ALLOWLIST (`ALLOWED_FIELDS`) — only a concept's declared top-level fields
         survive; the denylist above is a tripwire, the allowlist is the structural guarantee.
      2. GATED — `visibility_class == 'gated'` and the flag NOT explicitly enabled → withheld,
         reason `gated`, data null. Server-enforced; money cannot unlock it (the SEBI advice boundary).
      3. TIER — `access_tier == 'plus'` and the caller is below plus → withheld, reason `tier`, data
         null (the route returns HTTP 402; see `is_tier_withheld`).
      4. REFUSED — a runtime compliance refusal (ctx.refused) → withheld, reason `refused`, data null.

    Else status `present` + the scrubbed, allowlisted data + the registry-derived governance tags. This
    is the SOLE place the gating happens — no endpoint re-implements it. Returns a plain dict matching
    `DataEnvelope`. Raises `MissingConceptAllowlist` (fail-closed) if `concept_id` has no `ALLOWED_FIELDS`
    entry.
    """
    m = get_concept(concept_id)  # fail-closed: UnknownConcept on an un-registered id

    # 1. #2 numeric strip — unconditional, first (denylist tripwire + fail-closed non-plain check).
    data = _scrub(data)
    _assert_no_forbidden(data)

    # 1b. B87 ALLOWLIST — the structural guarantee: keep ONLY this concept's declared top-level fields.
    # Fail-closed (`MissingConceptAllowlist`) if the concept has no entry in `ALLOWED_FIELDS`.
    data = _apply_allowlist(concept_id, data)

    # 1c. Band-dict leaves must be band WORDS — closes the nested-numeric class the top-level
    # allowlist + name-based denylist cannot see (W2-A adversarial-review condition).
    _assert_band_dicts(data)

    status, reason, out = "present", None, data
    if m.visibility_class == "gated" and not ctx.gate_enabled:
        status, reason, out = "withheld", "gated", None
    # access_tier "plus" (the registry's paywall label) maps to the product's paid tier — Pro+
    # (deps._PRO_RANK, the same threshold is_plus uses). There is no literal "plus" subscription.
    elif m.access_tier == "plus" and _tier_rank(ctx.tier) < _PRO_RANK:
        status, reason, out = "withheld", "tier", None
    elif ctx.refused is not None:
        status, reason, out = "withheld", "refused", None

    return {
        "status": status,
        "data": out,
        "meta": {
            "reason": reason,
            "as_of": as_of,
            "is_stale": is_stale,
            "source": source,
            "visibility_class": m.visibility_class,
            "data_class": m.data_class,
            "access_tier": m.access_tier,
            "content_class": m.content_class,
            "gate": ({"flag": m.gate_flag, "enabled": ctx.gate_enabled} if m.gate_flag else None),
            "disclaimer_version": disclaimer_version,
            "engine_version": engine_version,
            "quality": quality,
        },
    }

def is_tier_withheld(envelope: dict[str, Any]) -> bool:
    """True iff this envelope was withheld for TIER — the route raises HTTP 402 (tier-gate = 402, §6)."""
    return envelope["status"] == "withheld" and envelope["meta"]["reason"] == "tier"


def _serialize_leaderboard_row(concept_id: str, row: dict) -> dict:
    """Apply the B87 allowlist for one board row; a champions row additionally
    allowlists its nested `winner`/`runner_up` FundRow sub-objects, and an
    insight row's `links` passes a nested fail-closed shape scrub."""
    row = _apply_allowlist(concept_id, row)
    if concept_id == "leaderboard.champion_row":
        if row.get("winner") is not None:
            row["winner"] = _apply_allowlist("leaderboard.fund_row", row["winner"])
        if row.get("runner_up") is not None:
            row["runner_up"] = _apply_allowlist("leaderboard.fund_row", row["runner_up"])
    if concept_id == "leaderboard.insight_row":
        # Entity links (2026-08-16), nested fail-closed: `links` survives ONLY as
        # a list of {name: non-empty str, isin: ^[A-Z0-9]{12}$} pairs, REBUILT
        # key-by-key (an extra key inside an item can never pass through). Any
        # malformed item is dropped; a non-list or fully-malformed value drops
        # the key entirely — text-only is always a valid row.
        links = row.get("links")
        clean_links: list[dict] = []
        if isinstance(links, list):
            for item in links:
                if (
                    isinstance(item, dict)
                    and isinstance(item.get("name"), str)
                    # Mirrors the writer's _LINK_MIN_NAME_LEN=5 floor (a
                    # degenerate short name would over-link mid-word) — the
                    # scrub re-enforces EVERY writer rule, not just the isin.
                    and len(item["name"]) >= 5
                    and isinstance(item.get("isin"), str)
                    and _INSIGHT_LINK_ISIN_RE.fullmatch(item["isin"])
                ):
                    clean_links.append({"name": item["name"], "isin": item["isin"]})
        if clean_links:
            row["links"] = clean_links
        else:
            row.pop("links", None)
    return row


def serialize_leaderboard_response(
    *, as_of: str | None, hero: dict[str, Any] | None, boards: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Fail-closed serialization for `GET /mf/leaderboard` (Phase 1,
    docs/features/leaderboard-data-backend.md §5) — the same #2 scrub + B87
    allowlist mechanism as `serialize_concept` above, applied per row SHAPE since a
    leaderboard payload isn't one flat concept, it's ~18 board shapes + a hero
    summary (`_LEADERBOARD_ROW_CONCEPT`). A leaderboard board is public educational
    content with no gating/tier axis (unlike `serialize_concept`'s registry-backed
    concepts, which are sourced from the frontend-generated concepts_registry.json)
    — this bypasses `get_concept()`/the withheld-status envelope entirely and applies
    the #2 scrub + fail-closed allowlist directly, still the same structural
    guarantee: a score field can never reach this response.

    `boards` maps board_key -> {"title": str, "rows": list[dict]}. Raises
    `MissingConceptAllowlist` (fail-closed) if a board_key has no entry in
    `_LEADERBOARD_ROW_CONCEPT`.
    """
    data = _scrub({"hero": hero, "boards": boards})
    _assert_no_forbidden(data)

    hero_clean: dict[str, Any] | None = None
    if data["hero"] is not None:
        hero_clean = _apply_allowlist("leaderboard.hero", data["hero"])
        if hero_clean.get("top_fund") is not None:
            hero_clean["top_fund"] = _apply_allowlist("leaderboard.fund_row", hero_clean["top_fund"])

    boards_clean: dict[str, dict[str, Any]] = {}
    for key, board in (data["boards"] or {}).items():
        concept_id = _LEADERBOARD_ROW_CONCEPT.get(key)
        if concept_id is None:
            raise MissingConceptAllowlist(
                f"leaderboard board '{key}' has no row-shape entry in "
                "_LEADERBOARD_ROW_CONCEPT (mf/serialization.py) — add one before serving it"
            )
        rows = [_serialize_leaderboard_row(concept_id, row) for row in board.get("rows", [])]
        out_board: dict[str, Any] = {"title": board.get("title"), "rows": rows}
        # V2 takeaway sentence (2026-08-16) — fail-closed: only a plain str passes
        # through; any other type (or absent key) is dropped silently, never raised.
        takeaway = board.get("takeaway")
        if isinstance(takeaway, str):
            out_board["takeaway"] = takeaway
        boards_clean[key] = out_board

    return {"as_of": as_of, "hero": hero_clean, "boards": boards_clean}


def serialize_watchlist_cards_response(
    *, as_of: str | None, items: list[dict[str, Any]]
) -> dict[str, Any]:
    """Fail-closed serialization for `GET /mf/watchlist/cards` (WATCHLIST_LIVE_DATA_
    PLAN.md Wave 1) — the same #2 scrub + B87 allowlist mechanism as
    `serialize_concept`, applied per card via the `mf.watchlist_card` row shape (the
    same bypass `serialize_leaderboard_response` uses above): a watchlist card is
    public fund-fact content composed server-side per caller ISIN, not itself a
    registry-gated concept, so this skips `get_concept()`/the withheld-status
    envelope and applies the #2 scrub + fail-closed allowlist directly — the same
    structural guarantee, a score field can never reach this response.
    """
    data = _scrub({"items": items})
    _assert_no_forbidden(data)
    cards = [_apply_allowlist("mf.watchlist_card", item) for item in data["items"]]
    return {"as_of": as_of, "items": cards}


def serialize_watchlist_changes_response(
    *, as_of: str | None, items: list[dict[str, Any]]
) -> dict[str, Any]:
    """Fail-closed serialization for `GET /mf/watchlist/changes` (WATCHLIST_LIVE_
    DATA_PLAN.md Wave 2) — same #2 scrub + B87 allowlist bypass pattern as
    `serialize_watchlist_cards_response`, applied via the `mf.watchlist_change`
    row shape.
    """
    data = _scrub({"items": items})
    _assert_no_forbidden(data)
    rows = [_apply_allowlist("mf.watchlist_change", item) for item in data["items"]]
    return {"as_of": as_of, "items": rows}


def serialize_watchlist_similar_response(
    *, as_of: str | None, items: list[dict[str, Any]]
) -> dict[str, Any]:
    """Fail-closed serialization for `GET /mf/watchlist/similar` (WATCHLIST_LIVE_
    DATA_PLAN.md Wave 2) — same #2 scrub + B87 allowlist bypass pattern as
    `serialize_watchlist_cards_response`, applied via the `mf.watchlist_similar`
    row shape.
    """
    data = _scrub({"items": items})
    _assert_no_forbidden(data)
    rows = [_apply_allowlist("mf.watchlist_similar", item) for item in data["items"]]
    return {"as_of": as_of, "items": rows}


def serialize_watchlist_ai_response(
    *,
    summary_items: list[str],
    insight_items: list[str],
    disclosure: str,
    not_advice: str,
    disclaimer_version: str,
) -> dict[str, Any]:
    """Fail-closed serialization for `GET /mf/watchlist/summary` (WATCHLIST_LIVE_
    DATA_PLAN.md Wave 3) — same #2 scrub + B87 allowlist bypass pattern as
    `serialize_watchlist_cards_response`. Each item is wrapped `{"text": item}`
    before the scrub/allowlist run, so a poisoned item dict (e.g. a smuggled
    `score`/`unified_score` key riding along with the text) is caught by
    `_assert_no_forbidden` and stripped to `text` only by the `mf.watchlist_ai_item`
    allowlist — only plain item TEXT plus the four top-level compliance fields
    ever reach the client; no model name, confidence float, or raw gateway
    metadata is ever passed in.
    """
    data = _scrub(
        {
            "summary_items": [{"text": t} for t in summary_items],
            "insight_items": [{"text": t} for t in insight_items],
            "disclosure": disclosure,
            "not_advice": not_advice,
            "disclaimer_version": disclaimer_version,
        }
    )
    _assert_no_forbidden(data)
    summary = [_apply_allowlist("mf.watchlist_ai_item", item).get("text", "") for item in data["summary_items"]]
    insights = [_apply_allowlist("mf.watchlist_ai_item", item).get("text", "") for item in data["insight_items"]]
    return {
        "summary_items": summary,
        "insight_items": insights,
        "disclosure": data["disclosure"],
        "not_advice": data["not_advice"],
        "disclaimer_version": data["disclaimer_version"],
    }


def serialize_compare_bundle_response(
    *, isins: list[str], fragments: dict[str, Any], as_of: str | None
) -> dict[str, Any]:
    """Fail-closed serialization for ``GET /mf/compare/bundle`` (COMPARE_LIVE_DATA_
    PLAN.md Wave C1) — same #2 scrub + B87 allowlist bypass pattern as
    ``serialize_leaderboard_response``.

    Three nested allowlists enforce defence-in-depth on the benchmark series
    (``mf.compare_benchmark``), SIP illustrations (``mf.compare_sip``), and each
    per-ISIN fragment (``mf.compare_fragment``) — the architect review condition
    that the benchmark be "serialized through new mf.compare_* allowlists, never
    embedded raw" is satisfied by the nested scrub below (a benchmark dict with any
    extra key is reduced to only {label, is_fallback, points, window} before it can
    reach the client).
    """
    data = _scrub({"isins": isins, "fragments": fragments, "as_of": as_of})
    _assert_no_forbidden(data)

    clean_fragments: dict[str, dict[str, Any] | None] = {}
    for isin, frag in (data["fragments"] or {}).items():
        if frag is None:
            clean_fragments[isin] = None
            continue
        frag = _apply_allowlist("mf.compare_fragment", frag)
        # Nested benchmark allowlist — never embedded raw (architect condition).
        if frag.get("benchmark") is not None:
            frag["benchmark"] = _apply_allowlist("mf.compare_benchmark", frag["benchmark"])
        # Nested SIP allowlists (one per fixed illustration slot).
        for sip_key in ("sip_5y", "sip_10y"):
            if frag.get(sip_key) is not None:
                frag[sip_key] = _apply_allowlist("mf.compare_sip", frag[sip_key])
        clean_fragments[isin] = frag

    bundle = _apply_allowlist("mf.compare_bundle", data)
    bundle["fragments"] = clean_fragments
    return bundle
