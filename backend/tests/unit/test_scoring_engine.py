"""
Unit tests for the Rating/Scoring Engine v1 (Phase 4, architecture §S).

Covers the plan's verification matrix + the compliance non-negotiables:
  - golden-set inputs → expected score + label
  - label is NOT a pure function of the score (same score, different label)
  - confidence floor (<0.30) → insufficient_data, NO numeric exposed (refuse)
  - 2-eval hysteresis: a flip is suppressed until 2 consecutive evals
  - >5% batch churn → held for Compliance; distribution bound → held
  - risk_profile is excluded from engine inputs (non-neg #3)
  - public projection carries NO numeric (non-neg #2)
  - two-person methodology gate; config weight-sum + double-count validators

Pure unit tests — no Redis/DB (fakes injected).
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from dhanradar.scoring.engine import (
    Axis,
    ConfidenceBand,
    FactorInputs,
    LabelSignals,
    RatingEngine,
    SubFactor,
    VerbLabel,
    make_changelog_entry,
    review_batch,
)
from dhanradar.scoring.engine.config import ConfigError, EngineConfig, load_config
from dhanradar.scoring.engine.governance import BatchDecision, two_person_gate_ok
from dhanradar.scoring.engine.schemas import PublicScore, ScoringResult


# --- fakes -------------------------------------------------------------------
class _FakeHystStore:
    def __init__(self) -> None:
        self.d: dict = {}

    async def get(self, key):
        return self.d.get(key)

    async def set(self, key, state):
        self.d[key] = state


class _FakeResultStore:
    def __init__(self) -> None:
        self.d: dict = {}

    async def set(self, key, value, ex=None):
        self.d[key] = value


_IN_FORM = LabelSignals(
    outperform_1y=True, outperform_3y=True, drawdown_controlled=True,
    contributing=["1Y beat", "3Y beat", "low drawdown"],
)
_OUT_OF_FORM = LabelSignals(
    sustained_underperformance=True, structural_concern=True,
    contributing=["3Y lag", "mandate drift", "AUM exodus"], contradicting=["1M bounce"],
)


def _inputs(score=60.0, *, signals=_IN_FORM, identifier="HDFC500", axes=None, **kw):
    if axes is None:
        axes = {a: [SubFactor(a.value, score, 1.0)] for a in Axis}
    return FactorInputs(
        instrument_type="mf",
        identifier=identifier,
        axes=axes,
        label_signals=signals,
        freshness=kw.get("freshness", 1.0),
        retrieval_relevance=kw.get("retrieval_relevance", 1.0),
        model_signal=kw.get("model_signal", 0.6),
        sources_reliable=kw.get("sources_reliable", True),
        liquid=kw.get("liquid", True),
        stale=kw.get("stale", False),
    )


def _engine(**kw):
    return RatingEngine(
        hysteresis_store=kw.get("hyst", _FakeHystStore()),
        result_store=kw.get("result_store", _FakeResultStore()),  # avoid real Redis
        event_sink=kw.get("event_sink"),
        now=lambda: __import__("datetime").datetime(2026, 6, 6, tzinfo=__import__("datetime").timezone.utc),
    )


# --- golden set --------------------------------------------------------------
async def test_golden_set_score_and_label():
    res = await _engine().score(_inputs(score=60.0, signals=_IN_FORM))
    assert res.unified_score == 60
    assert res.verb_label == VerbLabel.in_form
    assert res.confidence_band in (ConfidenceBand.high, ConfidenceBand.medium)
    assert res.disclosure and res.not_advice == "NOT_ADVICE"


# --- label is NOT a pure function of the score -------------------------------
async def test_label_not_a_function_of_score():
    a = await _engine().score(_inputs(score=60.0, signals=_IN_FORM, identifier="A"))
    b = await _engine().score(_inputs(score=60.0, signals=_OUT_OF_FORM, identifier="B"))
    assert a.unified_score == b.unified_score == 60  # SAME score
    assert a.verb_label == VerbLabel.in_form
    assert b.verb_label == VerbLabel.out_of_form  # DIFFERENT label


# --- confidence floor → refuse, no numeric -----------------------------------
async def test_confidence_floor_refuses_with_no_numeric():
    inp = _inputs(
        axes={Axis.quality: [SubFactor("q", 60.0, 1.0)]},  # only 1 of 5 axes
        freshness=0.0, retrieval_relevance=0.0, model_signal=0.0,
    )
    res = await _engine().score(inp)
    assert res.verb_label == VerbLabel.insufficient_data
    assert res.confidence_band == ConfidenceBand.insufficient_data
    assert res.unified_score is None and res.confidence is None  # NO numeric exposed
    assert "insufficient_data" in res.flags


# --- 2-eval hysteresis -------------------------------------------------------
async def test_hysteresis_suppresses_flip_until_two_consecutive():
    eng = _engine(hyst=_FakeHystStore())
    r1 = await eng.score(_inputs(signals=_IN_FORM, identifier="X"))
    assert r1.verb_label == VerbLabel.in_form and r1.eval_seq == 1
    r2 = await eng.score(_inputs(signals=_OUT_OF_FORM, identifier="X"))
    assert r2.verb_label == VerbLabel.in_form  # flip SUPPRESSED (held)
    assert r2.eval_seq == 2
    r3 = await eng.score(_inputs(signals=_OUT_OF_FORM, identifier="X"))
    assert r3.verb_label == VerbLabel.out_of_form  # flip confirmed
    assert r3.eval_seq == 3


# --- partial coverage caps confidence at medium ------------------------------
async def test_partial_coverage_caps_band_medium():
    axes = {a: [SubFactor(a.value, 60.0, 1.0)] for a in Axis if a != Axis.risk}  # drop risk
    res = await _engine().score(_inputs(axes=axes))
    assert "partial_coverage" in res.flags
    assert res.confidence_band == ConfidenceBand.medium


# --- governance: churn + distribution ----------------------------------------
def test_churn_gate_holds_above_five_percent():
    prev = {f"f{i}": "on_track" for i in range(20)}
    cur = dict(prev)
    cur["f0"] = "off_track"
    cur["f1"] = "off_track"  # 2/20 = 10% changed
    review = review_batch(prev, cur, max_label_share=1.0)
    assert review.decision == BatchDecision.hold and review.churn == pytest.approx(0.10)


def test_churn_gate_publishes_within_bounds():
    prev = {f"f{i}": ("in_form" if i % 2 else "on_track") for i in range(20)}
    cur = dict(prev)
    cur["f0"] = "off_track"  # 1/20 = 5% (not > 5%)
    review = review_batch(prev, cur, max_label_share=1.0)
    assert review.decision == BatchDecision.publish


def test_distribution_collapse_is_held():
    cur = {f"f{i}": "out_of_form" for i in range(20)}  # 100% one label
    review = review_batch({}, cur)
    assert review.decision == BatchDecision.hold and review.distribution_violations


# --- compliance invariants ---------------------------------------------------
def test_factor_inputs_exclude_risk_profile_and_user():
    names = {f.name for f in fields(FactorInputs)}
    assert "risk_profile" not in names
    assert "user_id" not in names and "user" not in names


def test_public_projection_has_no_numeric():
    pub_fields = {f.name for f in fields(PublicScore)}
    assert "unified_score" not in pub_fields
    assert "confidence" not in pub_fields  # only confidence_band is public
    assert "confidence_band" in pub_fields


async def test_to_public_strips_numeric():
    res = await _engine().score(_inputs())
    pub = res.to_public()
    assert isinstance(pub, PublicScore)
    assert not hasattr(pub, "unified_score")


# --- two-person methodology gate ---------------------------------------------
def test_two_person_gate():
    assert two_person_gate_ok("alice", "bob") is True
    assert two_person_gate_ok("alice", "alice") is False
    assert two_person_gate_ok("alice", None) is False


def test_changelog_enforces_two_person_when_activating():
    from dhanradar.scoring.engine.governance import TwoPersonGateError

    with pytest.raises(TwoPersonGateError):
        make_changelog_entry(
            model_version="v1", created_by="x", approved_by="x",
            factors_before={}, factors_after={}, methodology_url="u",
            enforce_two_person=True,
        )
    entry = make_changelog_entry(
        model_version="v1", created_by="x", approved_by="y",
        factors_before={}, factors_after={}, methodology_url="u",
        enforce_two_person=True,
    )
    assert entry["two_person_ok"] is True


# --- config validators -------------------------------------------------------
def test_config_rejects_bad_weight_sum():
    cfg = EngineConfig(
        model_version="v1", activated=False,
        axis_weights={Axis.quality: 0.5, Axis.valuation: 0.4},  # sum 0.9
        weight_sum_tolerance=0.001,
        axis_subfactors={Axis.quality: ["a"], Axis.valuation: ["b"]},
        confidence_weights={"freshness": 1.0},
        low_coverage_threshold_pct=40, confidence_floor=0.30,
    )
    with pytest.raises(ConfigError):
        cfg.validate()


def test_config_rejects_duplicate_subfactor():
    cfg = EngineConfig(
        model_version="v1", activated=False,
        axis_weights={Axis.quality: 0.5, Axis.valuation: 0.5},
        weight_sum_tolerance=0.001,
        axis_subfactors={Axis.quality: ["dup"], Axis.valuation: ["dup"]},  # duplicate
        confidence_weights={"freshness": 1.0},
        low_coverage_threshold_pct=40, confidence_floor=0.30,
    )
    with pytest.raises(ConfigError):
        cfg.validate()


def test_canonical_config_is_valid():
    load_config()  # raises ConfigError if the shipped ranking_configs_v1.json is bad


# --- publish: event carries public projection; cache carries full result -----
async def test_provisional_model_flag_when_not_activated():
    # ranking_configs_v1 is activated:false → every result is tagged provisional.
    res = await _engine().score(_inputs())
    assert "provisional_model" in res.flags


async def test_prior_label_surfaced_on_refusal():
    eng = _engine(hyst=_FakeHystStore())
    r1 = await eng.score(_inputs(signals=_IN_FORM, identifier="P"))
    assert r1.verb_label == VerbLabel.in_form and r1.prior_label is None
    # Data drops out → refuse, but prior_label tells the consumer what it WAS.
    r2 = await eng.score(
        _inputs(axes={Axis.quality: [SubFactor("q", 60.0, 1.0)]}, identifier="P",
                freshness=0.0, retrieval_relevance=0.0, model_signal=0.0)
    )
    assert r2.verb_label == VerbLabel.insufficient_data
    assert r2.prior_label == VerbLabel.in_form


async def test_disclaimer_version_carried_public_and_internal():
    res = await _engine().score(_inputs())
    assert res.disclaimer_version
    assert res.to_public().disclaimer_version == res.disclaimer_version


def test_internal_token_guard(monkeypatch):
    from fastapi import HTTPException

    from dhanradar.config import settings
    from dhanradar.scoring.engine.router import _require_internal_token

    # Unset token → endpoint DISABLED (fail-closed 503).
    monkeypatch.setattr(settings, "INTERNAL_API_TOKEN", "")
    with pytest.raises(HTTPException) as ei:
        _require_internal_token("anything")
    assert ei.value.status_code == 503

    # Token set → wrong/missing header → 403; correct header → passes.
    monkeypatch.setattr(settings, "INTERNAL_API_TOKEN", "s3cret")
    with pytest.raises(HTTPException) as ei2:
        _require_internal_token(None)
    assert ei2.value.status_code == 403
    with pytest.raises(HTTPException):
        _require_internal_token("wrong")
    assert _require_internal_token("s3cret") is None  # OK


async def test_publish_emits_public_and_caches_full():
    sink_calls = []

    async def sink(evt):
        sink_calls.append(evt)

    rs = _FakeResultStore()
    eng = _engine(event_sink=sink, result_store=rs)
    res = await eng.score(_inputs(identifier="PUBM"))
    assert len(sink_calls) == 1
    assert isinstance(sink_calls[0].public, PublicScore)  # no numeric to consumers
    # internal cache retains the numeric for the tier-gated read endpoint
    import json

    cached = json.loads(rs.d["scoring:result:mf:PUBM"])
    assert cached["unified_score"] == res.unified_score
