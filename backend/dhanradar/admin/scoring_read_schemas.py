"""
DhanRadar — Admin Phase 3: Scoring read-only response schemas.

TIER-C LOAD-BEARING: these schemas gate the scoring model read surface.
Requires Opus line-by-line diff review before merge.

No mutation schemas live here — this file is strictly read-only response types.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class EngineVersionRecord(BaseModel):
    model_version: str
    created_by: str | None
    approved_by: str | None
    two_person_ok: bool
    activated: bool
    activated_at: datetime | None
    created_at: datetime | None


class CoverageInfo(BaseModel):
    total_funds: int


class ScoringModelResponse(BaseModel):
    model_version: str
    activated: bool
    provisional: bool  # True when current version is NOT registry-activated
    methodology_url: str | None
    created_by: str | None
    axis_weights: dict[str, float]
    coverage: CoverageInfo
    registry_versions: list[EngineVersionRecord]
