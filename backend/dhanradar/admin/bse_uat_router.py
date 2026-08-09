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
  * Writes are limited to the UAT order rail (order_new + order-2FA + hosted
    PG link) for the /mf/invest wizard — UAT demo tenant only, RequireAdmin,
    every attempt audited. Money can never route through us: payment uses
    BSE's HOSTED PG page (payee = ICCL), never send_payment_info.
"""

from __future__ import annotations

import json
import logging
import re
import time
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


# BSE's WAF serves an HTML block page (HTTP 200!) to python user-agents —
# a real browser UA is mandatory (bse-api.md recipe; same class as the
# Resend/Cloudflare 1010 gotcha in infra-notes).
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


async def _bse_post(path: str, body: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": _BROWSER_UA,
    }
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
    # Login body is data-wrapped like every other BSE call (bse-api.md recipe).
    result = await _bse_post("login", {"data": {"username": _USERNAME, "password": body.password}})
    # BSE nests the token either at data.access_token or data.data.access_token
    # (both shapes observed on the demo tenant — see bse-api.md login recipe).
    d = (result["body"].get("data") or {}) if isinstance(result["body"], dict) else {}
    token = d.get("access_token") or (d.get("data") or {}).get("access_token")
    ok = result["http_status"] == 200 and bool(token)
    await record_admin_action(
        admin_id=str(admin.user_id),
        action="bse_uat_login",
        target_type="bse_member",
        target_id=_MEMBER,
        result="success" if ok else f"failed_http_{result['http_status']}",
    )
    if not ok:
        # Surface BSE's own error body (no secrets in a failed-login response);
        # string detail so the UI shows it verbatim. Logged too — do NOT retry.
        body_str = str(result["body"])[:400]
        logger.warning(
            "bse_uat login failed: http=%s body=%s", result["http_status"], body_str
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"BSE login not accepted (http {result['http_status']}): {body_str}",
        )
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
    order_id: str | None = None,
) -> list[dict[str, Any]]:
    """Our own bse.webhook_events inbox — the receiver-side evidence trail."""
    stmt = select(BSEWebhookEvent).order_by(BSEWebhookEvent.received_at.desc())
    if order_id:
        stmt = stmt.where(BSEWebhookEvent.order_id == order_id)
    rows = (await db.execute(stmt.limit(min(max(limit, 1), 200)))).scalars().all()
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


# ---------------------------------------------------------------------------
# UAT order rail — /mf/invest wizard backend (order_new → order-2FA → PG link)
# Flow + payload shapes proven live 2026-07-12 (bse-test-results Stage 2b/3)
# and re-verified 2026-08-06. UAT tenant + RequireAdmin + audit on every write.
# ---------------------------------------------------------------------------

_UCC_DEFAULT = "DRTEST009"  # ACTIVE, transaction_ready UAT client — reusable per runbook
_SCHEME_CACHE_TTL = 24 * 3600
_TWOFA_STASH_TTL = 600  # page jwt lives ~15 min; stash a bit under


def _find_url(obj: Any, needle: str) -> str | None:
    """Recursively find the first string containing `needle` in a JSON-ish tree."""
    if isinstance(obj, str) and needle in obj:
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            if (f := _find_url(v, needle)) is not None:
                return f
    if isinstance(obj, list):
        for v in obj:
            if (f := _find_url(v, needle)) is not None:
                return f
    return None


def _parse_2fa_page(html: str) -> tuple[str | None, list[str]]:
    """Extract the page jwt + row lids from a BSE 2FA view-object page.

    `data-id` is UNQUOTED in BSE's HTML (data-id=<uuid>); jwt sits in
    <meta name="jwt-token" content="...">, attribute order not guaranteed.
    """
    jwt = None
    m = re.search(r'name=["\']jwt-token["\'][^>]*content=["\']([^"\']+)["\']', html)
    if not m:
        m = re.search(r'content=["\']([^"\']+)["\'][^>]*name=["\']jwt-token["\']', html)
    if m:
        jwt = m.group(1)
    lids = list(dict.fromkeys(re.findall(r"data-id=[\"']?([0-9a-fA-F-]{36})", html)))
    return jwt, lids


def _extract_order_id(body: Any) -> str | None:
    """order_new/order_get responses nest the id differently across shapes.

    Live UAT 2026-08-07: order_new returns data.items[0].id (founder's first
    wizard order 5001212827 was placed but read as a failure before this path
    was added). order_get returns data.id; docs also show data.orders[0]."""
    if not isinstance(body, dict):
        return None
    d = body.get("data") or {}
    if not isinstance(d, dict):
        return None
    candidates: list[Any] = [d]
    for key in ("items", "orders"):
        rows = d.get(key)
        if isinstance(rows, list):
            candidates.extend(rows)
    for candidate in candidates:
        if isinstance(candidate, dict):
            for k in ("id", "order_id"):
                if candidate.get(k):
                    return str(candidate[k])
    return None


async def _bse_get_html(url: str) -> tuple[int, str]:
    if "demo" not in url:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "2FA link is not on the UAT demo tenant")
    headers = {"User-Agent": _BROWSER_UA, "Accept": "text/html"}
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        try:
            res = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"BSE 2FA page unreachable: {exc.__class__.__name__}") from exc
    return res.status_code, res.text


class SchemeLookupOut(BaseModel):
    isin: str
    found: bool
    scheme: dict[str, Any] | None = None
    cached: bool = False


@router.get("/scheme")
async def scheme_lookup(
    isin: str,
    _admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> SchemeLookupOut:
    """ISIN → UAT scheme-master record (scheme_bse_code + lumpsum/systematic mins).

    No proven server-side ISIN filter on master_scheme_list — try filter_param,
    then search; exact-match client-side either way. Cached 24h (UAT master is
    stable day-to-day)."""
    isin = isin.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{12}", isin):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid ISIN")
    cache_key = f"bse_uat:scheme:{isin}"
    if cached := await get_redis().get(cache_key):
        raw = cached.decode() if isinstance(cached, bytes) else cached
        return SchemeLookupOut(isin=isin, found=True, scheme=json.loads(raw), cached=True)

    token = await _cached_token()
    probes: list[dict[str, Any]] = [
        {"data": {"fields": ["ALL"], "count_only": False, "start": 0, "length": 10,
                  "filter_param": {"scheme_isin": [isin]}}},
        {"data": {"fields": ["ALL"], "count_only": False, "start": 0, "length": 10,
                  "search": {"value": isin}}},
    ]
    for probe in probes:
        res = await _bse_post("master_scheme_list", probe, token)
        if res["http_status"] != 200:
            continue
        rows = ((res["body"].get("data") or {}).get("lists")) or []
        match = next((r for r in rows if r.get("scheme_isin") == isin), None)
        if match:
            await get_redis().set(cache_key, json.dumps(match), ex=_SCHEME_CACHE_TTL)
            return SchemeLookupOut(isin=isin, found=True, scheme=match)
    return SchemeLookupOut(isin=isin, found=False)


class PlaceOrderRequest(BaseModel):
    scheme_code: str = Field(min_length=2, max_length=20)  # scheme_bse_code, e.g. "208-GR"
    amount: int = Field(gt=0, le=10_000_000)
    ucc: str = Field(default=_UCC_DEFAULT, min_length=3, max_length=20)
    contact_email: str | None = Field(default=None, max_length=120)
    contact_mobile: str | None = Field(default=None, max_length=15)


@router.post("/order")
async def place_order(
    body: PlaceOrderRequest,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> dict[str, Any]:
    """order_new lumpsum purchase on the UAT tenant (physical, fresh folio)."""
    token = await _cached_token()
    ref = str(int(time.time()))  # numeric-only string — the documented BSE requirement
    order: dict[str, Any] = {
        "type": "p",
        "mem_ord_ref_id": ref,
        "investor": {"ucc": body.ucc},
        "member": _MEMBER,
        "scheme": body.scheme_code,
        "amount": body.amount,
        "cur": "INR",
        "is_units": False,
        "all_units": False,
        "min_redeem_flag": False,
        "folio": "",
        "is_fresh": True,
        "phys_or_demat": "p",
        "kyc_passed": True,
        "is_nomination_opted": False,
    }
    if body.contact_email or body.contact_mobile:
        order["holder"] = [{
            "holder_rank": "1",
            "email": body.contact_email or "",
            "mobnum": body.contact_mobile or "",
        }]
        if body.contact_email:
            order["email"] = body.contact_email
    result = await _bse_post("order_new", {"data": {"orders": [order]}}, token)
    order_id = _extract_order_id(result["body"]) if result["http_status"] == 200 else None
    await record_admin_action(
        admin_id=str(admin.user_id),
        action="bse_uat_order_place",
        target_type="bse_order",
        target_id=order_id or ref,
        result="success" if order_id else f"failed_http_{result['http_status']}",
    )
    return {**result, "order_id": order_id, "mem_ord_ref_id": ref}


@router.post("/order/{order_id}/approve/start")
async def approve_start(
    order_id: int,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> dict[str, Any]:
    """Order-2FA kickoff: 2fa link → page jwt+lids → captcha → send OTP email.

    The OTP goes to the UCC's registered contact; the admin types it into
    /approve/verify. Demo tenant leaks the captcha answer (prod would not)."""
    token = await _cached_token()
    link_res = await _bse_post(
        "v2/get_2fa_link",
        {"data": [{"event": "verify_order_new", "order": str(order_id)}]},
        token,
    )
    page_url = _find_url(link_res["body"], "2fa_view_object")
    if link_res["http_status"] != 200 or not page_url:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"get_2fa_link failed (http {link_res['http_status']}): {str(link_res['body'])[:300]}",
        )
    if page_url.startswith("/"):
        page_url = _base_url().removesuffix("/api") + page_url

    page_status, html = await _bse_get_html(page_url)
    jwt, lids = _parse_2fa_page(html)
    if page_status != 200 or not jwt or not lids:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"2FA page parse failed (http {page_status}, jwt={'yes' if jwt else 'no'}, lids={len(lids)})",
        )

    cap = await _bse_post("generate_captcha", {})
    cap_data = (cap["body"].get("data") or {}) if isinstance(cap["body"], dict) else {}
    answer, cap_id = cap_data.get("captcha"), cap_data.get("captcha_id")
    if cap["http_status"] != 200 or answer is None or not cap_id:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "generate_captcha failed")
    val = await _bse_post("validate_captcha", {"data": {"captcha": answer, "captcha_id": cap_id}}, jwt)
    if val["http_status"] != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"validate_captcha failed: {str(val['body'])[:200]}")

    otp = await _bse_post("s2/2fa_send_otp", {}, jwt)
    if otp["http_status"] != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"2fa_send_otp failed: {str(otp['body'])[:200]}")

    stash = {"url": page_url, "jwt": jwt, "lids": lids, "captcha": answer}
    await get_redis().set(f"bse_uat:2fa:{order_id}", json.dumps(stash), ex=_TWOFA_STASH_TTL)
    await record_admin_action(
        admin_id=str(admin.user_id),
        action="bse_uat_order_2fa_start",
        target_type="bse_order",
        target_id=str(order_id),
        result="otp_sent",
    )
    return {"ok": True, "otp_sent": True, "lids": len(lids)}


class VerifyOtpRequest(BaseModel):
    otp: str = Field(min_length=4, max_length=8, pattern=r"^\d+$")


@router.post("/order/{order_id}/approve/verify")
async def approve_verify(
    order_id: int,
    body: VerifyOtpRequest,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> dict[str, Any]:
    """Submit the emailed OTP → s2/2fa_verify_link approve.

    Known trap (RCA'd 2026-07-12): the page jwt expires ~15 min → 509
    token_verification_failed. Recovery = fresh page GET + fresh captcha,
    REUSING the same OTP — done here automatically, once."""
    raw = await get_redis().get(f"bse_uat:2fa:{order_id}")
    if not raw:
        raise HTTPException(status.HTTP_409_CONFLICT, "No 2FA in progress — start approval first")
    stash = json.loads(raw.decode() if isinstance(raw, bytes) else raw)

    async def _verify(jwt: str, captcha: Any) -> dict[str, Any]:
        return await _bse_post(
            "s2/2fa_verify_link",
            {"data": {"lid": stash["lids"], "otp": body.otp, "captcha": captcha, "action": "approve"}},
            jwt,
        )

    result = await _verify(stash["jwt"], stash["captcha"])
    if result["http_status"] != 200 and "token" in str(result["body"]).lower():
        _status, html = await _bse_get_html(stash["url"])
        jwt, _lids = _parse_2fa_page(html)
        cap = await _bse_post("generate_captcha", {})
        cap_data = (cap["body"].get("data") or {}) if isinstance(cap["body"], dict) else {}
        if jwt and cap_data.get("captcha_id"):
            await _bse_post(
                "validate_captcha",
                {"data": {"captcha": cap_data.get("captcha"), "captcha_id": cap_data["captcha_id"]}},
                jwt,
            )
            result = await _verify(jwt, cap_data.get("captcha"))

    ok = result["http_status"] == 200
    if ok:
        await get_redis().delete(f"bse_uat:2fa:{order_id}")
    await record_admin_action(
        admin_id=str(admin.user_id),
        action="bse_uat_order_2fa_verify",
        target_type="bse_order",
        target_id=str(order_id),
        result="success" if ok else f"failed_http_{result['http_status']}",
    )
    return {**result, "approved": ok}


@router.get("/order/{order_id}/pg-link")
async def pg_link(
    order_id: int,
    _admin: Annotated[UserContext, Depends(RequireAdmin())],
    ucc: str = _UCC_DEFAULT,
) -> dict[str, Any]:
    """Hosted PG page link (payee = ICCL — money never routes through us).

    send_payment_info is deliberately NOT used: a plain MFD member is
    not_allowed for the member-hosted PG flow, and must never be the payee."""
    token = await _cached_token()
    result = await _bse_post(
        "get_exchpg_service",
        {
            "data": {
                "mem_details": {"euin": "", "euin_flag": False, "sub_br_code": "", "sub_br_arn": "", "partner_id": ""},
                "investor": {"ucc": ucc},
                "order_ids": [order_id],
                "requested_method": "exch_pg_page",
                "payment_mode": ["upi", "netbanking", "mandate"],
                "redirection_url": "https://dhanradar.com/mf/portfolio",
            }
        },
        token,
    )
    link = _find_url(result["body"], "pg_view_object")
    if link and link.startswith("/"):
        link = _base_url().removesuffix("/api") + link
    return {**result, "pg_link": link}
