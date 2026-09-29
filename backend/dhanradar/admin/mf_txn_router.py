"""
DhanRadar — Admin MF transaction provider switch (/admin/mf-txn).

The single neutral seam that names which rail (BSE StAR MF or MF Utility)
new MF orders should use. It does NOT place orders itself and must NEVER
import from the BSE or MFU packages/routers (module isolation, non-neg #7) —
it only stores a provider name.

LOCKED to BSE: MFU has no order rail yet (Phase 0 foundation only — see
config.py's MFU block). `_MFU_ORDER_RAIL_READY` is the single flip point for
Phase 2; until then "mfu" can never resolve as the active provider, even if
an operator hand-sets the Redis override (defence in depth).

Idempotency-Key: NOT required here, matching admin/router.py's documented
convention (see its module docstring) — this PUT is naturally idempotent
(setting the same provider twice, or clearing to default, is a safe no-op),
so duplicate-submit safety holds without a key.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from dhanradar.audit.service import record_admin_action
from dhanradar.config import settings
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.redis_client import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/mf-txn", tags=["admin-mf-txn"])

_OVERRIDE_KEY = "mf_txn:provider_override"
_PROVIDERS = ("bse", "mfu")
_LABELS = {"bse": "BSE StAR MF", "mfu": "MF Utility"}
# ponytail: flips to True in MFU Phase 2 when NORMAL-TXN orders land; until
# then MFU cannot be selected.
_MFU_ORDER_RAIL_READY = False


async def active_provider() -> tuple[str, str]:
    """Resolve the provider new orders should use: (provider, source).

    source is "override" (Redis) or "default" (settings.MF_TXN_PROVIDER_DEFAULT,
    or "bse" if that setting is itself invalid). Any Redis error, or an "mfu"
    override while the order rail isn't ready, fails safe to ("bse", "default").
    """
    try:
        raw = await get_redis().get(_OVERRIDE_KEY)
    except Exception:  # noqa: BLE001 — fail-safe to BSE, never break the caller
        logger.warning("mf_txn: redis read failed, defaulting to bse", exc_info=True)
        return "bse", "default"

    if raw is not None:
        value = raw.decode() if isinstance(raw, bytes) else raw
        if value in _PROVIDERS:
            if value == "mfu" and not _MFU_ORDER_RAIL_READY:
                return "bse", "default"
            return value, "override"

    default = settings.MF_TXN_PROVIDER_DEFAULT
    if default in _PROVIDERS:
        if default == "mfu" and not _MFU_ORDER_RAIL_READY:
            return "bse", "default"
        return default, "default"
    return "bse", "default"


def _options() -> list[dict[str, object]]:
    return [
        {"id": "bse", "label": _LABELS["bse"], "ready": True, "note": ""},
        {
            "id": "mfu",
            "label": _LABELS["mfu"],
            "ready": _MFU_ORDER_RAIL_READY,
            "note": ""
            if _MFU_ORDER_RAIL_READY
            else "Not ready yet — MF Utility orders come in a later phase.",
        },
    ]


async def _state_response() -> dict[str, object]:
    provider, source = await active_provider()
    return {
        "provider": provider,
        "provider_label": _LABELS[provider],
        "source": source,
        "default": settings.MF_TXN_PROVIDER_DEFAULT
        if settings.MF_TXN_PROVIDER_DEFAULT in _PROVIDERS
        else "bse",
        "options": _options(),
    }


@router.get("/provider")
async def get_provider(
    _admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> dict[str, object]:
    return await _state_response()


class ProviderRequest(BaseModel):
    provider: Literal["bse", "mfu"] | None = None


@router.put("/provider")
async def put_provider(
    body: ProviderRequest,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> dict[str, object]:
    old, _source = await active_provider()

    if body.provider == "mfu" and not _MFU_ORDER_RAIL_READY:
        await record_admin_action(
            admin_id=str(admin.user_id),
            action="mf_txn.provider.set",
            target_type="mf_txn_provider",
            target_id="mfu",
            result="rejected_not_ready",
        )
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="MF Utility can't take orders yet, so it can't be selected.",
        )

    redis = get_redis()
    if body.provider is None:
        await redis.delete(_OVERRIDE_KEY)
        new_target = "default"
    else:
        await redis.set(_OVERRIDE_KEY, body.provider)
        new_target = body.provider

    await record_admin_action(
        admin_id=str(admin.user_id),
        action="mf_txn.provider.set",
        target_type="mf_txn_provider",
        target_id=new_target,
        result=f"{old}->{new_target}",
    )
    return await _state_response()
