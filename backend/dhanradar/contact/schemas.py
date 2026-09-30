"""Pydantic schemas for POST /api/v1/contact."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

TopicLiteral = Literal["general", "account", "data_deletion", "feedback", "partnership", "other"]

# Machine value -> human label, used in the subject line and (optionally) the
# email body. Plain English only (SEBI non-neg #1 — no advisory verbs anywhere).
TOPIC_LABELS: dict[str, str] = {
    "general": "General question",
    "account": "My account",
    "data_deletion": "Delete my data",
    "feedback": "Feedback",
    "partnership": "Partnership",
    "other": "Other",
}


class ContactRequest(BaseModel):
    """Body for POST /contact. `extra='forbid'` rejects unknown fields (422)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    topic: TopicLiteral
    message: str = Field(min_length=10, max_length=3000)
    website: str = ""  # honeypot — real users never see/fill this field

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        if any(ord(c) < 32 or ord(c) == 127 for c in v):
            raise ValueError("name must not contain control characters")
        return v

    @field_validator("message")
    @classmethod
    def _clean_message(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("message must be at least 10 characters")
        return v


class ContactResponse(BaseModel):
    status: Literal["received"] = "received"
