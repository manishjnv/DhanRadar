"""Unit tests for the B26 admin gate (`RequireAdmin`) + `settings.admin_user_ids`.

The gate is fail-closed and surface-hiding: every non-admin (anonymous OR an
authenticated non-admin) gets 404; an empty allowlist denies everyone.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from dhanradar.deps import RequireAdmin, UserContext


def _ctx(user_id: str, is_anon: bool = False) -> UserContext:
    return UserContext(user_id=user_id, tier="free", is_anonymous=is_anon)


async def _call(user: UserContext) -> UserContext:
    return await RequireAdmin()(user)


def test_admin_user_ids_parses_normalizes_and_drops_garbage(monkeypatch):
    from dhanradar.config import settings

    a = "11111111-1111-1111-1111-111111111111"
    b = "22222222-2222-2222-2222-222222222222"
    # Uppercase, surrounding whitespace, blank entries, and non-UUID garbage.
    raw = f"  {a.upper()} , {b} , , garbage ,"
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", raw)
    # Confirm the monkeypatch actually mutated the field (guards against a vacuous
    # test if pydantic ever made the field immutable to setattr).
    assert settings.ADMIN_USER_IDS == raw
    assert settings.admin_user_ids == frozenset({a, b})


async def test_admin_in_allowlist_passes_and_returns_context(monkeypatch):
    from dhanradar.config import settings

    a = str(uuid.uuid4())
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", a)
    out = await _call(_ctx(a))
    assert out.user_id == a


async def test_admin_match_is_case_insensitive_on_uuid(monkeypatch):
    from dhanradar.config import settings

    a = str(uuid.uuid4())
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", a.upper())  # stored upper
    out = await _call(_ctx(a))  # presented lower → normalized match
    assert out.user_id == a


async def test_authenticated_non_admin_gets_404(monkeypatch):
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", str(uuid.uuid4()))
    with pytest.raises(HTTPException) as ei:
        await _call(_ctx(str(uuid.uuid4())))  # valid UUID, not in allowlist
    assert ei.value.status_code == 404


async def test_anonymous_gets_404(monkeypatch):
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", str(uuid.uuid4()))
    with pytest.raises(HTTPException) as ei:
        await _call(_ctx("anonymous", is_anon=True))
    assert ei.value.status_code == 404


async def test_empty_allowlist_denies_everyone(monkeypatch):
    from dhanradar.config import settings

    a = str(uuid.uuid4())
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")  # no admins → fail-closed
    with pytest.raises(HTTPException) as ei:
        await _call(_ctx(a))
    assert ei.value.status_code == 404


async def test_non_string_user_id_gets_404(monkeypatch):
    """A non-string user_id (defensive: the real stack never produces one) must hit
    the TypeError branch and 404, never an unhandled 500."""
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", str(uuid.uuid4()))
    with pytest.raises(HTTPException) as ei:
        await _call(_ctx(None))  # type: ignore[arg-type]
    assert ei.value.status_code == 404


async def test_garbage_allowlist_entry_grants_no_one(monkeypatch):
    """A malformed allowlist entry must never grant access, even to a user whose raw
    id string equals it (the id can't parse as a UUID → 404)."""
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "not-a-uuid")
    assert settings.admin_user_ids == frozenset()
    with pytest.raises(HTTPException) as ei:
        await _call(_ctx("not-a-uuid"))
    assert ei.value.status_code == 404
