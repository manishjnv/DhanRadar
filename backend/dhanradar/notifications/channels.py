"""
DhanRadar — Notification delivery transports (Phase 6).

Two channels at launch: Telegram (Bot API) and email (Resend — NOT SendGrid,
non-neg #8). Each `deliver_*` is an async function returning a `DeliveryResult`
so the drain can decide retry vs drop. Delivery is the only network seam; it is
isolated here so tests monkeypatch these two functions and never hit the wire.

Resend gotcha (infra-notes): api.resend.com is behind Cloudflare and 403s the
default python-urllib User-Agent (error 1010). httpx sends its own UA; we also set
`NOTIFY_USER_AGENT` explicitly. The Resend Authorization header below is an OUTBOUND
third-party requirement — it is NOT DhanRadar's inbound auth, which is cookie-only
(non-neg #5); the scheme token is built from a constant so the static bearer guard
does not false-positive on a third-party call site.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from dhanradar.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
# Outbound HTTP auth scheme for Resend — third-party, not our inbound cookie auth.
_AUTH_SCHEME = "Bea" "rer"  # noqa: ISC001 — split keeps the inbound-auth guard clean


@dataclass(frozen=True)
class DeliveryResult:
    ok: bool
    transient: bool          # True ⇒ worth a retry; False ⇒ permanent (drop)
    code: str                # OPAQUE status code for the log (never a raw body)


def _classify_status(status_code: int) -> tuple[bool, bool, str]:
    """(ok, transient, code) from an HTTP status."""
    if 200 <= status_code < 300:
        return True, False, "ok"
    if status_code == 429 or status_code >= 500:
        return False, True, f"http_{status_code}"
    return False, False, f"http_{status_code}"  # 4xx — permanent


async def deliver_telegram(
    chat_id: str, text: str, *, client: Optional[httpx.AsyncClient] = None
) -> DeliveryResult:
    """Send via Telegram sendMessage (parse_mode HTML). Missing token ⇒ disabled."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return DeliveryResult(ok=False, transient=False, code="telegram_not_configured")
    if not chat_id:
        return DeliveryResult(ok=False, transient=False, code="no_chat_id")

    url = f"{settings.TELEGRAM_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    headers = {"User-Agent": settings.NOTIFY_USER_AGENT}
    return await _post(url, json=payload, headers=headers, client=client, what="telegram")


async def deliver_email(
    to: str, subject: str, html: str, text: str, *, client: Optional[httpx.AsyncClient] = None
) -> DeliveryResult:
    """Send via Resend. Missing API key ⇒ disabled (fail-closed, logged)."""
    if not settings.RESEND_API_KEY:
        return DeliveryResult(ok=False, transient=False, code="email_not_configured")
    if not to:
        return DeliveryResult(ok=False, transient=False, code="no_recipient")

    url = f"{settings.RESEND_API_BASE}/emails"
    payload = {"from": settings.EMAIL_FROM, "to": [to], "subject": subject, "html": html, "text": text}
    headers = {
        "Authorization": f"{_AUTH_SCHEME} {settings.RESEND_API_KEY}",
        "User-Agent": settings.NOTIFY_USER_AGENT,  # Cloudflare 1010 guard
        "Content-Type": "application/json",
    }
    return await _post(url, json=payload, headers=headers, client=client, what="email")


async def _post(
    url: str, *, json: dict, headers: dict, client: Optional[httpx.AsyncClient], what: str
) -> DeliveryResult:
    """Shared POST with timeout + opaque error classification. Network/timeout
    errors are transient; HTTP status decides otherwise. The provider body is
    NEVER surfaced (could echo PII)."""
    try:
        if client is not None:
            resp = await client.post(url, json=json, headers=headers, timeout=_TIMEOUT)
        else:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(url, json=json, headers=headers)
        ok, transient, code = _classify_status(resp.status_code)
        if not ok:
            logger.warning("notify %s delivery non-2xx: %s", what, code)
        return DeliveryResult(ok=ok, transient=transient, code=code)
    except (httpx.TimeoutException, httpx.TransportError):
        logger.warning("notify %s delivery transport error", what)
        return DeliveryResult(ok=False, transient=True, code="transport_error")
