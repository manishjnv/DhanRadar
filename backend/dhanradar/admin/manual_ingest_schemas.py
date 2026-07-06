"""
DhanRadar — Admin manual disclosure inbox Pydantic schemas.

Mirrors admin/ops_schemas.py's separation: kept out of the compliance/ops
schema files so this narrow upload/read surface stays independently reviewable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class UploadFileResult(BaseModel):
    filename: str
    file_id: str | None
    status: str  # 'pending' | 'duplicate'


class SkippedFileResult(BaseModel):
    """A zip member that was never intake_file()'d — the zip itself uploaded
    fine, but this member was ineligible (bad extension, oversized, nested
    zip, unreadable). Reason strings mirror expand_zip()'s skip reasons."""

    filename: str
    reason: str


class UploadBatchResponse(BaseModel):
    results: list[UploadFileResult]
    skipped: list[SkippedFileResult] = Field(default_factory=list)


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
