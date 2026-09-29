"""
DhanRadar — MF Utility (MFU) API evidence-ledger ORM model.

One table in the `mfu` schema: `mfu_api_log`. Every outbound MFU call (login +
service calls) writes one row here — success or failure — as the UAT evidence
trail, mirroring the role `bse.webhook_events` plays for the BSE rail. Request
and response JSON are scrubbed (see `dhanradar.mfu.client._scrub`) before being
stored: credentials and PII never land in this table.

Module isolation (non-neg #7): this table carries NO foreign key into any
other schema, and no FK from another schema points into `mfu` — MFU identifiers
are MFU's own, not our user/portfolio ids.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dhanradar.models.base import Base

_SCHEMA = {"schema": "mfu"}


class MfuApiLog(Base):
    """One MFU API call attempt (OAuth login or a service call), scrubbed."""

    __tablename__ = "mfu_api_log"
    __table_args__ = (
        Index("ix_mfu_api_log_created_at", "created_at"),
        _SCHEMA,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # MFU's uniqueId (login calls use a synthetic one) — never repeats, UNIQUE
    # doubles as a DB-level idempotency guard on the evidence ledger.
    unique_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    api_type: Mapped[str] = mapped_column(String(30), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resp_flag: Mapped[str | None] = mapped_column(String(1), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    request_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
