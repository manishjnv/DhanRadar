"""
DhanRadar — Misc queue tasks.

Routed to the 'misc' queue via celery_app.conf.task_routes.
Used for housekeeping, notifications, and other low-priority work.
"""

from __future__ import annotations

from dhanradar.celery_app import celery_app


@celery_app.task(name="dhanradar.tasks.misc.send_notification")
def send_notification(user_id: str, message: str) -> str:
    """
    Stub: send a notification via Resend.
    TODO Phase 6: implement Resend API integration (NOT sendgrid).
    """
    return f"send_notification: stub — user={user_id!r} message={message!r} not yet implemented"
