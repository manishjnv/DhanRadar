"""
DhanRadar — Admin manual disclosure inbox Pydantic schemas.

Mirrors admin/ops_schemas.py's separation: kept out of the compliance/ops
schema files so this narrow upload/read surface stays independently reviewable.
"""

from __future__ import annotations

from pydantic import BaseModel


class UploadFileResult(BaseModel):
    filename: str
    file_id: str | None
    status: str  # 'pending' | 'duplicate'


class UploadBatchResponse(BaseModel):
    results: list[UploadFileResult]


class ManualIngestFileRow(BaseModel):
    id: str
    original_filename: str
    channel: str
    status: str
    amc_detected: str | None
    period_detected: str | None  # ISO date (YYYY-MM-DD), first-of-month
    rows_ingested: int | None
    error: str | None
    received_at: str
    parsed_at: str | None
