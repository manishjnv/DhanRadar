"""
DhanRadar — BSE Star MF 2.0 webhook processing task (misc queue).

The webhook receiver persists the event and ACKs BSE synchronously; this task does
the actual (currently inert at UAT) processing off the stored row, so a slow or
failing processor never turns into a non-200 / BSE retry storm.

Routed to the 'misc' queue (NOT 'mood' — the 192 MB celery-mood worker OOMs on
extra load). Retries transient failures; on exhaustion the row is marked dead-letter.
"""

from __future__ import annotations

import asyncio
import logging

from celery.exceptions import MaxRetriesExceededError

from dhanradar.bse import service
from dhanradar.celery_app import celery_app
from dhanradar.db import task_session
from dhanradar.models.bse import STATUS_DEAD, STATUS_FAILED

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5


@celery_app.task(
    name="dhanradar.tasks.bse.process_webhook_event",
    bind=True,
    max_retries=_MAX_RETRIES,
    default_retry_delay=30,
)
def process_webhook_event(self, event_id: str) -> str:  # noqa: ANN001 (celery self)
    """Process one stored BSE webhook event. Idempotent; retries on transient error."""
    try:
        asyncio.run(_run(event_id))
        return f"processed:{event_id}"
    except Exception as exc:  # noqa: BLE001 — mark + decide retry vs dead-letter
        logger.warning("bse.process_webhook_event failed event=%s: %s", event_id, exc)
        asyncio.run(_mark_failure(event_id, str(exc), dead=False))
        # Let Celery decide retry-vs-exhausted (robust to retry-count semantics):
        # self.retry re-raises Retry to reschedule, or raises MaxRetriesExceededError
        # once exhausted — only THEN do we dead-letter the row.
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error("bse.process_webhook_event exhausted retries event=%s", event_id)
            asyncio.run(_mark_failure(event_id, str(exc), dead=True))
            return f"dead:{event_id}"


async def _run(event_id: str) -> None:
    async with task_session() as db:
        await service.process_event(db, event_id)


async def _mark_failure(event_id: str, error: str, *, dead: bool) -> None:
    """Record the failure on the inbox row (attempts++, status, last_error)."""
    from sqlalchemy import select

    from dhanradar.models.bse import BSEWebhookEvent

    async with task_session() as db:
        row = await db.scalar(select(BSEWebhookEvent).where(BSEWebhookEvent.id == event_id))
        if row is None:
            return
        row.attempts = (row.attempts or 0) + 1
        row.last_error = error[:2000]
        row.status = STATUS_DEAD if dead else STATUS_FAILED
        await db.commit()
