"""
DhanRadar — AI output contract (architecture §S, AIOutputBase).

Every LLM output in DhanRadar extends ``AIOutputBase``. The contract encodes the
non-negotiable explainability + SEBI-boundary rules at the type level:

  - confidence is an internal 0–1 float; the public surface shows the BAND only.
  - at least 2 contributing signals; confidence > 0.7 ⇒ at least 3 (§B3, §S).
  - contributing AND contradicting signals are always carried (disagreement is
    never hidden — §S "Disagreement disclosure").
  - the mandatory disclaimer "AI-generated insight, not investment advice" is
    forced on every instance and cannot be overridden away (non-negotiable #9).

This module is pure schema — no I/O, no model calls. Advisory-language screening
of the free-text lives in ``QualityValidator`` (quality.py).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# The single canonical label that must appear on every AI surface (architecture
# "any LLM-generated commentary is labeled 'AI-generated insight, not investment
# advice'"). Forced by the validator below — never client/model supplied.
AI_DISCLAIMER = "AI-generated insight, not investment advice"

ConfidenceBand = Literal["high", "medium", "low"]


class AIOutputBase(BaseModel):
    """Base contract every AI output schema must extend.

    Subclasses add task-specific fields (e.g. a stock thesis, a mood commentary)
    but inherit the structural + compliance invariants enforced here.
    """

    confidence: float = Field(
        ge=0.0, le=1.0, description="Internal confidence 0–1; public surface shows the band only."
    )
    confidence_band: ConfidenceBand = Field(description="Public-facing confidence band.")
    contributing_signals: list[str] = Field(
        min_length=2, description="Evidence supporting the analysis (>=2; >=3 if confidence>0.7)."
    )
    contradicting_signals: list[str] = Field(
        default_factory=list, description="Evidence against — always carried, never hidden."
    )
    # Forced to AI_DISCLAIMER by the validator; declared so it serializes out.
    disclaimer: str = Field(default=AI_DISCLAIMER)

    @model_validator(mode="after")
    def _enforce_invariants(self) -> "AIOutputBase":
        # High-confidence claims need more evidence (§B3 / §S).
        if self.confidence > 0.7 and len(self.contributing_signals) < 3:
            raise ValueError(
                "confidence > 0.7 requires >= 3 contributing signals "
                f"(got {len(self.contributing_signals)})"
            )
        # The disclaimer is mandatory and non-overridable: a model/caller can
        # never strip or alter the SEBI label.
        object.__setattr__(self, "disclaimer", AI_DISCLAIMER)
        return self

    def model_copy(self, *, update: dict | None = None, deep: bool = False) -> "AIOutputBase":
        """``model_copy`` does NOT re-run validators in Pydantic v2, so a caller
        could otherwise ``model_copy(update={"disclaimer": "..."})`` and strip the
        SEBI label. Force it back on every copy — the disclaimer is non-strippable
        through copies too."""
        obj = super().model_copy(update=update, deep=deep)
        object.__setattr__(obj, "disclaimer", AI_DISCLAIMER)
        return obj
