"""
Unit tests for the two-person methodology gate (governance.two_person_gate_ok)
and the activation-layer assert_activatable helper.

Pure unit tests — no DB, no Redis, no HTTP.
"""

from __future__ import annotations

import pytest

from dhanradar.scoring.engine.governance import TwoPersonGateError, two_person_gate_ok

# ---------------------------------------------------------------------------
# two_person_gate_ok — pure boolean gate
# ---------------------------------------------------------------------------


def test_same_principal_returns_false():
    """approved_by == created_by must return False (self-approval not allowed)."""
    assert two_person_gate_ok("alice", "alice") is False


def test_distinct_principals_returns_true():
    """approved_by != created_by with both truthy must return True."""
    assert two_person_gate_ok("alice", "bob") is True


def test_none_approved_by_returns_false():
    """approved_by=None → False (gate requires a real approver)."""
    assert two_person_gate_ok("alice", None) is False


def test_empty_string_approved_by_returns_false():
    """approved_by='' → False (empty string is falsy — not a real approver)."""
    assert two_person_gate_ok("alice", "") is False


def test_none_created_by_with_truthy_approver_returns_true():
    """created_by=None with a real approved_by value satisfies the gate
    (gate only blocks self-approval and missing approver)."""
    # None != "bob" and bool("bob") is True
    assert two_person_gate_ok(None, "bob") is True


def test_both_none_returns_false():
    """Both None → False (approved_by is falsy)."""
    assert two_person_gate_ok(None, None) is False


# ---------------------------------------------------------------------------
# assert_activatable — raises TwoPersonGateError on self-approval
# ---------------------------------------------------------------------------


def test_assert_activatable_raises_when_same_principal():
    """assert_activatable must raise TwoPersonGateError when created_by == approved_by,
    even with backtest_passed=True."""
    from dhanradar.scoring.engine.activation import assert_activatable

    with pytest.raises(TwoPersonGateError):
        assert_activatable(
            created_by="operator-x",
            approved_by="operator-x",
            backtest_passed=True,
        )


def test_assert_activatable_passes_for_distinct_principals():
    """Distinct principals + backtest_passed=True must not raise."""
    from dhanradar.scoring.engine.activation import assert_activatable

    # Must not raise
    assert_activatable(
        created_by="author-a",
        approved_by="approver-b",
        backtest_passed=True,
    )


def test_assert_activatable_raises_backtest_first():
    """BacktestNotPassedError is raised BEFORE the two-person check (backtest checked first)."""
    from dhanradar.scoring.engine.activation import BacktestNotPassedError, assert_activatable

    with pytest.raises(BacktestNotPassedError):
        assert_activatable(
            created_by="author-a",
            approved_by="approver-b",
            backtest_passed=False,
        )
