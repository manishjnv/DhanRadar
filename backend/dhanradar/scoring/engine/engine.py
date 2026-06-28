"""
DhanRadar — RatingEngine: the collapse function (architecture §S, spec §3–§7).

`score(FactorInputs) -> ScoringResult` orchestrates the deterministic pipeline:

  axes → (drop-and-renormalize) axis scores → composite (reweight present axes)
       → confidence (formula + structural caps) → band
       → if band == insufficient_data (confidence < 0.30): REFUSE (no label, no
         numeric exposed)
       → else: verb label from the RULE TABLE (not the score) → 2-eval hysteresis
       → ScoringResult (+ public projection published via the event sink).

Compliance properties (test-enforced):
  * No user / risk_profile is an input (non-neg #3).
  * The label is derived from LabelSignals, never the numeric score (non-neg #1).
  * The published event + cached read carry the PUBLIC projection (band+label,
    no numeric) for any consumer; the numeric score stays server-side (non-neg #2).
  * Every result carries the disclosure bundle + NOT_ADVICE (non-neg #9).
"""

from __future__ import annotations

import datetime
import json
from collections.abc import Awaitable, Callable
from typing import Any

from dhanradar.scoring.engine.confidence import (
    apply_structural_caps,
    band_for,
    compute_confidence,
    factor_agreement,
)
from dhanradar.scoring.engine.config import EngineConfig, get_config
from dhanradar.scoring.engine.events import ScoringResultPublished
from dhanradar.scoring.engine.hysteresis import (
    HysteresisStore,
    RedisHysteresisStore,
    apply_hysteresis,
)
from dhanradar.scoring.engine.labels import derive_label, disagrees_materially
from dhanradar.scoring.engine.normalize import aggregate_axis, composite
from dhanradar.scoring.engine.schemas import (
    Axis,
    ConfidenceBand,
    FactorInputs,
    ScoringResult,
    VerbLabel,
)

_DEFAULT_VALID_FOR = 7200  # 2h cache horizon (MF cadence)


def _to_strength(value: float) -> str:
    """Map a 0–1 confidence-factor float → qualitative band string.

    Thresholds are independent of the confidence band thresholds (0.30/0.50/0.70)
    — these measure per-factor DATA QUALITY, not the composite confidence level.
    Edge cases: 0.0→low, 0.4→medium, 0.7→high, 1.0→high (correct in all cases).
    """
    if value >= 0.7:
        return "high"
    if value >= 0.4:
        return "medium"
    return "low"


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class RatingEngine:
    def __init__(
        self,
        *,
        config: EngineConfig | None = None,
        hysteresis_store: HysteresisStore | None = None,
        event_sink: Callable[[ScoringResultPublished], Awaitable[None]] | None = None,
        result_store: Any = None,
        valid_for_seconds: int = _DEFAULT_VALID_FOR,
        now: Callable[[], datetime.datetime] | None = None,
    ) -> None:
        self._config = config or get_config()
        self._store = hysteresis_store or RedisHysteresisStore()
        self._event_sink = event_sink
        self._result_store = result_store  # Redis-like for the internal read API
        self._valid_for = valid_for_seconds
        self._now = now or _utcnow

    @property
    def model_version(self) -> str:
        """Public accessor for the active config's model_version (so consumers
        never reach into engine internals)."""
        return self._config.model_version

    async def score(self, inputs: FactorInputs) -> ScoringResult:
        cfg = self._config

        # 1. Per-axis aggregation (drop-and-renormalize missing sub-factors).
        axis_scores: dict[Axis, float | None] = {}
        axis_coverage: dict[Axis, float] = {}
        for axis in Axis:
            score, cov = aggregate_axis(inputs.axes.get(axis, []))
            axis_scores[axis] = score
            axis_coverage[axis] = cov

        # 2. Composite over present axes (reweighted), partial_coverage flag.
        unified, partial, _present = composite(axis_scores, cfg.axis_weights)

        # 3. Confidence.
        coverage = self._overall_coverage(axis_coverage, cfg)
        agreement = factor_agreement(axis_scores)
        conf = compute_confidence(
            freshness=inputs.freshness,
            coverage=coverage,
            agreement=agreement,
            retrieval_relevance=inputs.retrieval_relevance,
            model_signal=inputs.model_signal,
            weights=cfg.confidence_weights,
        )
        # Named factor bands — captured BEFORE structural caps (caps lower the aggregate
        # but do not change the per-factor quality; show the raw input quality to the user).
        # Mapping to display names (Feature 4):
        #   consistency   ← factor_agreement (do axes agree with each other?)
        #   recency       ← freshness (how recent is the NAV data?)
        #   volatility    ← retrieval_relevance (quality of the vol/risk signal retrieval)
        #   data_coverage ← overall_axis_coverage (how many axes have usable data?)
        _confidence_factors: dict[str, str] = {
            "consistency": _to_strength(agreement),
            "recency": _to_strength(inputs.freshness),
            "volatility": _to_strength(inputs.retrieval_relevance),
            "data_coverage": _to_strength(coverage),
        }
        conf = apply_structural_caps(
            conf,
            partial_coverage=partial,
            liquid=inputs.liquid,
            stale=inputs.stale,
            contributing_count=len(inputs.label_signals.contributing),
            sources_reliable=inputs.sources_reliable,
        )
        band = band_for(conf)

        valid_until = (self._now() + datetime.timedelta(seconds=self._valid_for)).isoformat()
        flags: list[str] = []
        # The numeric is computed with PROPOSED v1 weights that have not cleared
        # the backtest/calibration/two-person activation gates (B6) — tag every
        # result so no downstream consumer mistakes a draft numeric for authoritative.
        if not cfg.activated:
            flags.append("provisional_model")
        if partial:
            flags.append("partial_coverage")
        if inputs.stale:
            flags.append("stale")
        if not inputs.liquid:
            flags.append("low_liquidity")

        contributing = list(inputs.label_signals.contributing)
        contradicting = list(inputs.label_signals.contradicting)

        # 4. Confidence floor → REFUSE (no label, no numeric exposed).
        if band == ConfidenceBand.insufficient_data or unified is None:
            outcome = await apply_hysteresis(
                self._store, inputs.instrument_type, inputs.identifier, VerbLabel.insufficient_data
            )
            result = ScoringResult(
                instrument_type=inputs.instrument_type,
                identifier=inputs.identifier,
                verb_label=VerbLabel.insufficient_data,
                confidence_band=ConfidenceBand.insufficient_data,
                unified_score=None,
                confidence=None,
                eval_seq=outcome.eval_seq,
                valid_until=valid_until,
                model_version=cfg.model_version,
                contributing_signals=contributing,
                contradicting_signals=contradicting,
                flags=flags + ["insufficient_data"],
                confidence_factors={},  # omit factors when confidence is refused
                prior_label=outcome.prior_label,
            )
            await self._publish(result)
            return result

        # 5. Label from the RULE TABLE (independent of the numeric score).
        rule_label = derive_label(inputs.label_signals)
        disagreement = disagrees_materially(rule_label, unified)

        # 6. 2-eval hysteresis → published label + eval_seq.
        outcome = await apply_hysteresis(
            self._store, inputs.instrument_type, inputs.identifier, rule_label
        )

        result = ScoringResult(
            instrument_type=inputs.instrument_type,
            identifier=inputs.identifier,
            verb_label=outcome.published_label,
            confidence_band=band,
            unified_score=unified,
            confidence=round(conf, 4),
            eval_seq=outcome.eval_seq,
            valid_until=valid_until,
            model_version=cfg.model_version,
            contributing_signals=contributing,
            contradicting_signals=contradicting,
            flags=flags,
            confidence_factors=_confidence_factors,
            band_disagreement=disagreement,
            prior_label=outcome.prior_label,
        )
        await self._publish(result)
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _overall_coverage(self, axis_coverage: dict[Axis, float], cfg: EngineConfig) -> float:
        total_w = sum(cfg.axis_weights.values())
        if total_w <= 0:
            return 0.0
        return sum(cfg.axis_weights[a] * axis_coverage.get(a, 0.0) for a in cfg.axis_weights) / total_w

    async def _publish(self, result: ScoringResult) -> None:
        public = result.to_public()
        # Cache the FULL (internal) result for the tier-gated read endpoint.
        store = self._result_store
        if store is None:
            try:
                from dhanradar.redis_client import get_redis

                store = get_redis()
            except Exception:  # pragma: no cover - redis optional in some contexts
                store = None
        if store is not None:
            key = f"scoring:result:{result.instrument_type}:{result.identifier}"
            await store.set(key, json.dumps(_result_to_dict(result)), ex=self._valid_for)
        if self._event_sink is not None:
            await self._event_sink(
                ScoringResultPublished(result.instrument_type, result.identifier, public)
            )


def _result_to_dict(r: ScoringResult) -> dict:
    return {
        "instrument_type": r.instrument_type,
        "identifier": r.identifier,
        "verb_label": r.verb_label.value,
        "confidence_band": r.confidence_band.value,
        "unified_score": r.unified_score,
        "confidence": r.confidence,
        "eval_seq": r.eval_seq,
        "valid_until": r.valid_until,
        "model_version": r.model_version,
        "contributing_signals": r.contributing_signals,
        "contradicting_signals": r.contradicting_signals,
        "flags": r.flags,
        "confidence_factors": dict(r.confidence_factors),
        "band_disagreement": r.band_disagreement,
        "prior_label": r.prior_label.value if r.prior_label else None,
        "disclaimer_version": r.disclaimer_version,
        "disclosure": r.disclosure,
        "not_advice": r.not_advice,
    }
