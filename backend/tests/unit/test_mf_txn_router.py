"""Unit tests for the MF transaction provider switch (admin/mf_txn_router.py).

Mirrors test_admin_auth.py's pattern of calling route/dependency functions
directly (no TestClient / no live DB) — the admin gate itself is already
covered generically in test_admin_auth.py; the "non-admin/anonymous → 404"
case here reuses that same RequireAdmin() call.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from dhanradar.admin import mf_txn_router as router_mod
from dhanradar.deps import RequireAdmin, UserContext


def _admin_ctx() -> UserContext:
    return UserContext(user_id=str(uuid.uuid4()), tier="free", is_anonymous=False)


class _FakeRedis:
    """Minimal async Redis stub — dict-backed get/set/delete."""

    def __init__(self, seed: dict[str, str] | None = None, *, raise_on_get: bool = False) -> None:
        self.store: dict[str, str] = dict(seed or {})
        self.raise_on_get = raise_on_get

    async def get(self, key: str) -> str | None:
        if self.raise_on_get:
            raise ConnectionError("redis down")
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


@pytest.fixture(autouse=True)
def _no_audit(monkeypatch):
    """record_admin_action is fire-and-forget elsewhere; stub it here so tests
    assert on call args instead of hitting a real DB."""
    calls: list[dict] = []

    async def _fake(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(router_mod, "record_admin_action", _fake)
    return calls


def _patch_redis(monkeypatch, fake: _FakeRedis) -> None:
    monkeypatch.setattr(router_mod, "get_redis", lambda: fake)


# ---------------------------------------------------------------------------
# active_provider() resolution
# ---------------------------------------------------------------------------


async def test_default_resolves_bse(monkeypatch):
    _patch_redis(monkeypatch, _FakeRedis())
    assert await router_mod.active_provider() == ("bse", "default")


async def test_valid_bse_override_resolves_override(monkeypatch):
    _patch_redis(monkeypatch, _FakeRedis({router_mod._OVERRIDE_KEY: "bse"}))
    assert await router_mod.active_provider() == ("bse", "override")


async def test_garbage_override_falls_back_to_default(monkeypatch):
    _patch_redis(monkeypatch, _FakeRedis({router_mod._OVERRIDE_KEY: "garbage"}))
    assert await router_mod.active_provider() == ("bse", "default")


async def test_redis_error_fails_safe_to_bse(monkeypatch):
    _patch_redis(monkeypatch, _FakeRedis(raise_on_get=True))
    assert await router_mod.active_provider() == ("bse", "default")


async def test_mfu_override_while_not_ready_resolves_to_bse(monkeypatch):
    assert router_mod._MFU_ORDER_RAIL_READY is False
    _patch_redis(monkeypatch, _FakeRedis({router_mod._OVERRIDE_KEY: "mfu"}))
    assert await router_mod.active_provider() == ("bse", "default")


# ---------------------------------------------------------------------------
# PUT /provider
# ---------------------------------------------------------------------------


async def test_put_bse_sets_override_key_and_audits(monkeypatch, _no_audit):
    fake = _FakeRedis()
    _patch_redis(monkeypatch, fake)
    admin = _admin_ctx()
    out = await router_mod.put_provider(router_mod.ProviderRequest(provider="bse"), admin)
    assert fake.store[router_mod._OVERRIDE_KEY] == "bse"
    assert out["provider"] == "bse"
    assert _no_audit[-1]["action"] == "mf_txn.provider.set"
    assert _no_audit[-1]["target_id"] == "bse"
    assert _no_audit[-1]["result"] == "bse->bse"


async def test_put_null_deletes_override_key(monkeypatch, _no_audit):
    fake = _FakeRedis({router_mod._OVERRIDE_KEY: "bse"})
    _patch_redis(monkeypatch, fake)
    admin = _admin_ctx()
    out = await router_mod.put_provider(router_mod.ProviderRequest(provider=None), admin)
    assert router_mod._OVERRIDE_KEY not in fake.store
    assert out["source"] == "default"
    assert _no_audit[-1]["target_id"] == "default"


async def test_put_mfu_rejected_409_key_unchanged_and_audited(monkeypatch, _no_audit):
    fake = _FakeRedis()
    _patch_redis(monkeypatch, fake)
    admin = _admin_ctx()
    with pytest.raises(HTTPException) as ei:
        await router_mod.put_provider(router_mod.ProviderRequest(provider="mfu"), admin)
    assert ei.value.status_code == 409
    assert router_mod._OVERRIDE_KEY not in fake.store
    assert _no_audit[-1]["result"] == "rejected_not_ready"
    assert _no_audit[-1]["target_id"] == "mfu"


# ---------------------------------------------------------------------------
# GET /provider shape
# ---------------------------------------------------------------------------


async def test_get_provider_shape(monkeypatch):
    _patch_redis(monkeypatch, _FakeRedis())
    admin = _admin_ctx()
    out = await router_mod.get_provider(admin)
    assert out["provider"] == "bse"
    assert out["provider_label"] == "BSE StAR MF"
    assert out["source"] == "default"
    assert out["default"] == "bse"
    ids = {o["id"] for o in out["options"]}
    assert ids == {"bse", "mfu"}
    mfu_option = next(o for o in out["options"] if o["id"] == "mfu")
    assert mfu_option["ready"] is False
    assert mfu_option["note"]


# ---------------------------------------------------------------------------
# Admin gate — non-admin/anonymous → 404 (matches test_admin_auth.py pattern;
# every route on this router depends on the same RequireAdmin()).
# ---------------------------------------------------------------------------


async def test_non_admin_gets_404(monkeypatch):
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", str(uuid.uuid4()))
    with pytest.raises(HTTPException) as ei:
        await RequireAdmin()(
            UserContext(user_id=str(uuid.uuid4()), tier="free", is_anonymous=False)
        )
    assert ei.value.status_code == 404


async def test_anonymous_gets_404(monkeypatch):
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", str(uuid.uuid4()))
    with pytest.raises(HTTPException) as ei:
        await RequireAdmin()(UserContext(user_id="anonymous", tier="free", is_anonymous=True))
    assert ei.value.status_code == 404
