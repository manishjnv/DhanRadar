"""The single serialization boundary (A3, UI_DATA_ARCHITECTURE_PLAN.md §5/§6/§7/§10 layer 8).

The ONE backend place that enforces non-negotiable #2 (no-numeric-in-DOM), visibility gating, and tier
gating, producing the `DataEnvelope` (§5) for every served concept. Defense-in-depth WITH RLS behind it:
RLS (I5) decides WHO sees WHOSE rows; this boundary decides WHAT framing (#2/visibility) and WHO PAID
(tier). They are complementary (§6) — neither replaces the other.

RULE: a concept payload reaches a client ONLY through `serialize_concept`. No endpoint re-implements the
gating; the I1/I2/tier fixtures red the build if a raw score leaks or a gate is bypassed.
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
#: This is a DENYLIST — it catches a raw-score key by KNOWN name. The per-concept structural guarantee is
#: the payload BUILDER being explicit (the pilot serves holdings with NO score field at all). A score
#: emitted under a NOVEL key (e.g. `rating`, `percentile`) would slip the generic scrub, so a
#: registry-declared serializable-field ALLOWLIST is the planned hardening (BLOCKERS B87) — required
#: before a second SCORED concept is served through this boundary. The I1 fixture guards the known names.
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
            raise RuntimeError(f"#2 violation: forbidden score key(s) {sorted(leaked)} at the boundary")
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
         fair-value can never reach a client (recursive scrub + a fail-closed assertion).
      2. GATED — `visibility_class == 'gated'` and the flag NOT explicitly enabled → withheld,
         reason `gated`, data null. Server-enforced; money cannot unlock it (the SEBI advice boundary).
      3. TIER — `access_tier == 'plus'` and the caller is below plus → withheld, reason `tier`, data
         null (the route returns HTTP 402; see `is_tier_withheld`).
      4. REFUSED — a runtime compliance refusal (ctx.refused) → withheld, reason `refused`, data null.

    Else status `present` + the scrubbed data + the registry-derived governance tags. This is the SOLE
    place the gating happens — no endpoint re-implements it. Returns a plain dict matching `DataEnvelope`.
    """
    m = get_concept(concept_id)  # fail-closed: UnknownConcept on an un-registered id

    # 1. #2 numeric strip — unconditional, first.
    data = _scrub(data)
    _assert_no_forbidden(data)

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
