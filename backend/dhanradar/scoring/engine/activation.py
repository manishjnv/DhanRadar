"""
DhanRadar — Scoring-engine activation gate (B6/B28).

Activating a scoring model_version requires:
  1. The two-person methodology gate (approved_by != created_by, governance §7 / B6).
  2. A passed backtest (§8 pass-gates asserted by the caller).

On success, an activated ``rating_engine_changelog`` row is written; the registry is
the authoritative runtime activation state (the engine's sync ``score()`` falls back to
the file ``activated`` flag when it has no DB session).

Module isolation: scoring→compliance.service is interface-only coupling — compliance
owns the changelog table writes/reads.  Do NOT import the compliance ORM model here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from dhanradar.scoring.engine import governance


class BacktestNotPassedError(Exception):
    """Activation refused: the §8 backtest pass-gates have not been asserted."""


class AlreadyActivatedError(Exception):
    """The model_version is already activated in the registry."""


# Activation is MONOTONIC (a version, once activated, stays activated — rollback/
# retire is a separate out-of-scope flow), so memoizing only POSITIVE results is
# safe and needs no invalidation.
_activated_cache: set[str] = set()


def assert_activatable(*, created_by: str, approved_by: str, backtest_passed: bool) -> None:
    """Pure gate check. Raises BacktestNotPassedError or governance.TwoPersonGateError."""
    if not backtest_passed:
        raise BacktestNotPassedError(
            f"backtest pass-gates not asserted for activation (created_by={created_by!r})"
        )
    if not governance.two_person_gate_ok(created_by, approved_by):
        raise governance.TwoPersonGateError(
            f"two-person gate failed: approved_by must be set and != created_by "
            f"(created_by={created_by!r}, approved_by={approved_by!r})"
        )


async def is_activated(db: Any, model_version: str) -> bool:
    """Authoritative DB-registry activation check (positive-memoized)."""
    if model_version in _activated_cache:
        return True
    from dhanradar.compliance import service

    ok = await service.is_engine_version_activated(db, model_version)
    if ok:
        _activated_cache.add(model_version)
    return ok


async def activate_model_version(
    db: Any,
    *,
    model_version: str,
    created_by: str,
    approved_by: str,
    factors_before: dict,
    factors_after: dict,
    methodology_url: str,
    backtest_passed: bool,
    backtest: dict | None = None,
    drift: dict | None = None,
) -> dict:
    """Run the gate, guard against double-activation, and write an activated
    rating_engine_changelog row (the activation record). Returns the changelog dict.

    Raises:
        BacktestNotPassedError: §8 backtest pass-gates not asserted.
        governance.TwoPersonGateError: approved_by missing or equals created_by.
        AlreadyActivatedError: model_version already has an activated registry row.
    """
    assert_activatable(
        created_by=created_by, approved_by=approved_by, backtest_passed=backtest_passed
    )
    from sqlalchemy.exc import IntegrityError

    from dhanradar.compliance import service

    # Persist the real §8 backtest pass-gate outcome (PR-5). assert_activatable above
    # guarantees backtest_passed is True for any activated row, so this records
    # {"passed": True}; a caller may still pass a richer backtest dict explicitly.
    # Surfaced read-only per version on /admin/ai/versions.
    if backtest is None:
        backtest = {"passed": backtest_passed}

    # Fast-path dup guard. The `uq_engine_changelog_activated_per_version` partial-
    # unique index (migration 0009) is the race-safe backstop: a concurrent activation
    # of the same version that slips past this SELECT is rejected at commit.
    if await service.is_engine_version_activated(db, model_version):
        raise AlreadyActivatedError(model_version)
    try:
        entry = await service.record_engine_changelog(
            db,
            model_version=model_version,
            created_by=created_by,
            approved_by=approved_by,
            factors_before=factors_before,
            factors_after=factors_after,
            methodology_url=methodology_url,
            activated=True,
            activated_at=datetime.now(UTC),
            backtest=backtest,
            drift=drift,
        )
    except IntegrityError as exc:
        await db.rollback()
        raise AlreadyActivatedError(model_version) from exc
    _activated_cache.add(model_version)
    return entry
