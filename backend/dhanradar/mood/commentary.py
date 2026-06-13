"""
DhanRadar — Market Mood AI commentary (B35-e).

The second governed AI-gateway consumer (after MF portfolio commentary, 2b967d7).
Generates a short, EDUCATIONAL description of the current market-mood regime — what the
snapshot's contributing/contradicting signals say about sentiment — NEVER advice, never a
numeric mood score.

Mood is MARKET-WIDE aggregate data with NO user PII, so unlike MF commentary there is no
consent gate and `contains_personal_data=False`. The remaining governed gates still apply:

  CALL   — gateway.complete() on the non-personal path (B20).
  FLOOR  — confidence < 0.30 → log_low_confidence (B22), withhold (return None).
  AUDIT  — record_served_label (B21/B26) for the served AI-commentary surface.

Best-effort: this NEVER raises. Any failure (gateway/budget error, low confidence) returns
None so the snapshot still publishes its regime label with no commentary (mirrors the MF
fire-and-forget contract). The Mood service applies a SECOND advisory-verb screen over the
returned text before persisting (defense in depth, non-neg #1), and only calls this when the
snapshot's own `commentary_allowed` gate is set (>= 7 signals, confidence >= 0.40).

Module isolation: touches ai_gateway + compliance interfaces only. No scoring, no billing.
"""

from __future__ import annotations

import json

from pydantic import Field

from dhanradar.ai_gateway.errors import ConsentNotVerifiedError, GatewayError
from dhanradar.ai_gateway.schemas import AIOutputBase
from dhanradar.budget import BudgetExhaustedError
from dhanradar.compliance.service import (
    active_disclaimer_version,
    log_low_confidence,
    record_served_label,
)
from dhanradar.mood.compute import MoodResult

_SURFACE = "mood_commentary"
_TASK_TYPE = "mood_commentary"
_CONFIDENCE_FLOOR = 0.30


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class MoodCommentary(AIOutputBase):
    """AI output schema for market-mood commentary.

    Extends ``AIOutputBase`` — inherits the advisory screen (QualityValidator walks ALL
    string fields of the dump), the >=2 contributing-signals floor, and the
    non-strippable disclaimer. Adds a free-text ``commentary`` field. No numeric mood
    score / weight (non-neg #2 — no numeric in DOM). The field MUST stay a plain ``str``
    so the recursive advisory screen reaches it (non-neg #1).
    """

    commentary: str = Field(
        min_length=1,
        description=(
            "Educational, descriptive commentary on the current market-mood regime — "
            "no advice. Describes what the contributing/contradicting market signals "
            "indicate about overall sentiment in plain, factual language."
        ),
    )


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an educational assistant for Indian retail investors. "
    "Your role is to DESCRIBE the current market-mood regime in plain, factual language: "
    "what the contributing and contradicting market signals indicate about overall "
    "sentiment. "
    "NEVER give buy/sell/hold/switch/avoid advice or recommend any action, asset, sector, "
    "or market-timing. "
    "NEVER state a numeric mood score, confidence number, index level, or price target. "
    "Output STRICT JSON matching this schema exactly:\n"
    "{\n"
    '  "confidence": <float 0.0-1.0>,\n'
    '  "confidence_band": <"high"|"medium"|"low">,\n'
    '  "contributing_signals": [<string>, ...],  // >= 2 items\n'
    '  "contradicting_signals": [<string>, ...],  // may be empty\n'
    '  "commentary": "<educational description of the market mood — no advice>"\n'
    "}\n"
    "contributing_signals must list >= 2 observable market signals that informed the "
    "regime (e.g. Nifty trend, India VIX, FII flows). "
    "If confidence > 0.7, list >= 3 contributing_signals."
)


def build_messages(result: MoodResult) -> list[dict[str, str]]:
    """Build a compact, PII-free prompt from the mood snapshot.

    Sends ONLY the regime label, confidence band, data-quality, and the raw signal keys
    that contributed/contradicted — NEVER the numeric mood_score or confidence float
    (non-neg #2). Deterministic and small so token cost stays bounded and the gateway's
    quality validator can screen the response.
    """
    mood_view = {
        "regime": result.regime,
        "confidence_band": result.confidence_band,
        "data_quality": result.data_quality,
        "contributing_signals": list(result.contributing_factors),
        "contradicting_signals": list(result.contradicting_factors),
    }
    user_content = (
        "Describe the current market mood for an educational audience.\n"
        f"Mood snapshot: {json.dumps(mood_view, separators=(',', ':'))}"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def generate_mood_commentary(
    gateway: object,
    *,
    result: MoodResult,
    request_id: str | None = None,
) -> str | None:
    """Generate educational mood commentary via the governed gateway.

    Returns the commentary string, or ``None`` when withheld (low confidence, gateway or
    budget error). NEVER raises — best-effort, mirrors ``mf.commentary``. The Mood service
    applies a second advisory screen and persists the result into ``market_mood.ai_commentary``.
    """
    disclaimer_version = active_disclaimer_version()

    # ------------------------------------------------------------------
    # Gate CALL — non-personal aggregate market data (no consent gate).
    # ------------------------------------------------------------------
    msgs = build_messages(result)
    try:
        res = await gateway.complete(  # type: ignore[attr-defined]
            task_type=_TASK_TYPE,
            messages=msgs,
            schema=MoodCommentary,
            contains_personal_data=False,
            request_id=request_id,
        )
    # GatewayError covers credit/quality/empty-pool/3-strike; ConsentNotVerifiedError is the
    # gateway's bare-Exception default-deny backstop; BudgetExhaustedError is the budget cap.
    except (GatewayError, BudgetExhaustedError, ConsentNotVerifiedError):
        return None

    # ------------------------------------------------------------------
    # Gate FLOOR (B22) — withhold below the confidence floor.
    # ------------------------------------------------------------------
    if res.output.confidence < _CONFIDENCE_FLOOR:
        await log_low_confidence(
            surface=_SURFACE,
            confidence_score=res.output.confidence,
            confidence_band=res.output.confidence_band,
            model=res.model_used,
            reason="below_floor",
            identifier=result.regime,
            request_id=request_id,
        )
        return None

    # ------------------------------------------------------------------
    # Gate AUDIT (B21/B26) — record the served AI-commentary surface.
    # ------------------------------------------------------------------
    await record_served_label(
        surface=_SURFACE,
        label="ai_commentary",
        model=res.model_used,
        disclaimer_version=disclaimer_version,
        recommendation_type="educational_label",
        identifier=result.regime,
        confidence_band=res.output.confidence_band,
        request_id=request_id,
    )

    return res.output.commentary
