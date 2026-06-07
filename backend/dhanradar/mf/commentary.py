"""
DhanRadar — MF portfolio-level AI commentary: the first AI-gateway consumer.

Commentary is NON-BLOCKING: any refusal, gate failure, or unexpected exception
returns ``None``; the report is ALWAYS served without commentary rather than
failing. See architecture §MF line 257.

Four governance gates, in order:

  B20 — cross-border DPDP consent (``cross_border_ai``) verified before any
        personal data reaches OpenRouter.
  B21 — audit row written to ``ai_recommendation_audit`` for every served
        commentary (``record_served_label``, surface="mf_report_ai").
  B22 — confidence floor: ``< 0.30`` (or no usable labels) → log low-confidence
        event and omit commentary.
  B23 — defense-in-depth advisory screen: a regex over the published ``summary``
        catches advisory verbs that slipped past the gateway's own
        ``QualityValidator`` screen (two independent nets before publish).

B26 — the audit row carries ``prompt_version``, ``model_used``, and
      ``disclaimer_version`` so every served AI surface is traceable to the
      in-force disclaimer and the model that generated it.
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any, Optional

from pydantic import Field

from dhanradar.ai_gateway.schemas import AI_DISCLAIMER, AIOutputBase

_SURFACE = "mf_report_ai"
_TASK_TYPE = "mf_commentary"
_PROMPT_VERSION = "mf_commentary_v1"
_REFUSE_CONFIDENCE = 0.30          # non-neg #4 confidence floor (B22)
_INSUFFICIENT_LABEL = "insufficient_data"
_MIN_USABLE_FUNDS = 1              # need >=1 labelled fund to have anything to say

# Defense-in-depth advisory screen over the PUBLISHED summary (B23). complete()
# already screens via quality.py; this is a second, independent net before publish.
_ADVISORY_RE = re.compile(
    r"\b(strong[\s_]?buy|strong[\s_]?sell|buy|sell|hold|switch|avoid|caution)\b", re.IGNORECASE
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

class MfPortfolioCommentary(AIOutputBase):
    """Portfolio-level educational commentary. Inherits the AIOutputBase invariants
    (>=2 contributing signals, forced disclaimer, confidence band)."""

    summary: str = Field(min_length=1, description="Plain-English educational read of the labelled portfolio.")


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an educational financial information assistant for DhanRadar, a "
    "SEBI-educational (not advisory) market-intelligence platform for Indian retail investors. "
    "Your role is to provide DESCRIPTIVE, educational commentary about a user's mutual fund "
    "portfolio based only on the fund labels provided. "
    "\n\n"
    "STRICT RULES:\n"
    "1. You MUST NOT issue or imply any buy / sell / hold / switch / avoid recommendation "
    "   for any fund or the portfolio as a whole.\n"
    "2. You MUST NOT reference any numeric scores, factor weights, or fair-value estimates — "
    "   use only the label strings and confidence bands provided.\n"
    "3. Describe what the fund labels collectively suggest in plain English, in an educational "
    "   framing (e.g. 'several funds appear to be performing relative to benchmark', NOT "
    "   'you should buy more equity funds').\n"
    "4. Output MUST be a single JSON object with exactly these keys:\n"
    "   - confidence: float 0–1 reflecting how complete and consistent the portfolio label data is\n"
    "   - confidence_band: one of 'high', 'medium', 'low'\n"
    "   - contributing_signals: array of >=2 short strings (the signals that support the read)\n"
    "   - contradicting_signals: array of short strings (may be empty, but include disagreements)\n"
    "   - summary: a short plain-English paragraph describing what the fund labels collectively "
    "     suggest, in strict educational framing\n"
    "5. No other keys are permitted. Do not include any prose outside the JSON object."
)


# ---------------------------------------------------------------------------
# Data minimization helper
# ---------------------------------------------------------------------------

def build_messages(funds: list[dict], category_allocation: dict) -> list[dict[str, str]]:
    """Build the LLM message list for the portfolio commentary request.

    DATA MINIMIZATION (DPDP B20): the user message includes ONLY the fields
    needed for educational commentary — ``verb_label``, ``confidence_band``,
    ``contributing_signals``, ``contradicting_signals`` — plus the portfolio
    ``category_allocation``. PII fields (``isin``, ``scheme_name``,
    ``folio_number``, ``units``, ``invested_amount``, ``current_value``) are
    intentionally excluded so they never reach OpenRouter.

    ``category_allocation`` is included verbatim: by the ``build_snapshot``
    contract (``mf/snapshot.py``) its keys are fund-CATEGORY labels (e.g.
    "uncategorized", "Equity") and its values are aggregate percentages — never
    fund identifiers (ISIN/folio/scheme). It carries no per-fund PII.
    """
    _PII_KEYS = frozenset({
        "isin", "scheme_name", "folio_number", "units",
        "invested_amount", "current_value",
    })
    _KEEP_KEYS = frozenset({
        "verb_label", "confidence_band",
        "contributing_signals", "contradicting_signals",
    })

    minimized = [
        {k: v for k, v in fund.items() if k in _KEEP_KEYS}
        for fund in funds
    ]

    user_content = json.dumps(
        {"funds": minimized, "category_allocation": category_allocation}
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Main consumer
# ---------------------------------------------------------------------------

async def maybe_generate_commentary(
    *,
    user_id: str,
    job_id: str,
    funds: list[dict],
    category_allocation: dict,
    db: Any,
    disclaimer_version: str,
    gateway: Any = None,
) -> Optional[str]:
    """Return the published commentary string, or None to OMIT it. NEVER raises:
    every refusal/failure path returns None so the report still serves."""
    try:
        # Lazy imports to avoid circular-import cycles at module level.
        from dhanradar.compliance import service as compliance_service
        from dhanradar.deps import ConsentRequiredError, assert_consent

        # ------------------------------------------------------------------
        # B20 — cross-border DPDP consent gate
        # ------------------------------------------------------------------
        try:
            await assert_consent(user_id, "cross_border_ai", db)
        except ConsentRequiredError:
            logger.info(
                "mf_commentary: cross_border_ai consent absent for user=%s job=%s — omit",
                user_id, job_id,
            )
            return None

        # ------------------------------------------------------------------
        # B22 pre-call — require at least _MIN_USABLE_FUNDS labelled funds
        # ------------------------------------------------------------------
        usable = [
            f for f in funds
            if f.get("verb_label") and f["verb_label"] != _INSUFFICIENT_LABEL
        ]
        if len(usable) < _MIN_USABLE_FUNDS:
            await compliance_service.log_low_confidence(
                surface=_SURFACE,
                confidence_score=None,
                confidence_band=_INSUFFICIENT_LABEL,
                model=None,
                reason="portfolio_no_usable_labels",
                identifier=job_id,
            )
            return None

        # ------------------------------------------------------------------
        # Build messages + call the gateway
        # ------------------------------------------------------------------
        # Lazy-import OpenRouterGateway here — AFTER the gates — so an omitted
        # path never constructs a client or opens a network connection.
        from dhanradar.ai_gateway import OpenRouterGateway

        gw = gateway or OpenRouterGateway()
        messages = build_messages(usable, category_allocation)

        result = await gw.complete(
            task_type=_TASK_TYPE,
            messages=messages,
            schema=MfPortfolioCommentary,
            contains_personal_data=True,
            cross_border_consent_verified=True,  # verified above via assert_consent
        )
        output = result.output
        model_used = result.model_used

        # ------------------------------------------------------------------
        # B22 post-call — confidence floor (non-neg #4)
        # ------------------------------------------------------------------
        # A non-finite confidence (NaN/inf) must be treated as BELOW the floor:
        # `nan < 0.30` is False in Python, so a naive comparison would fail OPEN
        # and publish an un-graded commentary. isfinite() closes that gap.
        if not math.isfinite(output.confidence) or output.confidence < _REFUSE_CONFIDENCE:
            await compliance_service.log_low_confidence(
                surface=_SURFACE,
                confidence_score=output.confidence if math.isfinite(output.confidence) else None,
                confidence_band=output.confidence_band,
                model=model_used,
                reason="model_confidence_below_floor",
                identifier=job_id,
            )
            return None

        # ------------------------------------------------------------------
        # B23 defense-in-depth advisory screen
        # ------------------------------------------------------------------
        if _ADVISORY_RE.search(output.summary):
            logger.error(
                "mf_commentary: advisory verb detected in summary — withheld "
                "job=%s model=%s",
                job_id, model_used,
            )
            return None

        # ------------------------------------------------------------------
        # B21 / B26 audit — record served AI surface
        # ------------------------------------------------------------------
        # record_served_label is fire-and-forget (never raises) by its own
        # contract; the local try/except is belt-and-suspenders so an audit-layer
        # change can never suppress a clean, already-screened commentary. House
        # posture is serve + alert-on-audit-failure (see the per-fund B26 call in
        # tasks/mf.py), not audit-or-nothing.
        try:
            await compliance_service.record_served_label(
                surface=_SURFACE,
                label=None,
                model=model_used,
                disclaimer_version=disclaimer_version,
                recommendation_type="educational_label",
                user_id=user_id,
                identifier=job_id,
                confidence_band=output.confidence_band,
                prompt_version=_PROMPT_VERSION,
            )
        except Exception:  # noqa: BLE001 — audit must never drop a served commentary
            logger.exception(
                "mf_commentary: audit write raised unexpectedly — serving anyway job=%s",
                job_id,
            )

        # SEBI-disclaimer-postfixed at serialization (architecture §MF line 257;
        # line 220: LLM commentary is labelled "AI-generated insight, not
        # investment advice"). The label rides with the string itself so any
        # consumer of the cached/served commentary carries it, not only the
        # report's general disclosure bundle.
        return f"{output.summary}\n\n{AI_DISCLAIMER}"

    except Exception:  # noqa: BLE001 — commentary is non-blocking
        logger.warning(
            "mf_commentary: unexpected error — omitting commentary job=%s",
            job_id, exc_info=True,
        )
        return None
