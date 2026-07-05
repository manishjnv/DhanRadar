"""
Integration tests for enrichment item 4 — the daily mood-regime-history snapshot.

Infrastructure contract (same as test_mood.py):
  - db_session / patch_redis / fake_redis — see tests/conftest.py.
  - monkeypatch.setattr(dhanradar.db, "engine", db_session.bind) mirrors the
    existing mood integration-test convention.

`mood_history_snapshot` (dhanradar/tasks/mood.py) is a PURE Redis cache consumer:
it reads the already-published `mood:latest` key and writes ONE
`mood.mood_regime_history` row. It must NEVER live-fetch and must fail closed
(log + no row) when the cache is cold, unparseable, or missing a regime.

Covered:
  1. Warm cache → exactly one row, with the cached regime + component readings.
  2. Idempotency — two runs same day → still exactly one row (second wins).
  3. Cold cache (key absent) → zero rows written.
  4. get_regime_series → ordered [{date, regime}] list for a date range.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select, text

import dhanradar.db as _db_mod
from dhanradar.models.mood import MoodRegimeHistory
from dhanradar.mood import service
from dhanradar.tasks.mood import _mood_history_snapshot_async

pytestmark = pytest.mark.integration

# The code under test (_mood_history_snapshot_async, dhanradar/tasks/mood.py:206)
# deliberately computes "today" as datetime.now(IST).date() -- the market's own
# trading day, never trusting a possibly-stale cached snapshot_date. A naive
# date.today() (system/UTC in CI) diverges from IST for ~5.5h of every day
# (after 00:00 IST but before 00:00 UTC) -- this test must match the SAME IST
# clock the code uses, not a naive one (RCA: found failing consistently during
# that window, not a flake).
_IST = ZoneInfo("Asia/Kolkata")


def _ist_today() -> date:
    return datetime.now(_IST).date()


@pytest.fixture(autouse=True)
async def _truncate_mood_regime_history(db_session):
    """Truncate mood.mood_regime_history after each test (same-connection pattern
    — see test_mood.py module docstring for why a second connection would hang)."""
    yield
    await db_session.rollback()
    await db_session.execute(
        text("TRUNCATE TABLE mood.mood_regime_history RESTART IDENTITY CASCADE")
    )
    await db_session.commit()


def _cached_public_dict(regime: str) -> str:
    """A minimal stand-in for the JSON `_public_dict` writes to `mood:latest`."""
    return json.dumps(
        {
            "snapshot_date": _ist_today().isoformat(),
            "regime": regime,
            "confidence_band": "medium",
            "data_quality": "ok",
            "contributing_factors": [{"label": "Nifty Trend", "tier": "strong"}],
            "contradicting_factors": [{"label": "India VIX", "tier": "slight"}],
            "commentary": None,
        }
    )


# ---------------------------------------------------------------------------
# 1. Warm cache → one row
# ---------------------------------------------------------------------------


async def test_snapshot_writes_row_from_warm_cache(db_session, monkeypatch, patch_redis):
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)
    await patch_redis.set(service._LATEST_KEY, _cached_public_dict("greed"))

    result = await _mood_history_snapshot_async()
    assert "greed" in result

    await db_session.commit()
    rows = (await db_session.scalars(select(MoodRegimeHistory))).all()
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"

    row = rows[0]
    assert row.regime == "greed"
    assert row.snapshot_date == _ist_today()
    assert row.score_inputs["confidence_band"] == "medium"
    assert row.score_inputs["data_quality"] == "ok"
    assert row.score_inputs["contributing_factors"] == [{"label": "Nifty Trend", "tier": "strong"}]
    assert row.score_inputs["contradicting_factors"] == [{"label": "India VIX", "tier": "slight"}]
    assert row.as_of is not None


# ---------------------------------------------------------------------------
# 2. Idempotency — two runs same day → one row, second wins
# ---------------------------------------------------------------------------


async def test_snapshot_idempotent_same_day(db_session, monkeypatch, patch_redis):
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    await patch_redis.set(service._LATEST_KEY, _cached_public_dict("greed"))
    await _mood_history_snapshot_async()
    await db_session.commit()

    await patch_redis.set(service._LATEST_KEY, _cached_public_dict("fear"))
    await _mood_history_snapshot_async()
    await db_session.commit()

    rows = (await db_session.scalars(select(MoodRegimeHistory))).all()
    assert len(rows) == 1, f"Expected 1 row after upsert, got {len(rows)}"
    assert rows[0].regime == "fear"


# ---------------------------------------------------------------------------
# 3. Cold cache → no row (fail-closed)
# ---------------------------------------------------------------------------


async def test_snapshot_cold_cache_writes_no_row(db_session, monkeypatch, patch_redis):
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)
    # patch_redis is a fresh FakeRedis — mood:latest was never set.

    result = await _mood_history_snapshot_async()
    assert "skipped" in result

    rows = (await db_session.scalars(select(MoodRegimeHistory))).all()
    assert len(rows) == 0


# ---------------------------------------------------------------------------
# 4. get_regime_series — ordered [{date, regime}]
# ---------------------------------------------------------------------------


async def test_get_regime_series_returns_ordered_series(db_session):
    today = date.today()
    yesterday = today - timedelta(days=1)

    db_session.add_all(
        [
            MoodRegimeHistory(
                snapshot_date=yesterday,
                regime="fear",
                score_inputs={},
                as_of=datetime.now(UTC),
            ),
            MoodRegimeHistory(
                snapshot_date=today,
                regime="greed",
                score_inputs={},
                as_of=datetime.now(UTC),
            ),
        ]
    )
    await db_session.commit()

    series = await service.get_regime_series(db_session, yesterday, today)

    assert series == [
        {"date": yesterday.isoformat(), "regime": "fear"},
        {"date": today.isoformat(), "regime": "greed"},
    ]
