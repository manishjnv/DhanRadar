"""DhanRadar — Compliance Audit API schemas (architecture Global §4)."""

from __future__ import annotations

from pydantic import BaseModel


class DisclaimerResponse(BaseModel):
    type: str
    version: str
    content: str
