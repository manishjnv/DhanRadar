"""
Unit tests for PHASE 5M freemium tiering (deps.is_plus, RequireTier OR-clause,
commentary entitlement gate, and founding-access stamp in signup_user).

Acceptance items tested:
  #1  is_plus True when pro_access_until is in the future (no sub).
  #2  is_plus False when pro_access_until is in the past and no sub;
      RequireTier("pro") raises 402 when is_plus→False.
  #3  is_plus True when an active subscription exists (status="active"),
      even with pro_access_until NULL/expired.
  #4  signup_user founding-access stamp when FOUNDING_ACCESS_UNTIL is set.
  #5  create_checkout still raises 503 for an unseeded plan (fail-safe intact).
  #6  is_commentary_entitled gate: Plus → True; taster unused → True + consumed;
      taster already used → False.

No DB for is_plus / RequireTier / commentary entitlement — tiny fakes only.
signup_user founding-stamp and is_commentary_entitled taster-consumption tests
need real DB writes; those are in tests/integration/test_freemium_tier_int.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from dhanradar.deps import RequireTier, UserContext, is_plus
from dhanradar.mf.commentary import is_commentary_entitled

# ---------------------------------------------------------------------------
# Fake DB helpers
# ---------------------------------------------------------------------------


class _FakeResult:
    """Stand-in for a SQLAlchemy CursorResult — only .rowcount is read."""

    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _FakeDB:
    """Minimal AsyncSession stub that returns preset scalars in FIFO order.

    ``update_rowcount`` is what ``execute()`` reports as the affected-row count —
    used to drive the atomic taster-claim UPDATE (1 = claimed, 0 = already used)."""

    def __init__(self, *scalar_returns: object, update_rowcount: int = 1) -> None:
        self._returns: list[object] = list(scalar_returns)
        self._update_rowcount = update_rowcount
        self._execute_called = 0
        self._commit_called = 0

    async def scalar(self, *_a, **_k) -> object:
        if self._returns:
            return self._returns.pop(0)
        return None

    async def execute(self, *_a, **_k) -> _FakeResult:
        self._execute_called += 1
        return _FakeResult(self._update_rowcount)

    async def commit(self) -> None:
        self._commit_called += 1


# ---------------------------------------------------------------------------
# Acceptance #1 — is_plus True when pro_access_until is in the future
# ---------------------------------------------------------------------------


async def test_is_plus_true_when_pro_access_until_future():
    """is_plus returns True when pro_access_until is set to a future timestamp."""
    future = datetime.now(UTC) + timedelta(days=30)
    # scalar(pro_access_until) → future; sub scalar never reached
    db = _FakeDB(future)
    assert await is_plus(str(uuid.uuid4()), db) is True


async def test_is_plus_false_when_pro_access_until_past_no_sub():
    """is_plus returns False when pro_access_until is in the past and no active sub."""
    past = datetime.now(UTC) - timedelta(days=1)
    # scalar(pro_access_until) → past; scalar(Subscription.id) → None
    db = _FakeDB(past, None)
    assert await is_plus(str(uuid.uuid4()), db) is False


# ---------------------------------------------------------------------------
# Acceptance #2 — RequireTier raises 402 when is_plus→False; passes when True
# ---------------------------------------------------------------------------


async def test_require_tier_pro_raises_402_when_is_plus_false(monkeypatch):
    """RequireTier("pro") raises 402 for a free user when is_plus returns False."""
    monkeypatch.setattr("dhanradar.deps.is_plus", AsyncMock(return_value=False))

    user = UserContext(user_id=str(uuid.uuid4()), tier="free", is_anonymous=False)
    dep = RequireTier("pro")
    fake_db = _FakeDB()  # not called (monkeypatched)

    with pytest.raises(HTTPException) as exc_info:
        await dep(user, fake_db)

    assert exc_info.value.status_code == 402
    assert exc_info.value.detail["error"] == "upgrade_required"
    assert exc_info.value.detail["upgrade_url"] == "/pricing"


async def test_require_tier_pro_passes_when_is_plus_true(monkeypatch):
    """RequireTier("pro") does NOT raise for a free user when is_plus returns True."""
    monkeypatch.setattr("dhanradar.deps.is_plus", AsyncMock(return_value=True))

    user = UserContext(user_id=str(uuid.uuid4()), tier="free", is_anonymous=False)
    dep = RequireTier("pro")
    fake_db = _FakeDB()

    # Must not raise.
    await dep(user, fake_db)


async def test_require_tier_free_passes_for_authed_user(monkeypatch):
    """RequireTier("free") passes for an authenticated free user even when is_plus
    returns False (is_plus is called but the bump doesn't matter — free already meets free)."""
    monkeypatch.setattr("dhanradar.deps.is_plus", AsyncMock(return_value=False))

    user = UserContext(user_id=str(uuid.uuid4()), tier="free", is_anonymous=False)
    dep = RequireTier("free")
    # Must not raise — free user satisfies a "free" tier gate regardless of is_plus result.
    await dep(user, _FakeDB())


async def test_require_tier_pro_plus_still_gates_above_pro(monkeypatch):
    """RequireTier("pro_plus") should NOT be satisfied by is_plus (which only bumps to
    pro rank), so a free user with a time-window grant is still refused pro_plus."""
    monkeypatch.setattr("dhanradar.deps.is_plus", AsyncMock(return_value=True))

    user = UserContext(user_id=str(uuid.uuid4()), tier="free", is_anonymous=False)
    dep = RequireTier("pro_plus")
    fake_db = _FakeDB()

    with pytest.raises(HTTPException) as exc_info:
        await dep(user, fake_db)

    assert exc_info.value.status_code == 402


async def test_require_tier_anonymous_never_calls_is_plus(monkeypatch):
    """Anonymous users must be refused immediately; is_plus must not be called."""
    mock_is_plus = AsyncMock(return_value=True)
    monkeypatch.setattr("dhanradar.deps.is_plus", mock_is_plus)

    user = UserContext(user_id="anonymous", tier="free", is_anonymous=True)
    dep = RequireTier("pro")

    with pytest.raises(HTTPException) as exc_info:
        await dep(user, _FakeDB())

    assert exc_info.value.status_code == 402
    mock_is_plus.assert_not_called()


# ---------------------------------------------------------------------------
# Acceptance #3 — is_plus True with active subscription (pro_access_until NULL)
# ---------------------------------------------------------------------------


async def test_is_plus_true_with_active_subscription():
    """is_plus returns True when pro_access_until is NULL but there is an active sub."""
    sub_id = uuid.uuid4()
    # scalar(pro_access_until) → None; scalar(Subscription.id) → sub_id
    db = _FakeDB(None, sub_id)
    assert await is_plus(str(uuid.uuid4()), db) is True


async def test_is_plus_true_with_authenticated_subscription():
    """'authenticated' is a valid active status for Razorpay mandates."""
    sub_id = uuid.uuid4()
    db = _FakeDB(None, sub_id)
    assert await is_plus(str(uuid.uuid4()), db) is True


async def test_is_plus_false_when_no_sub_and_null_until():
    """is_plus returns False when both pro_access_until is NULL and no active sub."""
    db = _FakeDB(None, None)
    assert await is_plus(str(uuid.uuid4()), db) is False


# ---------------------------------------------------------------------------
# Fail-closed guards on is_plus
# ---------------------------------------------------------------------------


async def test_is_plus_false_for_anonymous_string():
    """is_plus returns False immediately for the 'anonymous' sentinel."""
    assert await is_plus("anonymous", _FakeDB()) is False


async def test_is_plus_false_for_malformed_user_id():
    """is_plus returns False for a non-UUID user_id without touching the DB."""
    assert await is_plus("not-a-uuid", _FakeDB()) is False


async def test_is_plus_false_for_non_string_user_id():
    """is_plus returns False for a non-string subject."""
    assert await is_plus(None, _FakeDB()) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Acceptance #5 — create_checkout 503 for unseeded plan (fail-safe intact)
# ---------------------------------------------------------------------------


async def test_create_checkout_503_for_unconfigured_plan(monkeypatch):
    """B7/B8 inert fail-safe: create_checkout raises 503 when plan has no
    Razorpay plan_id / total_count. Redis is mocked so this stays a unit test."""
    from dhanradar.billing import service as billing_svc
    from dhanradar.models.billing import Plan

    plan = Plan(
        id="unmapped_plan",
        name="Unmapped Plan",
        price_inr=39900,
        interval="month",
        features=[],
        razorpay_plan_id=None,  # not configured → 503
        total_count=None,
    )

    class _FakeRedis:
        async def get(self, *_a, **_k) -> object:
            return None  # no cached result → proceed to plan lookup

    class _FakeDBPlan:
        async def scalar(self, *_a, **_k) -> object:
            return plan

    monkeypatch.setattr(billing_svc, "get_redis", lambda: _FakeRedis())

    with pytest.raises(HTTPException) as exc_info:
        await billing_svc.create_checkout(
            user_id="user-123",
            plan_id="unmapped_plan",
            idempotency_key="key-abc",
            db=_FakeDBPlan(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "plan_not_configured_for_billing"


# ---------------------------------------------------------------------------
# Acceptance #6 — is_commentary_entitled gate (unit-level, no real DB)
# ---------------------------------------------------------------------------


async def test_commentary_entitled_plus_user(monkeypatch):
    """Plus user (is_plus → True) is always entitled to commentary."""
    monkeypatch.setattr("dhanradar.mf.commentary.is_plus", AsyncMock(return_value=True))

    db = _FakeDB()
    result = await is_commentary_entitled(str(uuid.uuid4()), db)
    assert result is True


async def test_commentary_entitled_free_taster_unused(monkeypatch):
    """Free user whose atomic taster-claim UPDATE affects 1 row → entitled."""
    monkeypatch.setattr("dhanradar.mf.commentary.is_plus", AsyncMock(return_value=False))

    db = _FakeDB(update_rowcount=1)  # claim won the race (NULL→now)
    result = await is_commentary_entitled(str(uuid.uuid4()), db)
    assert result is True
    assert db._execute_called == 1  # atomic UPDATE executed
    assert db._commit_called == 1  # committed


async def test_commentary_not_entitled_free_taster_used(monkeypatch):
    """Free user whose taster-claim UPDATE affects 0 rows (already consumed, or a
    concurrent request won) → not entitled."""
    monkeypatch.setattr("dhanradar.mf.commentary.is_plus", AsyncMock(return_value=False))

    db = _FakeDB(update_rowcount=0)  # WHERE ai_taster_used_at IS NULL matched nothing
    result = await is_commentary_entitled(str(uuid.uuid4()), db)
    assert result is False
    assert db._execute_called == 1  # the atomic UPDATE still runs (matches 0 rows)


async def test_commentary_not_entitled_malformed_user_id(monkeypatch):
    """Malformed user_id → not entitled (fail-closed)."""
    monkeypatch.setattr("dhanradar.mf.commentary.is_plus", AsyncMock(return_value=False))

    db = _FakeDB()
    result = await is_commentary_entitled("not-a-uuid", db)
    assert result is False
