"""
DhanRadar — Admin BSE UAT console router (/admin/bse-uat).

Read-only proxy onto the BSE StAR MF 2.0 **UAT demo tenant** so the BSE demo
session can be driven from the DhanRadar UI instead of a terminal. Exposes the
UAT evidence surfaces only: session login, get_ucc, order_get/order_list,
mandate_list, plus our own bse.webhook_events rows.

Auth: RequireAdmin() — mirrors admin/ops_router.py (404 surface-hiding).

Safety rails:
  * UAT-ONLY — refuses to start unless the configured base URL contains
    "demo" (never points at the production BSE gateway).
  * The BSE password is accepted per-request, used for ONE login call, and
    never stored or logged; only the short-lived Bearer token is cached in
    Redis (TTL < BSE's ~30 min token life). ONE login per session request —
    wrong passwords count toward BSE's member lockout, so no retry loop.
  * Every proxied call is a read (get/list); nothing here can create or
    mutate anything on BSE.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.audit.service import record_admin_action
from dhanradar.config import settings
from dhanradar.db import get_admin_db
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.models.bse import BSEWebhookEvent
from dhanradar.redis_client import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/bse-uat", tags=["admin-bse-uat"])

_TOKEN_KEY = "bse_uat:access_token"
_TOKEN_TTL = 1500  # seconds — under BSE's ~30 min token life
_MEMBER = "66910"
_USERNAME = f"member/{_MEMBER}/manishkumar"
_TIMEOUT = 30.0


def _base_url() -> str:
    # ALWAYS the UAT tenant — deliberately ignores BSE_ENV so this console can
    # never reach the production BSE gateway, whatever the deploy env says.
    base = settings.BSE_API_BASE_URL_UAT.rstrip("/")
    if "demo" not in base:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "BSE UAT console is demo-tenant-only")
    return base


async def _bse_post(path: str, body: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        # BSE's OWN outbound auth scheme — not our inbound cookie auth (non-neg #5 governs inbound)
        headers["Authorization"] = f"Bearer {token}"  # nosec — outbound to BSE, not our session auth
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            res = await client.post(f"{_base_url()}/{path}", json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"BSE UAT unreachable: {exc.__class__.__name__}") from exc
    try:
        payload = res.json()
    except ValueError:
        payload = {"raw": res.text[:500]}
    return {"http_status": res.status_code, "body": payload}


async def _cached_token() -> str:
    token = await get_redis().get(_TOKEN_KEY)
    if not token:
        raise HTTPException(status.HTTP_409_CONFLICT, "No BSE UAT session — login first")
    return token.decode() if isinstance(token, bytes) else token


class SessionRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@router.post("/session")
async def create_session(
    body: SessionRequest,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> dict[str, Any]:
    """ONE login attempt against BSE UAT; caches BSE's outbound token in Redis (not our session auth)."""
    result = await _bse_post("login", {"username": _USERNAME, "password": body.password})
    token = ((result["body"].get("data") or {}).get("access_token")) if isinstance(result["body"], dict) else None
    ok = result["http_status"] == 200 and bool(token)
    await record_admin_action(
        admin_id=str(admin.user_id),
        action="bse_uat_login",
        target_type="bse_member",
        target_id=_MEMBER,
        result="success" if ok else f"failed_http_{result['http_status']}",
    )
    if not ok:
        # surface BSE's own error body (no secrets in it); do NOT retry
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail={"bse": result["body"]})
    await get_redis().set(_TOKEN_KEY, token, ex=_TOKEN_TTL)
    return {"ok": True, "member_code": _MEMBER, "expires_in": _TOKEN_TTL}


@router.get("/session")
async def session_status(
    _admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> dict[str, Any]:
    ttl = await get_redis().ttl(_TOKEN_KEY)
    return {"active": ttl > 0, "expires_in": max(ttl, 0), "member_code": _MEMBER}


@router.get("/ucc/{client_code}")
async def get_ucc(
    client_code: str,
    _admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> dict[str, Any]:
    token = await _cached_token()
    return await _bse_post(
        "v2/get_ucc",
        {"data": {"member": {"member_id": _MEMBER}, "investor": {"client_code": client_code}}},
        token,
    )


@router.get("/order/{order_id}")
async def get_order(
    order_id: int,
    _admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> dict[str, Any]:
    token = await _cached_token()
    return await _bse_post("order_get", {"data": {"id": order_id, "filter_param": {}}}, token)


@router.get("/orders")
async def list_orders(
    _admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> dict[str, Any]:
    token = await _cached_token()
    return await _bse_post(
        "order_list",
        {
            "data": {
                "member_code": _MEMBER,
                "fields": ["ALL"],
                "start": 0,
                "length": 50,
                "filter_param": {"open_close": "a"},
            }
        },
        token,
    )


@router.get("/mandates")
async def list_mandates(
    _admin: Annotated[UserContext, Depends(RequireAdmin())],
    ucc: str | None = None,
) -> dict[str, Any]:
    token = await _cached_token()
    filter_param: dict[str, Any] = {"member_code": _MEMBER}
    if ucc:
        filter_param["ucc"] = [ucc]
    return await _bse_post(
        "mandate_list",
        {
            "data": {
                "start": 0,
                "length": 50,
                "fields": ["ALL"],
                "count_only": False,
                "search": {"value": ""},
                "filter_param": filter_param,
            }
        },
        token,
    )


@router.get("/webhook-events")
async def webhook_events(
    _admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Our own bse.webhook_events inbox — the receiver-side evidence trail."""
    rows = (
        (
            await db.execute(
                select(BSEWebhookEvent)
                .order_by(BSEWebhookEvent.received_at.desc())
                .limit(min(max(limit, 1), 200))
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "event_type": r.event_type,
            "event": r.event,
            "client_code": r.client_code,
            "order_id": r.order_id,
            "received_at": r.received_at.isoformat() if r.received_at else None,
            "processed_at": r.processed_at.isoformat() if r.processed_at else None,
        }
        for r in rows
    ]
