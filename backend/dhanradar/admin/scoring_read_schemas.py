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
    # Display-only enrichments (UUID → auth.users.email); None if unresolvable.
    created_by_email: str | None = None
    approved_by_email: str | None = None
    two_person_ok: bool
    activated: bool
    activated_at: datetime | None
    created_at: datetime | None


class CoverageInfo(BaseModel):
    # Rows in mf.mf_funds — one per plan-variant ISIN (Direct/Regular etc.).
    total_funds: int
    # Distinct schemes (plan variants collapsed, models/mf.py SCHEME_KEY) —
    # matches the AMC Coverage page and industry counting.
    total_schemes: int = 0
    # Distinct SCHEMES with a label in the latest nightly ranking run
    # (scheme-deduped like total_schemes, so the two tiles compare 1:1).
    labelled_funds: int = 0


class ScoringModelResponse(BaseModel):
    model_version: str
    activated: bool
    provisional: bool  # True when current version is NOT registry-activated
    methodology_url: str | None
    created_by: str | None
    # Display-only enrichment (UUID → auth.users.email); None if unresolvable.
    created_by_email: str | None = None
    axis_weights: dict[str, float]
    coverage: CoverageInfo
    registry_versions: list[EngineVersionRecord]
