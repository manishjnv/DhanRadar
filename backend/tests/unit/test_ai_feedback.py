"""Unit tests for AI output feedback service functions (no DB)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest


def test_feedback_router_post_returns_201():
    """Smoke test: FeedbackRequest schema accepts valid input."""
    from dhanradar.ai_feedback.router import FeedbackRequest

    req = FeedbackRequest(audit_id="00000000-0000-0000-0000-000000000001", helpful=True)
    assert req.helpful is True
    assert req.feedback_text is None


def test_feedback_request_rejects_long_text():
    """feedback_text max_length=500 enforced."""
    from pydantic import ValidationError

    from dhanradar.ai_feedback.router import FeedbackRequest

    with pytest.raises(ValidationError):
        FeedbackRequest(
            audit_id="00000000-0000-0000-0000-000000000001",
            helpful=True,
            feedback_text="x" * 501,
        )


def test_feedback_summary_returns_zero_when_empty():
    """feedback_summary returns zeroed dict when no rows exist."""
    from dhanradar.compliance.service import feedback_summary

    async def fake_scalar(_q):
        return 0

    async def fake_scalars(_q):
        m = MagicMock()
        m.all.return_value = []
        return m

    db = MagicMock()
    db.scalar = fake_scalar
    db.scalars = fake_scalars

    result = asyncio.run(feedback_summary(db, days=30))
    assert result["total"] == 0
    assert result["helpful_pct"] is None
    assert result["recent"] == []
