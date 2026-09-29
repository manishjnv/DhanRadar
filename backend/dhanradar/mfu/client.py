"""
DhanRadar — MF Utility (MFU) HTTP client: OAuth login + request envelope.

Phase 0 foundation only — no order calls yet. Every attempt (login or a
service call) writes one row to `mfu.mfu_api_log` (the UAT evidence ledger),
scrubbed of credentials/PII, success or failure.

UAT-only (mirrors bse_uat_router's demo-tenant-only rail): `base_url()` refuses
to run unless `settings.MFU_UAT_ENABLED` is set AND the configured base URL is
exactly `https://test.mfuonline.com`.

ONE login attempt per call — no retry loop, MFU's lockout policy on repeated
bad logins is unknown. A failed login arms a 5-minute cooldown so a caller
can't hammer the endpoint.
"""

from __future__ import annotations

import json
import re
import secrets
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.config import settings
from dhanradar.mfu.crypto import decrypt, encrypt
from dhanradar.redis_client import get_redis

_IST = ZoneInfo("Asia/Kolkata")

_TOKEN_KEY = "mfu_uat:access_token"
_COOLDOWN_KEY = "mfu_uat:login_cooldown"
_COOLDOWN_S = 300
_TIMEOUT = 30.0

# BSE's WAF blocks python UAs with an HTML page — MFU's may too; a real
# browser UA is the same cheap defence used by bse_uat_router (own literal
# copy — the mfu module must not import from dhanradar.bse/.admin.bse_uat_router).
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_SCRUB_KEYS = {
    "pan",
    "panno",
    "invpan",
    "accno",
    "accountno",
    "invaccno",
    "bankaccno",
    "mobile",
    "mobileno",
    "email",
    "emailid",
    "clientuser",
    "clientpwd",
    "data",
    "access_token",
}
_PAN_RE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")


class MfuError(Exception):
    """Any MFU login/call failure — carries MFU's own error_code/error_msg."""

    def __init__(self, http_status: int | None, error_code: str, error_msg: str) -> None:
        self.http_status = http_status
        self.error_code = error_code
        self.error_msg = error_msg
        super().__init__(f"MFU error {error_code}: {error_msg} (http={http_status})")


def _none_to_empty(obj: Any) -> Any:
    """Recursively replace None with "" — MFU's JSON forbids nulls (absent
    values must be empty strings with the key present)."""
    if obj is None:
        return ""
    if isinstance(obj, dict):
        return {k: _none_to_empty(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_none_to_empty(v) for v in obj]
    return obj


def _scrub(obj: Any) -> Any:
    """Redact credential/PII-shaped values before writing to the api-log table."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k.lower() in _SCRUB_KEYS:
                out[k] = "***"
            else:
                out[k] = _scrub(v)
        return out
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    if isinstance(obj, str):
        return _PAN_RE.sub("*****", obj)
    return obj


def new_unique_id() -> str:
    """A uniqueId that never repeats, <=50 chars (timestamp + random suffix)."""
    return datetime.now(_IST).strftime("%y%m%d%H%M%S") + secrets.token_hex(6)


def base_url() -> str:
    if not settings.MFU_UAT_ENABLED:
        raise MfuError(None, "DISABLED", "MFU UAT is not enabled (MFU_UAT_ENABLED=False)")
    if not all(
        [
            settings.MFU_ENTITY_ID,
            settings.MFU_LOGIN_USER,
            settings.MFU_LOGIN_PASSWORD,
            settings.MFU_AES_KEY,
            settings.MFU_AES_IV,
        ]
    ):
        raise MfuError(None, "NOT_CONFIGURED", "MFU credentials/keys are not fully configured")
    base = settings.MFU_API_BASE_URL_UAT.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or parsed.hostname != "test.mfuonline.com":
        raise MfuError(None, "NOT_UAT_HOST", f"MFU base URL is not the UAT host: {base}")
    return base


def build_envelope(api_type: str, body: dict[str, Any]) -> dict[str, Any]:
    """Pure: build the reqHeader/reqBody envelope for a service call."""
    clean_body = _none_to_empty(body)
    unique_id = new_unique_id()
    req_header = {
        "entityId": settings.MFU_ENTITY_ID,
        "version": "1.00",
        "reqTS": datetime.now(_IST).strftime("%Y-%m-%d %H:%M:%S"),
        "apiType": api_type,
        "uniqueId": unique_id,
    }
    data = encrypt(
        json.dumps(clean_body, separators=(",", ":")),
        settings.MFU_AES_KEY,
        settings.MFU_AES_IV,
    )
    return {"reqHeader": req_header, "reqBody": {"data": data}}


def _parse_error(status_code: int, payload: Any) -> tuple[str, str]:
    """Plaintext error body — either {"errorRespData": {...}} or a top-level
    {"errorCode": ..., "errorMsg": ...} (both shapes documented)."""
    if isinstance(payload, dict):
        inner = payload.get("errorRespData")
        if isinstance(inner, dict):
            return str(inner.get("errorCode", "")), str(inner.get("errorMsg", ""))
        if "errorCode" in payload or "errorMsg" in payload:
            return str(payload.get("errorCode", "")), str(payload.get("errorMsg", ""))
    return "HTTP_ERROR", f"unexpected error body at http {status_code}"


async def _write_log(
    db: AsyncSession,
    *,
    unique_id: str,
    api_type: str,
    http_status: int | None,
    resp_flag: str | None,
    error_code: str | None,
    error_msg: str | None,
    latency_ms: int,
    request_json: Any,
    response_json: Any,
) -> None:
    from dhanradar.models.mfu import MfuApiLog

    db.add(
        MfuApiLog(
            unique_id=unique_id,
            api_type=api_type,
            http_status=http_status,
            resp_flag=resp_flag,
            error_code=error_code,
            error_msg=error_msg,
            latency_ms=latency_ms,
            request_json=_scrub(request_json),
            response_json=_scrub(response_json),
        )
    )
    await db.commit()


async def login(db: AsyncSession) -> tuple[str, int]:
    """ONE login attempt. Returns (token, ttl_s). Caches the token in Redis."""
    redis = get_redis()
    if await redis.get(_COOLDOWN_KEY):
        raise MfuError(None, "COOLDOWN", "MFU login is in a post-failure cooldown")

    base = base_url()
    unique_id = new_unique_id()
    req_body = {
        "entityId": settings.MFU_ENTITY_ID,
        "clientUser": encrypt(settings.MFU_LOGIN_USER, settings.MFU_AES_KEY, settings.MFU_AES_IV),
        "clientPwd": encrypt(
            settings.MFU_LOGIN_PASSWORD, settings.MFU_AES_KEY, settings.MFU_AES_IV
        ),
    }
    logged_request = {
        "reqBody": {**req_body, "clientUser": "<encrypted>", "clientPwd": "<encrypted>"}
    }

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            res = await client.post(
                f"{base}/GetAccessTokenV1",
                json={"reqBody": req_body},
                headers={"Content-Type": "application/json", "User-Agent": _BROWSER_UA},
            )
        except httpx.HTTPError as exc:
            await redis.set(_COOLDOWN_KEY, "1", ex=_COOLDOWN_S)
            await _write_log(
                db,
                unique_id=unique_id,
                api_type="OAUTH-LOGIN",
                http_status=None,
                resp_flag=None,
                error_code="TRANSPORT_ERROR",
                error_msg=exc.__class__.__name__,
                latency_ms=0,
                request_json=logged_request,
                response_json=None,
            )
            raise MfuError(None, "TRANSPORT_ERROR", exc.__class__.__name__) from exc
    latency_ms = int((time.monotonic() - started) * 1000)

    try:
        payload = res.json()
    except ValueError:
        payload = {"raw": res.text[:500]}

    if res.status_code != 200 or "access_token" not in (
        payload if isinstance(payload, dict) else {}
    ):
        code, msg = _parse_error(res.status_code, payload)
        await redis.set(_COOLDOWN_KEY, "1", ex=_COOLDOWN_S)
        await _write_log(
            db,
            unique_id=unique_id,
            api_type="OAUTH-LOGIN",
            http_status=res.status_code,
            resp_flag=None,
            error_code=code,
            error_msg=msg,
            latency_ms=latency_ms,
            request_json=logged_request,
            response_json=payload,
        )
        raise MfuError(res.status_code, code, msg)

    token = payload["access_token"]
    try:
        expires_hours = int(payload.get("expires_in", 24))
    except (TypeError, ValueError):
        expires_hours = 24
    ttl_s = expires_hours * 3600 - 3600
    if ttl_s <= 0:
        ttl_s = 23 * 3600

    await redis.set(_TOKEN_KEY, token, ex=ttl_s)
    logged_response = {**payload, "access_token": "<redacted>"}
    await _write_log(
        db,
        unique_id=unique_id,
        api_type="OAUTH-LOGIN",
        http_status=res.status_code,
        resp_flag="S",
        error_code=None,
        error_msg=None,
        latency_ms=latency_ms,
        request_json=logged_request,
        response_json=logged_response,
    )
    return token, ttl_s


async def get_token(db: AsyncSession) -> str:
    """Cached token, or a fresh login."""
    cached = await get_redis().get(_TOKEN_KEY)
    if cached:
        return cached.decode() if isinstance(cached, bytes) else cached
    token, _ttl = await login(db)
    return token


# Token-invalid / token-expired MFU error codes — on either, evict the cached
# token so the NEXT call re-logins instead of reusing a dead token for up to
# 23h. No automatic retry of the call itself.
_TOKEN_DEAD_CODES = {"100006", "100007"}


async def call(db: AsyncSession, api_type: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    """Envelope, POST with a Bearer-authenticated request, decrypt respData, always log."""
    token = await get_token(db)
    envelope = build_envelope(api_type, body)
    unique_id = envelope["reqHeader"]["uniqueId"]
    # Evidence log carries the PLAINTEXT body (masked by _scrub), not the
    # ciphertext in envelope["reqBody"]["data"] — otherwise the UAT evidence
    # trail loses what we actually sent.
    logged_request = {"reqHeader": envelope["reqHeader"], "reqBody": _none_to_empty(body)}

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            res = await client.post(
                f"{base_url()}/{path.lstrip('/')}",
                json=envelope,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",  # nosec — outbound to MFU, not our session auth
                    "User-Agent": _BROWSER_UA,
                },
            )
        except httpx.HTTPError as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _write_log(
                db,
                unique_id=unique_id,
                api_type=api_type,
                http_status=None,
                resp_flag=None,
                error_code="TRANSPORT_ERROR",
                error_msg=exc.__class__.__name__,
                latency_ms=latency_ms,
                request_json=logged_request,
                response_json=None,
            )
            raise MfuError(None, "TRANSPORT_ERROR", exc.__class__.__name__) from exc
    latency_ms = int((time.monotonic() - started) * 1000)

    try:
        raw_payload = res.json()
    except ValueError:
        raw_payload = {"raw": res.text[:500]}

    if res.status_code != 200:
        code, msg = _parse_error(res.status_code, raw_payload)
        if code in _TOKEN_DEAD_CODES:
            await get_redis().delete(_TOKEN_KEY)
        await _write_log(
            db,
            unique_id=unique_id,
            api_type=api_type,
            http_status=res.status_code,
            resp_flag=None,
            error_code=code,
            error_msg=msg,
            latency_ms=latency_ms,
            request_json=logged_request,
            response_json=raw_payload,
        )
        raise MfuError(res.status_code, code, msg)

    resp_data_enc = raw_payload.get("respData") if isinstance(raw_payload, dict) else None
    if not resp_data_enc:
        await _write_log(
            db,
            unique_id=unique_id,
            api_type=api_type,
            http_status=res.status_code,
            resp_flag=None,
            error_code="NO_RESP_DATA",
            error_msg="response had no respData",
            latency_ms=latency_ms,
            request_json=logged_request,
            response_json=raw_payload,
        )
        raise MfuError(res.status_code, "NO_RESP_DATA", "response had no respData")

    try:
        decrypted = json.loads(decrypt(resp_data_enc, settings.MFU_AES_KEY, settings.MFU_AES_IV))
    except Exception as exc:
        # Exactly the failure class we're fighting with MFU's cipher-text
        # format (errorCode 1 / "decrypt the text") — it MUST land in the
        # evidence ledger, not escape as a raw exception with no log row.
        await _write_log(
            db,
            unique_id=unique_id,
            api_type=api_type,
            http_status=res.status_code,
            resp_flag=None,
            error_code="DECRYPT_ERROR",
            error_msg=exc.__class__.__name__,
            latency_ms=latency_ms,
            request_json=logged_request,
            response_json=raw_payload,
        )
        raise MfuError(res.status_code, "DECRYPT_ERROR", exc.__class__.__name__) from exc

    resp_header = decrypted.get("respHeader", {}) if isinstance(decrypted, dict) else {}
    resp_flag = resp_header.get("respFlag")

    if resp_flag == "F":
        code = str(resp_header.get("errorCode", ""))
        msg = str(resp_header.get("errorMsg", ""))
        if code in _TOKEN_DEAD_CODES:
            await get_redis().delete(_TOKEN_KEY)
        await _write_log(
            db,
            unique_id=unique_id,
            api_type=api_type,
            http_status=res.status_code,
            resp_flag="F",
            error_code=code,
            error_msg=msg,
            latency_ms=latency_ms,
            request_json=logged_request,
            response_json=decrypted,
        )
        raise MfuError(res.status_code, code, msg)

    await _write_log(
        db,
        unique_id=unique_id,
        api_type=api_type,
        http_status=res.status_code,
        resp_flag=resp_flag,
        error_code=None,
        error_msg=None,
        latency_ms=latency_ms,
        request_json=logged_request,
        response_json=decrypted,
    )
    return decrypted
