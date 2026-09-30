"""
DhanRadar — Admin "Account deletions" console Pydantic schemas.

Separate from users_schemas.py so this read-only console surface never widens
the users load-bearing contract. Mirrors the ops_schemas.py separation pattern.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PendingDeletion(BaseModel):
    user_id: str
    email: str
    requested_at: datetime
    earliest_erase_at: datetime
    erase_by: datetime
    status: Literal["waiting", "ready", "overdue"]


class RecentErasure(BaseModel):
    erased_at: datetime
    # Parsed from audit.admin_actions.result ("erased:<N>_rows"); null if the
    # result string doesn't match the expected shape (malformed/legacy row).
    rows_removed: int | None
    erased_by: str


class RetentionRow(BaseModel):
    label: str
    keep_days: int


class DeletionsPolicy(BaseModel):
    erase_wait_days: int
    erase_due_days: int
    retention: list[RetentionRow]


class RetentionJobStatus(BaseModel):
    last_run_at: str | None
    result: str | None


class AdminDeletionsResponse(BaseModel):
    pending: list[PendingDeletion]
    recent_erasures: list[RecentErasure]
    policy: DeletionsPolicy
    retention_job: RetentionJobStatus | None
