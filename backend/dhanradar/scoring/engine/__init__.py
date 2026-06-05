"""
DhanRadar — Rating / Scoring Engine v1 (architecture §S, FINAL_SCORING_SPEC).

The IP core. A standalone, deterministic service with STRICT interface coupling:
domain modules couple only via the events (`scoring.result.published`) and the
internal read endpoint — never by importing engine internals.

Public surface:
  - RatingEngine.score(FactorInputs) -> ScoringResult
  - FactorInputs / LabelSignals / SubFactor / Axis  (inputs; no user/risk_profile)
  - ScoringResult / PublicScore  (PublicScore = band+label, no numeric)
  - VerbLabel / ConfidenceBand
  - events: ScoreRequested / ScoringResultPublished
  - governance: review_batch / make_changelog_entry / two_person_gate_ok
"""

from __future__ import annotations

from dhanradar.scoring.engine.engine import RatingEngine
from dhanradar.scoring.engine.events import ScoreRequested, ScoringResultPublished
from dhanradar.scoring.engine.governance import (
    BatchDecision,
    BatchReview,
    make_changelog_entry,
    review_batch,
    two_person_gate_ok,
)
from dhanradar.scoring.engine.schemas import (
    Axis,
    ConfidenceBand,
    FactorInputs,
    LabelSignals,
    PublicScore,
    ScoringResult,
    SubFactor,
    VerbLabel,
)

__all__ = [
    "RatingEngine",
    "FactorInputs",
    "LabelSignals",
    "SubFactor",
    "Axis",
    "ScoringResult",
    "PublicScore",
    "VerbLabel",
    "ConfidenceBand",
    "ScoreRequested",
    "ScoringResultPublished",
    "BatchDecision",
    "BatchReview",
    "review_batch",
    "make_changelog_entry",
    "two_person_gate_ok",
]
