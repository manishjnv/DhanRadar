"""
Unit tests for the PR-5 backtest/drift schema surface on /admin/ai/versions.

The DB-backed behaviour (record_engine_changelog + list_engine_versions storing/
returning backtest_passed, and the router deriving backtest/drift) is covered by
the integration test + the alembic-migrations CI job. These pure-schema tests
lock the contract the frontend mirrors.
"""

from __future__ import annotations

from dhanradar.admin.aiops_schemas import (
    AiVersionsResponse,
    BacktestInfo,
    DriftInfo,
    EngineVersionRow,
)


def _row(backtest_passed: bool | None) -> EngineVersionRow:
    return EngineVersionRow(
        model_version="v1.2",
        created_by="a",
        approved_by="b",
        two_person_ok=True,
        activated=True,
        activated_at=None,
        created_at=None,
        backtest_passed=backtest_passed,
    )


def test_engine_version_row_carries_backtest_passed():
    assert _row(True).backtest_passed is True
    assert _row(False).backtest_passed is False
    assert _row(None).backtest_passed is None


def test_engine_version_row_backtest_defaults_none():
    # A row constructed without the field (older payload shape) is not-asserted.
    row = EngineVersionRow(
        model_version="v1",
        created_by=None,
        approved_by=None,
        two_person_ok=False,
        activated=False,
        activated_at=None,
        created_at=None,
    )
    assert row.backtest_passed is None


def test_backtest_info_is_instrumented_by_default():
    bt = BacktestInfo(versions_with_backtest=2)
    assert bt.instrumented is True
    assert bt.versions_with_backtest == 2


def test_drift_info_defaults_not_instrumented():
    d = DriftInfo()
    assert d.instrumented is False
    assert d.decision == "insufficient_data"
    assert d.churn == 0.0
    assert d.requires_human_review is False


def test_drift_info_instrumented_with_real_churn():
    d = DriftInfo(instrumented=True, decision="stable", churn=0.03, requires_human_review=False)
    assert d.instrumented is True
    assert d.churn == 0.03


def test_versions_response_defaults():
    resp = AiVersionsResponse(versions=[_row(True), _row(None)])
    assert resp.backtest.instrumented is True
    assert resp.drift.instrumented is False
    assert len(resp.versions) == 2
