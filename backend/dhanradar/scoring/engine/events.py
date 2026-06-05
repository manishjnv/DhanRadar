"""
DhanRadar — scoring engine event contracts (architecture §S interface).

Domain modules couple to the engine ONLY through these events + the internal
read endpoint — never by importing the engine's internals. The published event
carries the PUBLIC projection (label + confidence band, NO numeric).
"""

from __future__ import annotations

from dataclasses import dataclass

from dhanradar.scoring.engine.schemas import PublicScore

SCORE_REQUESTED = "scoring.score.requested"
SCORING_RESULT_PUBLISHED = "scoring.result.published"


@dataclass(frozen=True)
class ScoreRequested:
    instrument_type: str
    identifier: str
    name: str = SCORE_REQUESTED


@dataclass(frozen=True)
class ScoringResultPublished:
    instrument_type: str
    identifier: str
    public: PublicScore  # no numeric — safe for any consumer / surface
    name: str = SCORING_RESULT_PUBLISHED
