"""
DhanRadar — Market-mood NEWS SENTIMENT signal (Phase 2, 11th mood factor).

A governed AI-gateway consumer (mirrors mood.commentary's call order). It pulls the
last ~48h of news_items HEADLINE TITLES (no body — the model stores none), asks the
gateway to rate the OVERALL news tone toward the equity market on a DESCRIPTIVE
5-point scale, and maps that label to the engine's 0–1 news_sentiment input
(1 = greed/bullish) via signals.norm_news_sentiment.

Mood is MARKET-WIDE aggregate data with NO user PII, so `contains_personal_data=False`
and there is no consent gate. Governed gates that still apply:

  CALL   — gateway.complete() on the non-personal path (B20). The gateway's
           QualityValidator screens the output for advisory verbs and rejects it
           (→ GatewayError) if any appear.
  FLOOR  — confidence < 0.30 → withhold (return None); the signal is then absent and
           the engine drops it (never imputed).

Best-effort: this NEVER raises. No headlines, a gateway/budget error, a low-confidence
read, or an advisory-verb rejection all return None — the signal is simply absent and
the mood engine degrades gracefully (coverage decrements, nothing is fabricated).

The value feeds the SERVER-SIDE score only; it never reaches the DOM (non-neg #2).

Module isolation: touches ai_gateway + a news read interface only. No scoring, no billing.
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import Field

from dhanradar.ai_gateway.errors import ConsentNotVerifiedError, GatewayError
from dhanradar.ai_gateway.schemas import AIOutputBase
from dhanradar.budget import BudgetExhaustedError
from dhanradar.mood.signals import norm_news_sentiment

logger = logging.getLogger(__name__)

_TASK_TYPE = "news_sentiment"
_CONFIDENCE_FLOOR = 0.30
_LOOKBACK_HOURS = 48
_MAX_HEADLINES = 30

NewsTone = Literal[
    "negative", "slightly_negative", "neutral", "slightly_positive", "positive"
]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class NewsSentiment(AIOutputBase):
    """AI output schema for the news-sentiment signal.

    Extends ``AIOutputBase`` — inherits the advisory screen (QualityValidator walks ALL
    string fields), the >=2 contributing-signals floor, and the non-strippable disclaimer.
    The model emits a DESCRIPTIVE tone LABEL, never a raw number — the numeric mapping to
    the engine's 0–1 scale happens server-side in ``norm_news_sentiment``.
    """

    tone: NewsTone = Field(
        description=(
            "Overall descriptive tone of the recent market news flow toward the equity "
            "market — one of: negative, slightly_negative, neutral, slightly_positive, "
            "positive. A description of sentiment in the headlines, NOT a market prediction."
        ),
    )


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an educational assistant for Indian retail investors. "
    "You are given a list of recent market news HEADLINES (titles only). "
    "Assess the OVERALL TONE of this news flow toward the equity market and classify it as "
    "exactly one of: negative, slightly_negative, neutral, slightly_positive, positive. "
    "This is a DESCRIPTIVE reading of the sentiment present in the headlines — NOT a market "
    "prediction, NOT a forecast, and NOT advice. "
    "NEVER recommend any action and NEVER use buy/sell/hold/switch/avoid language. "
    "NEVER state an index level, price, target, or return figure. "
    "Output STRICT JSON matching this schema exactly:\n"
    "{\n"
    '  "confidence": <float 0.0-1.0>,\n'
    '  "confidence_band": <"high"|"medium"|"low">,\n'
    '  "contributing_signals": [<string>, ...],  // >= 2 headline themes that set the tone\n'
    '  "contradicting_signals": [<string>, ...],  // headline themes pulling the other way\n'
    '  "tone": <"negative"|"slightly_negative"|"neutral"|"slightly_positive"|"positive">\n'
    "}\n"
    "contributing_signals must list >= 2 headline THEMES (not advice) that informed the tone. "
    "If confidence > 0.7, list >= 3 contributing_signals."
)


def build_messages(headlines: list[str]) -> list[dict[str, str]]:
    """Build a compact prompt from headline titles only. No body, no PII, no numbers
    supplied by us — deterministic and small so token cost stays bounded and the
    gateway's quality validator can screen the response."""
    user_content = (
        "Classify the overall tone of these recent market news headlines.\n"
        f"Headlines: {json.dumps(headlines, separators=(',', ':'))}"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def fetch_news_sentiment(
    gateway: object,
    db: object,
    *,
    request_id: str | None = None,
) -> float | None:
    """Return the normalized news-sentiment value in [0, 1] (1 = greed), or None.

    None is returned (signal absent — never imputed) when: there are no recent
    headlines, the news read fails, the gateway/budget errors, the model output trips
    the advisory screen, the confidence is below the floor, or the tone is unrecognised.
    NEVER raises — best-effort, mirrors mood.commentary.
    """
    # Pull recent headline titles (the sentiment input).
    try:
        from dhanradar.news.service import get_recent_headlines

        headlines = await get_recent_headlines(
            db,  # type: ignore[arg-type]
            hours=_LOOKBACK_HOURS,
            limit=_MAX_HEADLINES,
        )
    except Exception:  # noqa: BLE001 — a news-read failure must not crash the pipeline
        logger.warning("mood.news_sentiment: headline read failed — signal absent")
        return None

    if not headlines:
        logger.info("mood.news_sentiment: no recent headlines — signal absent")
        return None

    # Gate CALL — non-personal aggregate data (no consent gate). The gateway's
    # QualityValidator rejects any advisory verb in the output (→ GatewayError).
    msgs = build_messages(headlines)
    try:
        res = await gateway.complete(  # type: ignore[attr-defined]
            task_type=_TASK_TYPE,
            messages=msgs,
            schema=NewsSentiment,
            contains_personal_data=False,
            request_id=request_id,
        )
    # ConsentNotVerifiedError cannot fire here (contains_personal_data=False), but is
    # caught defensively: if a future change accidentally flips that flag, this fails
    # SOFT (signal absent) rather than crashing the mood pipeline. Do not remove.
    except (GatewayError, BudgetExhaustedError, ConsentNotVerifiedError):
        logger.info("mood.news_sentiment: gateway withheld output — signal absent")
        return None

    # Gate FLOOR — withhold below the confidence floor.
    if res.output.confidence < _CONFIDENCE_FLOOR:
        logger.info("mood.news_sentiment: below confidence floor — signal absent")
        return None

    # Descriptive tone label → server-side 0–1 score (never reaches the DOM).
    return norm_news_sentiment(res.output.tone)
