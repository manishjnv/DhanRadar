"""
DhanRadar — Notification API + internal schemas (Phase 6).

`NotificationJob` is the internal queue payload (LPUSH'd to
`notifications:queue:{channel}` by `publish_notification`). The preferences
request/response models are the only public surface besides `/notifications/test`.

No-numeric / no-advisory (non-neg #1/#2) applies to the rendered MESSAGE, enforced
in `templates.py`; these schemas carry opaque `data` that a template maps to safe
copy — they never expose a score field.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# Channels deliverable at launch. whatsapp is Y2 (preference can be stored, but the
# drain does not deliver it).
Channel = Literal["telegram", "email"]
Priority = Literal["high", "normal"]

# HH:MM 24h quiet-hours bound (IST). Validated by pattern so a malformed value is a
# 422 at the API edge, never a delivery-time crash.
_HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"

# Telegram chat ids are signed integers (channels are negative). Reject garbage at
# write time so a stored value cannot only fail at delivery (defense-in-depth).
_TG_CHAT_ID = r"^-?\d{1,20}$"


class NotificationJob(BaseModel):
    """The queue payload. `priority="high"` bypasses quiet-hours (e.g. a security
    alert); `normal` defers during the user's quiet window."""

    user_id: str
    channel: Channel
    template_id: str
    data: dict = Field(default_factory=dict)
    priority: Priority = "normal"
    # Internal retry counter — incremented by the drain on transient failure; the
    # job is dropped (logged failed) once it exceeds the per-channel cap.
    attempts: int = 0


class PreferencesResponse(BaseModel):
    telegram_chat_id: str | None = None
    email_verified: bool = False
    whatsapp_number: str | None = None
    quiet_hours_start: str | None = None  # "HH:MM" IST, or null
    quiet_hours_end: str | None = None
    channels_enabled: dict[str, bool] = {}


class PreferencesUpdate(BaseModel):
    """Partial update — only provided fields are written. `None` for a nullable
    address clears it; omit a field to leave it unchanged."""

    telegram_chat_id: Annotated[str, Field(pattern=_TG_CHAT_ID)] | None = None
    whatsapp_number: str | None = Field(default=None, max_length=24)
    quiet_hours_start: Annotated[str, Field(pattern=_HHMM)] | None = None
    quiet_hours_end: Annotated[str, Field(pattern=_HHMM)] | None = None
    channels_enabled: dict[str, bool] | None = None

    # Sentinel-free partial update: the router distinguishes "field absent" via
    # model_fields_set, so a client must send the key to change it.
    model_config = {"extra": "forbid"}


class TestNotificationRequest(BaseModel):
    channel: Channel = "telegram"


class TestNotificationResponse(BaseModel):
    enqueued: bool
    channel: Channel
    detail: str
