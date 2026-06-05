"""
DhanRadar — Rating/Scoring Engine contracts (architecture §S, FINAL_SCORING_SPEC).

Compliance invariants encoded structurally at the type level:

  * The engine consumes INSTRUMENT factors only. There is deliberately NO user
    field and NO ``risk_profile`` anywhere in ``FactorInputs`` — the user risk
    profile is excluded from all scoring inputs (non-neg #3 / spec §6.2 HARD
    RULE). A test asserts this field is absent.
  * The label is carried separately from the score and is derived from
    ``LabelSignals`` (category-relative facts), never from the numeric score
    (non-neg #1 / spec §4).
  * ``ScoringResult`` holds the numeric ``unified_score`` and raw ``confidence``
    for SERVER-SIDE/tier-gated use only; ``to_public()`` returns a ``PublicScore``
    that carries the label + confidence BAND + signals + disclosure and NO
    numeric (non-neg #2 "no numeric in DOM").
  * Every result carries the disclosure bundle + NOT_ADVICE (non-neg #9).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional

MODEL_VERSION = "v1"

# Disclosure bundle attached to every result (architecture §9 / non-neg #9).
NOT_ADVICE = "NOT_ADVICE"
DISCLAIMER_VERSION = "2026-06-06.v1"
DISCLOSURE_BUNDLE = (
    "Educational analysis only — not investment advice. Labels describe "
    "category-relative form, not a recommendation to buy, sell, hold, or switch."
)


class Axis(str, enum.Enum):
    quality = "quality"
    valuation = "valuation"
    momentum = "momentum"
    trend = "trend"
    risk = "risk"


class VerbLabel(str, enum.Enum):
    in_form = "in_form"
    on_track = "on_track"
    off_track = "off_track"
    out_of_form = "out_of_form"
    insufficient_data = "insufficient_data"


class ConfidenceBand(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"
    insufficient_data = "insufficient_data"


@dataclass(frozen=True)
class SubFactor:
    """One normalized (0–100) sub-factor within an axis. ``value=None`` = missing
    (dropped + remaining weights renormalized, spec §3.2 — never imputed)."""

    name: str
    value: Optional[float]  # normalized 0–100, or None if missing
    weight: float  # within-axis weight (relative; renormalized over present ones)


@dataclass(frozen=True)
class LabelSignals:
    """Category-relative facts that drive the verb-label RULE TABLE (spec §4.1).

    These are explicit booleans (not the numeric score) so the label can never be
    a pure function of the score. Descriptive ``contributing``/``contradicting``
    lists are always surfaced (disagreement disclosure, spec §7)."""

    outperform_1y: bool = False
    outperform_3y: bool = False
    drawdown_controlled: bool = False
    underperform_12m: bool = False
    sustained_underperformance: bool = False
    structural_concern: bool = False
    manager_change: bool = False
    contributing: list[str] = field(default_factory=list)
    contradicting: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FactorInputs:
    """Everything the engine needs for ONE instrument. No user/risk_profile."""

    instrument_type: str
    identifier: str
    axes: dict[Axis, list[SubFactor]]
    label_signals: LabelSignals
    # Confidence inputs (0–1 each), spec §5.
    freshness: float = 1.0
    retrieval_relevance: float = 1.0
    model_signal: float = 0.5
    # Provenance / structural gates.
    sources_reliable: bool = True
    liquid: bool = True
    stale: bool = False


@dataclass(frozen=True)
class PublicScore:
    """The ONLY shape that may reach a public surface — band + label, NO numeric
    (non-neg #2). The numeric score and factor weights never appear here."""

    instrument_type: str
    identifier: str
    verb_label: VerbLabel
    confidence_band: ConfidenceBand
    contributing_signals: list[str]
    contradicting_signals: list[str]
    eval_seq: int
    valid_until: str
    model_version: str
    disclosure: str
    not_advice: str


@dataclass(frozen=True)
class ScoringResult:
    """Full internal result. Numeric ``unified_score``/``confidence`` are
    SERVER-SIDE only (tier-gated); use ``to_public()`` for any client surface."""

    instrument_type: str
    identifier: str
    verb_label: VerbLabel
    confidence_band: ConfidenceBand
    unified_score: Optional[int]  # 0–100, internal/tier-gated; None when refused
    confidence: Optional[float]  # 0–1, internal; None when refused
    eval_seq: int
    valid_until: str
    model_version: str = MODEL_VERSION
    contributing_signals: list[str] = field(default_factory=list)
    contradicting_signals: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)  # partial_coverage / stale / low_liquidity / ...
    band_disagreement: bool = False  # rule label vs score-band leaning disagreed (rule wins)
    disclosure: str = DISCLOSURE_BUNDLE
    not_advice: str = NOT_ADVICE

    def to_public(self) -> PublicScore:
        """Project to the client-safe shape — strips every numeric (score,
        confidence float, weights). This is the no-numeric-in-DOM boundary."""
        return PublicScore(
            instrument_type=self.instrument_type,
            identifier=self.identifier,
            verb_label=self.verb_label,
            confidence_band=self.confidence_band,
            contributing_signals=list(self.contributing_signals),
            contradicting_signals=list(self.contradicting_signals),
            eval_seq=self.eval_seq,
            valid_until=self.valid_until,
            model_version=self.model_version,
            disclosure=self.disclosure,
            not_advice=self.not_advice,
        )
