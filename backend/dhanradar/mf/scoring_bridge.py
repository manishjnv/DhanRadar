"""
DhanRadar — MF ↔ Rating Engine bridge (Phase 5).

The MF module FEEDS signals and CONSUMES the unified score through the engine's
published interface — it never reimplements scoring (architecture: "consume
unified score via event only — never recompute"). This bridge maps MF
`FundSignals` → `FactorInputs`, calls `RatingEngine.score`, and upserts the
result into `mf.user_fund_scores` (server-side; the numeric is tier-gated and
never serialized to a client).

For v1 the per-fund signals are pre-normalized axis values produced by the NAV /
fundamentals pipeline; where a signal is unavailable the engine's missing-data /
confidence-floor logic handles it (often `insufficient_data`), which is the
honest, fail-safe outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dhanradar.scoring.engine import FactorInputs, LabelSignals, RatingEngine, SubFactor
from dhanradar.scoring.engine.schemas import Axis, ScoringResult


@dataclass(frozen=True)
class FundSignals:
    isin: str
    # Pre-normalized axis values 0–100 (None = unavailable → dropped by the engine).
    quality: float | None = None
    valuation: float | None = None
    momentum: float | None = None
    trend: float | None = None
    risk: float | None = None
    # Category-relative label rule inputs (drive the label, NOT the score).
    outperform_1y: bool = False
    outperform_3y: bool = False
    drawdown_controlled: bool = False
    underperform_12m: bool = False
    sustained_underperformance: bool = False
    structural_concern: bool = False
    manager_change: bool = False
    contributing: list[str] = field(default_factory=list)
    contradicting: list[str] = field(default_factory=list)
    # Confidence inputs / structural gates.
    freshness: float = 1.0
    retrieval_relevance: float = 0.6
    model_signal: float = 0.5
    sources_reliable: bool = True
    liquid: bool = True
    stale: bool = False


def to_factor_inputs(s: FundSignals) -> FactorInputs:
    axes = {
        Axis.quality: [SubFactor("quality", s.quality, 1.0)],
        Axis.valuation: [SubFactor("valuation", s.valuation, 1.0)],
        Axis.momentum: [SubFactor("momentum", s.momentum, 1.0)],
        Axis.trend: [SubFactor("trend", s.trend, 1.0)],
        Axis.risk: [SubFactor("risk", s.risk, 1.0)],
    }
    return FactorInputs(
        instrument_type="mf",
        identifier=s.isin,
        axes=axes,
        label_signals=LabelSignals(
            outperform_1y=s.outperform_1y,
            outperform_3y=s.outperform_3y,
            drawdown_controlled=s.drawdown_controlled,
            underperform_12m=s.underperform_12m,
            sustained_underperformance=s.sustained_underperformance,
            structural_concern=s.structural_concern,
            manager_change=s.manager_change,
            contributing=list(s.contributing),
            contradicting=list(s.contradicting),
        ),
        freshness=s.freshness,
        retrieval_relevance=s.retrieval_relevance,
        model_signal=s.model_signal,
        sources_reliable=s.sources_reliable,
        liquid=s.liquid,
        stale=s.stale,
    )


async def score_fund(engine: RatingEngine, signals: FundSignals) -> ScoringResult:
    """Score one fund via the engine's published interface."""
    return await engine.score(to_factor_inputs(signals))


async def upsert_user_fund_score(
    db: Any,
    user_id: str,
    result: ScoringResult,
    portfolio_id: Any,
) -> None:
    """Persist the engine result into mf.user_fund_scores (server-side; the
    unified_score is tier-gated and never serialized to a client)."""
    from sqlalchemy.dialects.postgresql import insert

    from dhanradar.models.mf import UserFundScore

    stmt = insert(UserFundScore).values(
        user_id=user_id,
        portfolio_id=portfolio_id,
        isin=result.identifier,
        unified_score=result.unified_score,
        confidence_band=result.confidence_band.value,
        verb_label=result.verb_label.value,
        # G10: persist the engine's own diagnostic flags verbatim (qualitative tags,
        # no numeric) so the transparency surface renders honest data-quality "why".
        flags=list(result.flags or []),
        model_version=result.model_version,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_user_fund_score",
        set_={
            "unified_score": stmt.excluded.unified_score,
            "confidence_band": stmt.excluded.confidence_band,
            "verb_label": stmt.excluded.verb_label,
            "flags": stmt.excluded.flags,
            "model_version": stmt.excluded.model_version,
            "scored_at": __import__("sqlalchemy").func.now(),
        },
    )
    await db.execute(stmt)
    await db.commit()
