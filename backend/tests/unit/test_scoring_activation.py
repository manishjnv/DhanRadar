"""
Unit tests for the B6/B28 scoring-engine activation gate (no DB).

Covers assert_activatable (pure gate), the config field extension, and the
module-level error taxonomy.
"""

from __future__ import annotations

import pytest

from dhanradar.scoring.engine.activation import (
    BacktestNotPassedError,
    assert_activatable,
)
from dhanradar.scoring.engine.governance import TwoPersonGateError


# ---------------------------------------------------------------------------
# assert_activatable — pure gate, no DB
# ---------------------------------------------------------------------------


def test_assert_activatable_rejects_failed_backtest():
    """backtest_passed=False must raise BacktestNotPassedError even with
    distinct principals (backtest is checked first)."""
    with pytest.raises(BacktestNotPassedError):
        assert_activatable(
            created_by="author-a",
            approved_by="approver-b",
            backtest_passed=False,
        )


def test_assert_activatable_rejects_same_principal():
    """Same created_by and approved_by → TwoPersonGateError (backtest True)."""
    with pytest.raises(TwoPersonGateError):
        assert_activatable(
            created_by="same-person",
            approved_by="same-person",
            backtest_passed=True,
        )


def test_assert_activatable_rejects_empty_approver():
    """Empty approved_by string → TwoPersonGateError (gate requires a real
    principal to be set)."""
    with pytest.raises(TwoPersonGateError):
        assert_activatable(
            created_by="author-a",
            approved_by="",
            backtest_passed=True,
        )


def test_assert_activatable_passes_distinct_principals():
    """Distinct created_by / approved_by + backtest True → no exception."""
    assert_activatable(
        created_by="architecture-review",
        approved_by="compliance-officer",
        backtest_passed=True,
    )


# ---------------------------------------------------------------------------
# EngineConfig — created_by and methodology_url populated from JSON
# ---------------------------------------------------------------------------


def test_config_exposes_created_by_and_methodology_url():
    """get_config() must expose created_by and methodology_url from
    ranking_configs_v1.json — both must be non-empty strings."""
    from dhanradar.scoring.engine.config import get_config

    cfg = get_config()
    assert cfg.created_by, "created_by must be non-empty (set in ranking_configs_v1.json)"
    assert cfg.methodology_url, "methodology_url must be non-empty (set in ranking_configs_v1.json)"


def test_config_rejects_uuid_shaped_created_by():
    """A UUID-shaped created_by must fail config validation — it would let the
    two-person gate be trivially/deceptively satisfied (B6 integrity)."""
    import dataclasses

    from dhanradar.scoring.engine.config import ConfigError, get_config

    cfg = get_config()
    bad = dataclasses.replace(cfg, created_by="11111111-1111-1111-1111-111111111111")
    with pytest.raises(ConfigError, match="role/team identifier"):
        bad.validate()


def test_config_accepts_role_created_by():
    """A role/team identifier (non-UUID) for created_by passes validation."""
    import dataclasses

    from dhanradar.scoring.engine.config import get_config

    cfg = get_config()
    dataclasses.replace(cfg, created_by="architecture-review").validate()  # no raise
