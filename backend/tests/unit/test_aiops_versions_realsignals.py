"""
Unit tests for PR-5 real backtest/drift signals on /admin/ai/versions (built on
#336's JSONB columns).

- BacktestStatus is instrumented (the §8 gate is tracked) + counts versions.
- DriftStatus carries the real churn fields.
- activate_model_version defaults the backtest JSONB to {"passed": backtest_passed}
  (the real §8 outcome) when the caller doesn't supply one.
"""

from __future__ import annotations

from dhanradar.admin.aiops_schemas import (
    AiVersionsResponse,
    BacktestStatus,
    DriftStatus,
    EngineVersionRow,
)


def _row(backtest: dict | None) -> EngineVersionRow:
    return EngineVersionRow(
        model_version="v1.2",
        created_by="a",
        approved_by="b",
        two_person_ok=True,
        activated=True,
        activated_at=None,
        created_at=None,
        backtest=backtest,
        drift=None,
    )


def test_backtest_status_instrumented_by_default():
    bt = BacktestStatus(versions_with_backtest=2)
    assert bt.instrumented is True
    assert bt.versions_with_backtest == 2


def test_drift_status_defaults_not_instrumented():
    d = DriftStatus()
    assert d.instrumented is False
    assert d.decision == "insufficient_data"
    assert d.churn == 0.0
    assert d.requires_human_review is False


def test_drift_status_with_real_churn():
    d = DriftStatus(instrumented=True, decision="publish", churn=0.02, requires_human_review=False)
    assert d.instrumented is True
    assert d.churn == 0.02


def test_engine_version_row_carries_backtest_dict():
    assert _row({"passed": True}).backtest == {"passed": True}
    assert _row(None).backtest is None


def test_versions_response_defaults():
    resp = AiVersionsResponse(versions=[_row({"passed": True}), _row(None)])
    assert resp.backtest.instrumented is True
    assert resp.drift.instrumented is False
    assert len(resp.versions) == 2


async def test_activation_defaults_backtest_to_passed(monkeypatch):
    # activate_model_version must record {"passed": True} into the backtest JSONB
    # when the caller passes no explicit backtest dict.
    import dhanradar.compliance.service as service
    import dhanradar.scoring.engine.activation as activation

    captured: dict = {}

    async def _fake_record(db, **kwargs):
        captured.update(kwargs)
        return {"model_version": kwargs["model_version"], **kwargs}

    async def _not_activated(db, mv):
        return False

    # activate_model_version does `from dhanradar.compliance import service` inside
    # the function, so patch the module-level functions it resolves at call time.
    monkeypatch.setattr(service, "record_engine_changelog", _fake_record)
    monkeypatch.setattr(service, "is_engine_version_activated", _not_activated)

    await activation.activate_model_version(
        db=object(),
        model_version="v2",
        created_by="creator",
        approved_by="approver",
        factors_before={},
        factors_after={},
        methodology_url="http://x",
        backtest_passed=True,
    )
    assert captured["backtest"] == {"passed": True}
