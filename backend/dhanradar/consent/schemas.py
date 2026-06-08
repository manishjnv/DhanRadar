"""
Pydantic schemas for the B44 DPDP consent grant/revoke writer.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from dhanradar.deps import CONSENT_PURPOSES


class ConsentChangeRequest(BaseModel):
    """Request body for POST /consent/grant and POST /consent/revoke."""

    purposes: list[str]

    @field_validator("purposes")
    @classmethod
    def validate_purposes(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("purposes must contain at least one item")
        unknown = [p for p in v if p not in CONSENT_PURPOSES]
        if unknown:
            raise ValueError(
                f"Unknown consent purpose(s): {unknown}. "
                f"Valid purposes: {sorted(CONSENT_PURPOSES)}"
            )
        return v


class ConsentStateResponse(BaseModel):
    """Response for GET /consent, POST /consent/grant, POST /consent/revoke."""

    consents: dict[str, bool]
    consent_version: str
