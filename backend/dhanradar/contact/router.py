"""
DhanRadar — public Contact-Us enquiry router.

  POST /api/v1/contact   — no auth required (works signed in or out).

Abuse controls (this is a PUBLIC unauthenticated endpoint that sends email):
  - RateLimit 3 req / 600s per IP (CF-Connecting-IP, same limiter as auth routes).
  - Honeypot `website` field: non-empty -> silently return the same 202 without
    sending (logged as contact.honeypot, no PII).
  - We NEVER email the submitter — only SUPPORT_EMAIL, with the submitter's
    address set as reply-to. Auto-acknowledging would let anyone make us email
    an arbitrary stranger.
  - Nothing is written to the DB.
"""

from __future__ import annotations

import html
import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from dhanradar.config import settings
from dhanradar.contact.schemas import TOPIC_LABELS, ContactRequest, ContactResponse
from dhanradar.deps import UserContext, current_user_or_anonymous
from dhanradar.errors import get_request_id
from dhanradar.notifications.channels import deliver_email, email_configured
from dhanradar.ratelimit import RateLimit
from dhanradar.redis_client import get_redis

router = APIRouter(prefix="/contact", tags=["contact"])
logger = logging.getLogger(__name__)

_rl = RateLimit(max_requests=3, window_seconds=600)

_SUBJECT_MAX = 80
# ponytail: site-wide daily cap. Enquiries share the email provider's daily quota with
# login-code emails; a many-IP spam run must never exhaust it. Raise if real volume grows.
_DAILY_CAP = 50


async def _within_daily_cap() -> bool:
    redis = get_redis()
    key = f"contact:daily:{datetime.now(UTC):%Y%m%d}"
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, 2 * 86400)
    return n <= _DAILY_CAP


def _one_line(v: str, max_len: int) -> str:
    """Collapse to a single line and truncate — used only for the subject header,
    never for the escaped email body."""
    v = " ".join(v.split())
    return v[:max_len]


def _build_email(body: ContactRequest, *, request_id: str, signed_in: bool) -> tuple[str, str, str]:
    """Return (subject, html_body, text_body). All user values are html.escape'd
    before interpolation into the HTML body."""
    topic_label = TOPIC_LABELS[body.topic]
    safe_name_line = _one_line(body.name, _SUBJECT_MAX)
    subject = _one_line(f"DhanRadar enquiry: {topic_label} from {safe_name_line}", _SUBJECT_MAX)

    esc_name = html.escape(body.name)
    esc_email = html.escape(body.email)
    esc_topic = html.escape(topic_label)
    esc_message_html = html.escape(body.message).replace("\n", "<br>")
    when = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    esc_rid = html.escape(request_id)
    html_body = (
        f"<p><strong>Topic:</strong> {esc_topic}</p>"
        f"<p><strong>Name:</strong> {esc_name}</p>"
        f"<p><strong>Email:</strong> {esc_email}</p>"
        f"<p><strong>Time:</strong> {when}</p>"
        f"<p><strong>Signed in:</strong> {signed_in}</p>"
        f"<p><strong>Request ID:</strong> {esc_rid}</p>"
        f"<p><strong>Message:</strong><br>{esc_message_html}</p>"
    )

    text_body = (
        f"Topic: {topic_label}\n"
        f"Name: {body.name}\n"
        f"Email: {body.email}\n"
        f"Time: {when}\n"
        f"Signed in: {signed_in}\n"
        f"Request ID: {request_id}\n\n"
        f"Message:\n{body.message}\n"
    )

    return subject, html_body, text_body


@router.post("", response_model=ContactResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_contact(
    body: ContactRequest,
    request: Request,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    _rl: Annotated[None, Depends(_rl)] = None,
) -> ContactResponse:
    # Honeypot: real users never see/fill `website`. Bots that fill every field
    # get the same success response with no email sent (no PII in the log).
    if body.website:
        logger.info("contact.honeypot topic=%s", body.topic)
        return ContactResponse()

    if not await _within_daily_cap():
        logger.warning("contact.daily_cap topic=%s", body.topic)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="contact_unavailable")

    request_id = get_request_id(request)
    subject, html_body, text_body = _build_email(
        body, request_id=request_id, signed_in=not user.is_anonymous
    )

    if not email_configured():
        logger.warning("contact.unavailable topic=%s reason=not_configured", body.topic)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="contact_unavailable")

    result = await deliver_email(
        to=settings.SUPPORT_EMAIL,
        subject=subject,
        html=html_body,
        text=text_body,
        reply_to=body.email,
    )
    if not result.ok:
        logger.warning("contact.delivery_failed topic=%s code=%s", body.topic, result.code)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="contact_unavailable")

    logger.info("contact.sent topic=%s ok=true", body.topic)
    return ContactResponse()
