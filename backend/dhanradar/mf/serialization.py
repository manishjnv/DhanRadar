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
