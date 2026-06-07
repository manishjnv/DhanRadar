"""
DhanRadar — MF portfolio AI commentary (B20/B21/B22 gated).

The first AI consumer in the governed gateway pipeline. Generates an educational,
descriptive commentary on a user's MF portfolio: diversification, category mix,
and concentration — NEVER advice, never numeric scores in the public payload.

Four-gate wiring order (per architecture §B3 / B20 / B21 / B22):
  1. CONSENT  — assert cross_border_ai granted (B20); refuse without calling gateway.
  2. CALL     — gateway.complete() with personal-data flag + verified consent (B20).
  3. FLOOR    — confidence < 0.30 → log low-confidence event (B22), return insufficient_data.
  4. AUDIT    — record_served_label (B21), return public payload (no numeric confidence).

Module isolation: only touches ai_gateway + compliance + deps interfaces.
No billing, no scoring imports.
"""

from __future__ import annotations

import json

from pydantic import Field

from dhanradar.ai_gateway.errors import ConsentNotVerifiedError, GatewayError
from dhanradar.ai_gateway.schemas import AI_DISCLAIMER, AIOutputBase
from dhanradar.budget import BudgetExhaustedError
from dhanradar.compliance.service import (
    active_disclaimer_version,
    log_low_confidence,
    record_served_label,
)
from dhanradar.deps import ConsentRequiredError, assert_consent

_SURFACE = "mf_commentary"
_CONFIDENCE_FLOOR = 0.30


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class MFCommentary(AIOutputBase):
    """AI output schema for MF portfolio commentary.

    Extends ``AIOutputBase`` — inherits all base invariants (signal floors,
    disclaimer enforcement, advisory screen via QualityValidator). Adds a
    free-text ``commentary`` field. No numeric score/factor/fair-value fields
    (non-negotiable #2 — no numeric in DOM).
    """

    # INVARIANT: every string field added here is screened by QualityValidator's
    # advisory net (quality.py walks ALL string fields of the model dump). Any new
    # free-text field is therefore covered automatically — but it MUST remain a
    # plain str/list[str] so the recursive screen reaches it (non-neg #1).
    commentary: str = Field(
        min_length=1,
        description=(
            "Educational, descriptive portfolio commentary — no advice. "
            "Describes diversification, category mix, and concentration."
        ),
    )


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an educational assistant for Indian retail mutual-fund investors. "
    "Your role is to DESCRIBE the portfolio's diversification, category mix, and "
    "concentration in plain, factual language. "
    "NEVER give buy/sell/hold/switch/avoid advice or recommend any action. "
    "NEVER mention specific rupee amounts, folio numbers, or personal identifiers. "
    "Output STRICT JSON matching this schema exactly:\n"
    "{\n"
    '  "confidence": <float 0.0–1.0>,\n'
    '  "confidence_band": <"high"|"medium"|"low">,\n'
    '  "contributing_signals": [<string>, ...],  // >= 2 items\n'
    '  "contradicting_signals": [<string>, ...],  // may be empty\n'
    '  "commentary": "<educational description — no advice>"\n'
    "}\n"
    "contributing_signals must list >= 2 observable portfolio features that informed "
    "the commentary (e.g. category concentration, overlap). "
    "If confidence > 0.7, list >= 3 contributing_signals."
)


def build_messages(snapshot: object, funds: list[dict]) -> list[dict[str, str]]:
    """Build the prompt message list for the gateway.

    Serialises a COMPACT, PII-free view of the portfolio — no user_id, no
    folio_number, no raw rupee amounts. Deterministic and small so token cost
    stays bounded and the gateway's quality validator can screen the response.
    """
    # Category allocation from the snapshot (no raw amounts).
    category_allocation: dict = {}
    if hasattr(snapshot, "category_allocation") and snapshot.category_allocation:
        category_allocation = snapshot.category_allocation

    # Overlap matrix presence (boolean — not the full matrix).
    has_overlap = bool(
        hasattr(snapshot, "overlap_matrix")
        and snapshot.overlap_matrix
    )

    # XIRR expressed as a band to avoid surfacing numeric precision.
    xirr_pct: float | None = getattr(snapshot, "xirr_pct", None)
    if xirr_pct is None:
        xirr_band = "unknown"
    elif xirr_pct >= 12.0:
        xirr_band = "above_12pct"
    elif xirr_pct >= 8.0:
        xirr_band = "8_to_12pct"
    elif xirr_pct >= 0.0:
        xirr_band = "0_to_8pct"
    else:
        xirr_band = "negative"

    portfolio_view = {
        "num_funds": len(funds),
        "category_allocation": category_allocation,
        "has_overlap_data": has_overlap,
        "xirr_band": xirr_band,
    }

    user_content = (
        "Analyse this portfolio summary and provide educational commentary.\n"
        f"Portfolio: {json.dumps(portfolio_view, separators=(',', ':'))}"
    )

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def generate_commentary(
    gateway: object,
    *,
    user_id: str,
    db: object,
    snapshot: object,
    funds: list[dict],
    request_id: str | None = None,
) -> dict:
    """Generate MF portfolio commentary with B20/B21/B22 gates.

    Returns a dict with ``state`` key:
      - ``"ok"``               — commentary served; includes commentary + compliance fields.
      - ``"insufficient_data"`` — confidence below floor; includes disclaimer only.
      - ``"unavailable"``      — consent denied, budget exhausted, or gateway error.

    NEVER raises — all errors are translated to the ``"unavailable"`` payload so
    the pipeline caller can treat this as best-effort (mirrors fire-and-forget
    audit pattern).
    """
    disclaimer = AI_DISCLAIMER
    disclaimer_version = active_disclaimer_version()

    # ------------------------------------------------------------------
    # Gate 1 — CONSENT (B20): refuse before touching the gateway.
    # ------------------------------------------------------------------
    try:
        await assert_consent(user_id, "cross_border_ai", db)  # type: ignore[arg-type]
    except ConsentRequiredError:
        return {
            "state": "unavailable",
            "reason": "consent_required",
            "disclaimer": disclaimer,
            "disclaimer_version": disclaimer_version,
        }
    except ValueError:
        # assert_consent raises ValueError only on an unknown purpose (a programming
        # error — the purpose here is a hardcoded valid constant, so this is currently
        # unreachable). Catch it anyway to honor the never-raises contract and fail
        # CLOSED: refuse without ever building a payload or touching the gateway.
        return {
            "state": "unavailable",
            "reason": "consent_gate_error",
            "disclaimer": disclaimer,
            "disclaimer_version": disclaimer_version,
        }

    # ------------------------------------------------------------------
    # Gate 2 — CALL: build messages and invoke the gateway.
    # ------------------------------------------------------------------
    msgs = build_messages(snapshot, funds)
    try:
        res = await gateway.complete(  # type: ignore[attr-defined]
            task_type="mf_pick",
            messages=msgs,
            schema=MFCommentary,
            contains_personal_data=True,
            cross_border_consent_verified=True,
        )
    # CreditExhaustedError, AllFreeModelsFailedError, QualityValidationError and
    # ThreeStrikeSkipError all subclass GatewayError, so the 402/credit, empty-pool
    # and quality/skip paths are all caught here. ConsentNotVerifiedError (the gateway
    # default-deny backstop) is a bare Exception, so it is listed explicitly.
    except (GatewayError, BudgetExhaustedError, ConsentNotVerifiedError) as exc:
        return {
            "state": "unavailable",
            "reason": type(exc).__name__,
            "disclaimer": disclaimer,
            "disclaimer_version": disclaimer_version,
        }

    # ------------------------------------------------------------------
    # Gate 3 — CONFIDENCE FLOOR (B22): log and return insufficient_data.
    # ------------------------------------------------------------------
    if res.output.confidence < _CONFIDENCE_FLOOR:
        await log_low_confidence(
            surface=_SURFACE,
            confidence_score=res.output.confidence,
            confidence_band=res.output.confidence_band,
            model=res.model_used,
            reason="below_floor",
            identifier=None,
            request_id=request_id,
        )
        return {
            "state": "insufficient_data",
            "disclaimer": disclaimer,
            "disclaimer_version": disclaimer_version,
        }

    # ------------------------------------------------------------------
    # Gate 4 — AUDIT (B21) + SERVE: write audit row, return public payload.
    # CRITICAL: confidence float is NEVER included in the returned dict (non-neg #2).
    # ------------------------------------------------------------------
    await record_served_label(
        surface=_SURFACE,
        label="ai_commentary",
        model=res.model_used,
        disclaimer_version=disclaimer_version,
        recommendation_type="educational_label",
        user_id=user_id,
        identifier=None,
        confidence_band=res.output.confidence_band,
        request_id=request_id,
    )

    return {
        "state": "ok",
        "commentary": res.output.commentary,
        "confidence_band": res.output.confidence_band,
        "contributing_signals": res.output.contributing_signals,
        "contradicting_signals": res.output.contradicting_signals,
        "disclaimer": res.output.disclaimer,
        "disclaimer_version": disclaimer_version,
    }
