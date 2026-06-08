"""
Integration tests for the Mood Compass module.

Infrastructure contract (same as test_compliance / test_notifications):
  - async_client      — httpx.AsyncClient over ASGITransport(app); no lifespan.
  - db_session        — function-scoped AsyncSession; conftest truncates auth/billing.
  - fake_redis / patch_redis — fakeredis.aioredis.FakeRedis; flushed between tests.
  - patch_settings_keys — ephemeral RSA keypair; COOKIE_SECURE=False.
  - monkeypatch.setattr(dhanradar.db, "engine", db_session.bind) routes the
    service's own-session DB writes (compute_and_store, emit_published,
    record_served_label) to the test DB.
  - Seed rows committed via db_session BEFORE the service call so the service's
    separate AsyncSession can see them.

TRUNCATE note — same-connection pattern (see _truncate_compliance in test_compliance.py):
  The teardown fixture TRUNCATEs on db_session's OWN connection, not a second
  db_session.bind.begin() connection. A dangling SELECT on db_session holds an
  ACCESS SHARE lock; a TRUNCATE from a second connection waits for ACCESS EXCLUSIVE
  and deadlocks with CI hanging for 37+ minutes. Same-connection upgrades the lock
  in-transaction, no wait.

Covered:
  1. compute_and_store with greedy fetch → returns MoodResult(extreme_greed); exactly
     one DB row with the correct regime.
  2. GET /api/v1/market/mood → 200 with regime, confidence_band, disclosure, not_advice,
     disclaimer_version; response JSON must NOT contain 'mood_score' or 'confidence_score'
     keys (non-neg #2 — no numeric leaks).
  3. GET /api/v1/market/mood with no snapshot → structured 200 data_unavailable (B35 gap c).
  4. GET /api/v1/market/mood/history?days=10 → 200; ≥1 item with regime + snapshot_date.
  5. B26 audit linkage: after compute_and_store, AiRecommendationAudit has exactly one
     row with surface='mood', recommendation_type='mood_regime', label='extreme_greed'.
  6. Upsert idempotency: two calls for the same date → still exactly one DB row.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select, text

import dhanradar.db as _db_mod
from dhanradar.models.compliance import AiRecommendationAudit
from dhanradar.models.mood import MarketMood
from dhanradar.mood.compute import WEIGHTS

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Teardown: truncate mood + compliance tables between tests (conftest only
# handles auth/billing). Same-connection pattern — see module docstring.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _truncate_mood(db_session):
    """Truncate mood.market_mood and compliance.ai_recommendation_audit after each
    test using db_session's OWN connection to avoid the TRUNCATE deadlock (the
    compliance note above explains why a second connection would hang in CI)."""
    yield
    await db_session.rollback()  # drop any open read txn so TRUNCATE is clean
    await db_session.execute(
        text(
            "TRUNCATE TABLE mood.market_mood, "
            "compliance.ai_recommendation_audit "
            "RESTART IDENTITY CASCADE"
        )
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# 1. compute_and_store → MoodResult + DB row
# ---------------------------------------------------------------------------


async def test_compute_and_store_writes_row(db_session, monkeypatch, patch_redis):
    """compute_and_store with all inputs = 0.9 returns MoodResult(extreme_greed)
    and persists exactly one MarketMood row with regime='extreme_greed'."""
    from dhanradar.mood.service import compute_and_store

    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    result = await compute_and_store(
        snapshot_date=date.today(),
        snapshot_time=datetime.now(UTC),
        fetch=lambda: {k: 0.9 for k in WEIGHTS},
    )

    assert result is not None
    assert result.regime == "extreme_greed"

    # Flush service's commit into our view
    await db_session.commit()

    rows = (await db_session.scalars(select(MarketMood))).all()
    assert len(rows) == 1, f"Expected 1 MarketMood row, got {len(rows)}"

    row = rows[0]
    assert row.regime == "extreme_greed"
    assert row.mood_score is not None, "mood_score must be stored server-side"


# ---------------------------------------------------------------------------
# 2. GET /api/v1/market/mood → 200, no numeric leaks
# ---------------------------------------------------------------------------


async def test_get_mood_200_no_numeric_leak(
    async_client, db_session, monkeypatch, patch_redis
):
    """After a snapshot is stored, GET /market/mood returns 200 with the disclosure
    bundle and must NOT expose mood_score or confidence_score (non-neg #2)."""
    from dhanradar.mood.service import compute_and_store

    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    await compute_and_store(
        snapshot_date=date.today(),
        snapshot_time=datetime.now(UTC),
        fetch=lambda: {k: 0.9 for k in WEIGHTS},
    )
    await db_session.commit()

    r = await async_client.get("/api/v1/market/mood")
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["regime"] == "extreme_greed"
    assert "confidence_band" in body
    assert "disclosure" in body
    assert "not_advice" in body
    assert "disclaimer_version" in body

    # Non-neg #2: numeric fields must never reach the client.
    assert "mood_score" not in body, "mood_score must NOT appear in public response"
    assert "confidence_score" not in body, "confidence_score must NOT appear in public response"


# ---------------------------------------------------------------------------
# 3. GET /api/v1/market/mood with no snapshot → structured 200 data_unavailable (B35 gap c)
# ---------------------------------------------------------------------------


async def test_get_mood_no_snapshot_data_unavailable(async_client, patch_redis):
    """With no row in mood.market_mood, GET /market/mood must return a structured
    200 'data_unavailable' (NOT 404) so the anon magnet always renders something
    compliant — regime='data_unavailable', no numeric, disclosure bundle present."""
    r = await async_client.get("/api/v1/market/mood")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["regime"] == "data_unavailable"
    assert body["confidence_band"] == "insufficient_data"
    assert body["disclosure"] and body["not_advice"] and body["disclaimer_version"]
    raw = r.text
    assert "mood_score" not in raw and "confidence_score" not in raw


# ---------------------------------------------------------------------------
# 4. GET /api/v1/market/mood/history?days=10 → list with ≥1 item
# ---------------------------------------------------------------------------


async def test_get_mood_history(
    async_client, db_session, monkeypatch, patch_redis
):
    """After storing one snapshot, GET /market/mood/history?days=10 returns a list
    with ≥1 item, each containing 'regime' and 'snapshot_date'."""
    from dhanradar.mood.service import compute_and_store

    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    await compute_and_store(
        snapshot_date=date.today(),
        snapshot_time=datetime.now(UTC),
        fetch=lambda: {k: 0.9 for k in WEIGHTS},
    )
    await db_session.commit()

    r = await async_client.get("/api/v1/market/mood/history?days=10")
    assert r.status_code == 200, r.text

    items = r.json()
    assert isinstance(items, list)
    assert len(items) >= 1, "Expected at least one history item"

    item = items[0]
    assert "regime" in item, f"Missing 'regime' in history item: {item}"
    assert "snapshot_date" in item, f"Missing 'snapshot_date' in history item: {item}"


# ---------------------------------------------------------------------------
# 5. B26 audit linkage
# ---------------------------------------------------------------------------


async def test_compute_and_store_writes_audit_row(db_session, monkeypatch, patch_redis):
    """compute_and_store must emit a B26 AiRecommendationAudit row with
    surface='mood', recommendation_type='mood_regime', label='extreme_greed'."""
    from dhanradar.mood.service import compute_and_store

    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    await compute_and_store(
        snapshot_date=date.today(),
        snapshot_time=datetime.now(UTC),
        fetch=lambda: {k: 0.9 for k in WEIGHTS},
    )
    await db_session.commit()

    audit_rows = (await db_session.scalars(select(AiRecommendationAudit))).all()
    assert len(audit_rows) == 1, f"Expected 1 audit row, got {len(audit_rows)}"

    row = audit_rows[0]
    assert row.surface == "mood", f"Expected surface='mood', got {row.surface!r}"
    assert row.recommendation_type == "mood_regime", (
        f"Expected recommendation_type='mood_regime', got {row.recommendation_type!r}"
    )
    assert row.label == "extreme_greed", (
        f"Expected label='extreme_greed', got {row.label!r}"
    )


# ---------------------------------------------------------------------------
# 6. Upsert idempotency — same date, two calls → one row
# ---------------------------------------------------------------------------


async def test_compute_and_store_upsert_idempotency(db_session, monkeypatch, patch_redis):
    """Calling compute_and_store twice for the SAME snapshot_date with different
    fetch values must result in exactly ONE MarketMood row (on_conflict_do_update)."""
    from dhanradar.mood.service import compute_and_store

    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    today = date.today()
    now = datetime.now(UTC)

    # First call: all 0.9 → extreme_greed
    await compute_and_store(
        snapshot_date=today,
        snapshot_time=now,
        fetch=lambda: {k: 0.9 for k in WEIGHTS},
    )
    await db_session.commit()

    # Second call: all 0.1 → extreme_fear — same date, different data
    await compute_and_store(
        snapshot_date=today,
        snapshot_time=now,
        fetch=lambda: {k: 0.1 for k in WEIGHTS},
    )
    await db_session.commit()

    rows = (await db_session.scalars(select(MarketMood))).all()
    assert len(rows) == 1, f"Expected 1 row after upsert, got {len(rows)}"
    # The upserted row must reflect the second call's data.
    assert rows[0].regime == "extreme_fear", (
        f"Expected upserted regime='extreme_fear', got {rows[0].regime!r}"
    )
