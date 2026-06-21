"""
Unit tests for MoodPublic.snapshot_at (feat/mood-relative-time).

Verifies:
  - snapshot_at is an ISO 8601 tz-aware string when snapshot_time is present
  - snapshot_at is None when snapshot_time is absent
  - unavailable_public() emits snapshot_at=None (no crash)
  - get_latest() propagates snapshot_time correctly

All tests are unit-level: no DB, no Redis, no network.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    *,
    snapshot_time: datetime | None = None,
    mood_score: float = 55.0,
) -> MagicMock:
    """Build a fake MarketMood ORM row with all fields service.py reads."""
    row = MagicMock()
    row.snapshot_date = date(2026, 6, 21)
    row.snapshot_time = snapshot_time
    row.mood_score = mood_score
    row.regime = "neutral"
    row.confidence_band = "medium"
    row.data_quality = "ok"
    row.contributing_factors = ["nifty_trend"]
    row.contradicting_factors = []
    row.ai_commentary = None
    return row


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, rows):
        self._rows = rows

    async def scalar(self, _stmt):
        return self._rows[0] if self._rows else None

    async def scalars(self, _stmt):
        return _FakeScalars(self._rows)


# ---------------------------------------------------------------------------
# 1. MoodPublic schema — field presence
# ---------------------------------------------------------------------------


def test_mood_public_snapshot_at_field_exists():
    """MoodPublic must accept a snapshot_at field."""
    from dhanradar.mood.schemas import MoodPublic
    from dhanradar.scoring.engine.schemas import (
        DISCLAIMER_VERSION,
        DISCLOSURE_BUNDLE,
        NOT_ADVICE,
    )

    now = datetime(2026, 6, 21, 9, 0, 0, tzinfo=UTC)
    pub = MoodPublic(
        snapshot_date="2026-06-21",
        snapshot_at=now.isoformat(),
        regime="neutral",
        confidence_band="medium",
        data_quality="ok",
        disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE,
        disclaimer_version=DISCLAIMER_VERSION,
    )
    assert pub.snapshot_at == now.isoformat()
    # Must be an ISO string with timezone info
    assert "+" in pub.snapshot_at or pub.snapshot_at.endswith("Z") or "+00:00" in pub.snapshot_at


def test_mood_public_snapshot_at_none_by_default():
    """snapshot_at defaults to None (backward compat)."""
    from dhanradar.mood.schemas import MoodPublic
    from dhanradar.scoring.engine.schemas import (
        DISCLAIMER_VERSION,
        DISCLOSURE_BUNDLE,
        NOT_ADVICE,
    )

    pub = MoodPublic(
        snapshot_date="2026-06-21",
        regime="neutral",
        confidence_band="medium",
        data_quality="ok",
        disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE,
        disclaimer_version=DISCLAIMER_VERSION,
    )
    assert pub.snapshot_at is None


# ---------------------------------------------------------------------------
# 2. unavailable_public() — snapshot_at must be None, no crash
# ---------------------------------------------------------------------------


def test_unavailable_public_snapshot_at_is_none():
    """unavailable_public() must set snapshot_at=None without raising."""
    from dhanradar.mood.service import unavailable_public

    pub = unavailable_public()
    assert pub.snapshot_at is None


# ---------------------------------------------------------------------------
# 3. get_latest() — snapshot_time propagated as ISO string
# ---------------------------------------------------------------------------


async def test_get_latest_propagates_snapshot_time():
    """get_latest() must set snapshot_at to the ISO string of snapshot_time."""
    from dhanradar.mood import service

    known_dt = datetime(2026, 6, 21, 9, 15, 0, tzinfo=UTC)
    row = _make_row(snapshot_time=known_dt)
    db = _FakeDb([row, _make_row(snapshot_time=known_dt, mood_score=50.0)])

    pub = await service.get_latest(db)

    assert pub is not None
    assert pub.snapshot_at == known_dt.isoformat(), (
        f"Expected {known_dt.isoformat()!r}, got {pub.snapshot_at!r}"
    )
    # Sanity: must contain UTC offset info
    assert "+00:00" in pub.snapshot_at or pub.snapshot_at.endswith("Z")


async def test_get_latest_snapshot_at_none_when_no_snapshot_time():
    """If snapshot_time is None on the row, snapshot_at must be None (not crash)."""
    from dhanradar.mood import service

    row = _make_row(snapshot_time=None)
    db = _FakeDb([row])

    pub = await service.get_latest(db)

    assert pub is not None
    assert pub.snapshot_at is None


async def test_get_latest_returns_none_when_no_rows():
    """get_latest() returns None for an empty table (existing behaviour, unbroken)."""
    from dhanradar.mood import service

    db = _FakeDb([])
    pub = await service.get_latest(db)
    assert pub is None


# ---------------------------------------------------------------------------
# 4. snapshot_at does not expose numeric scores
# ---------------------------------------------------------------------------


async def test_snapshot_at_does_not_leak_numeric_score():
    """snapshot_at value must not contain the raw mood_score (non-neg #2)."""
    from dhanradar.mood import service

    known_dt = datetime(2026, 6, 21, 8, 30, 0, tzinfo=UTC)
    row = _make_row(snapshot_time=known_dt, mood_score=72.5)
    db = _FakeDb([row, _make_row(snapshot_time=known_dt, mood_score=68.0)])

    pub = await service.get_latest(db)
    assert pub is not None
    dumped = pub.model_dump()
    assert "mood_score" not in dumped
    assert "confidence_score" not in dumped
    # snapshot_at should be a date/time string, NOT the score
    assert "72.5" not in (pub.snapshot_at or "")
