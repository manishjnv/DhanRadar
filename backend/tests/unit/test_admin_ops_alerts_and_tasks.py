"""Unit tests for Task 1 (_derive_admin_alerts reuse in get_health) and
Task 2 (_next_run_at cron computation).

All tests are fully unit-level:
  - DB calls are mocked with AsyncMock; no live Postgres or broker.
  - SQLAlchemy select() is called with real model columns (model definitions
    do NOT require a DB connection); only the DB execution layer is mocked.
  - No celery broker connection is triggered — celery.schedules.crontab is
    a pure-Python cron parser with no network I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Task 2 — _next_run_at
# ---------------------------------------------------------------------------


def test_next_run_at_returns_future_iso_for_simple_cron():
    """_next_run_at({"hour": 23, "minute": 30}, "Asia/Kolkata") returns an ISO string
    that parses as a future datetime."""
    from dhanradar.admin.ops_router import _next_run_at

    result = _next_run_at({"hour": 23, "minute": 30}, "Asia/Kolkata")
    assert result is not None, "_next_run_at returned None for a valid cron"
    # Must parse as a datetime
    dt = datetime.fromisoformat(result)
    # Must be in the future (or at most a day away — we're computing 23:30 IST next run)
    now = datetime.now(dt.tzinfo)
    assert dt > now - timedelta(seconds=5), "next_run_at should be in the future"
    assert dt <= now + timedelta(hours=25), "next_run_at should be within 25h for a daily cron"


def test_next_run_at_returns_none_for_none_cron():
    """_next_run_at(None, ...) must return None without raising."""
    from dhanradar.admin.ops_router import _next_run_at

    assert _next_run_at(None, "Asia/Kolkata") is None


def test_next_run_at_returns_none_for_empty_cron():
    """_next_run_at({}, ...) must return None (empty dict — falsy)."""
    from dhanradar.admin.ops_router import _next_run_at

    assert _next_run_at({}, "Asia/Kolkata") is None


def test_next_run_at_returns_none_for_bad_tz():
    """An invalid timezone name must not crash the endpoint — returns None."""
    from dhanradar.admin.ops_router import _next_run_at

    result = _next_run_at({"hour": 9, "minute": 0}, "Not/A/Timezone")
    assert result is None


def test_next_run_at_every_minute_cron():
    """minute='*' (notify-drain) should return a next-fire within 60 s."""
    from dhanradar.admin.ops_router import _next_run_at

    result = _next_run_at({"minute": "*"}, "Asia/Kolkata")
    assert result is not None
    dt = datetime.fromisoformat(result)
    now = datetime.now(dt.tzinfo)
    assert dt > now - timedelta(seconds=5)
    assert dt <= now + timedelta(seconds=65), "Every-minute cron should fire within 65 s"


def test_next_run_at_iso_contains_timezone_offset():
    """The returned ISO string must include timezone info (not be naive)."""
    from dhanradar.admin.ops_router import _next_run_at

    result = _next_run_at({"hour": 22, "minute": 0}, "Asia/Kolkata")
    assert result is not None
    # A timezone-aware ISO string contains '+' or 'Z' after the time part.
    assert "+" in result or "Z" in result, f"Expected tz offset in ISO string, got: {result!r}"


def test_next_run_at_monthly_cron():
    """day_of_month cron (mf-monthly-rescore) must return a future date within ~32 days."""
    from dhanradar.admin.ops_router import _next_run_at

    result = _next_run_at({"day_of_month": 1, "hour": 3, "minute": 0}, "Asia/Kolkata")
    assert result is not None
    dt = datetime.fromisoformat(result)
    now = datetime.now(dt.tzinfo)
    assert dt > now - timedelta(seconds=5)
    assert dt <= now + timedelta(days=32), "Monthly cron should fire within 32 days"


# ---------------------------------------------------------------------------
# Task 1 — _derive_admin_alerts reused in get_health (recent_alerts populated)
#
# Strategy: mock only the DB execution layer (execute/scalar/scalars).
# SQLAlchemy select() is called with real model column objects — that is safe
# (model class definitions do NOT open a DB connection; only execution does).
# ---------------------------------------------------------------------------


def _make_db_for_alerts(
    mood_row=None,
    fail_count: int = 0,
    health_rows: list | None = None,
) -> AsyncMock:
    """Build an AsyncSession mock wired for _derive_admin_alerts.

    mood_row:    (snapshot_time, data_quality, inputs_available) or None.
    fail_count:  scalar returned for the ingestion-failure count query.
    health_rows: list of mock MfSourceHealth objects with .reachable and .source attrs.
    """
    db = AsyncMock()

    # db.execute() is called once: for the mood query.
    mood_result = MagicMock()
    mood_result.first.return_value = mood_row
    db.execute = AsyncMock(return_value=mood_result)

    # db.scalar() is called once: for the fail_count query.
    db.scalar = AsyncMock(return_value=fail_count)

    # db.scalars() is called once: for the source-health rows.
    _rows = health_rows or []
    scalars_result = MagicMock()
    scalars_result.all.return_value = _rows

    async def _scalars(*_a, **_kw):
        return scalars_result

    db.scalars = AsyncMock(side_effect=_scalars)
    return db


import pytest


@pytest.mark.asyncio
async def test_derive_admin_alerts_mood_missing_produces_alert():
    """When no mood snapshot exists, a 'mood_missing' critical alert is returned."""
    from dhanradar.admin.ops_router import _derive_admin_alerts

    db = _make_db_for_alerts(mood_row=None, fail_count=0)
    alerts = await _derive_admin_alerts(db)

    keys = [a.key for a in alerts]
    assert "mood_missing" in keys, f"Expected mood_missing alert, got keys: {keys}"
    mood_alert = next(a for a in alerts if a.key == "mood_missing")
    assert mood_alert.severity == "critical"


@pytest.mark.asyncio
async def test_derive_admin_alerts_ingestion_failures_produce_alert():
    """When fail_count > 0, an 'ingestion_failures' warning alert is returned."""
    from dhanradar.admin.ops_router import _derive_admin_alerts

    # Provide a fresh mood so we only get the ingestion alert.
    snap_time = datetime.now(UTC) - timedelta(hours=1)
    mood_row = (snap_time, "ok", 11)
    db = _make_db_for_alerts(mood_row=mood_row, fail_count=3, health_rows=[])
    alerts = await _derive_admin_alerts(db)

    keys = [a.key for a in alerts]
    assert "ingestion_failures" in keys, f"Expected ingestion_failures alert, got: {keys}"
    fa = next(a for a in alerts if a.key == "ingestion_failures")
    assert fa.severity == "warning"
    assert "3" in fa.title


@pytest.mark.asyncio
async def test_derive_admin_alerts_unhealthy_sources_produce_alert():
    """When a source is not reachable, a 'sources_unhealthy' alert is returned."""
    from dhanradar.admin.ops_router import _derive_admin_alerts

    snap_time = datetime.now(UTC) - timedelta(hours=1)
    mood_row = (snap_time, "ok", 11)

    unreachable = MagicMock()
    unreachable.reachable = False
    unreachable.source = "amfi_nav"

    db = _make_db_for_alerts(mood_row=mood_row, fail_count=0, health_rows=[unreachable])
    alerts = await _derive_admin_alerts(db)

    keys = [a.key for a in alerts]
    assert "sources_unhealthy" in keys, f"Expected sources_unhealthy alert, got: {keys}"


@pytest.mark.asyncio
async def test_derive_admin_alerts_no_alerts_when_healthy():
    """When mood is fresh, no failures, all sources reachable — zero alerts returned."""
    from dhanradar.admin.ops_router import _derive_admin_alerts

    snap_time = datetime.now(UTC) - timedelta(hours=1)
    mood_row = (snap_time, "ok", 11)

    reachable = MagicMock()
    reachable.reachable = True
    reachable.source = "amfi_nav"

    db = _make_db_for_alerts(mood_row=mood_row, fail_count=0, health_rows=[reachable])
    alerts = await _derive_admin_alerts(db)

    assert alerts == [], f"Expected no alerts when system is healthy, got: {alerts}"


def test_get_health_recent_alerts_mapping():
    """Verify the AdminAlert → RecentAlert mapping logic used in get_health.

    We test the mapping expression directly (same code as in get_health) rather
    than invoking the full route handler, which requires wiring RequireAdmin,
    DB, and Redis — unnecessary for a pure-mapping test.
    """
    from dhanradar.admin.ops_schemas import AdminAlert, RecentAlert

    # Alert with a 'since' timestamp set
    ts = "2026-06-22T09:00:00+05:30"
    alert_with_since = AdminAlert(
        key="mood_stale",
        severity="critical",
        title="Market Mood snapshot is stale",
        detail="The last DMMI read is ~21h old.",
        since=ts,
        href="/admin",
    )
    # Alert without 'since'
    alert_no_since = AdminAlert(
        key="mood_missing",
        severity="critical",
        title="Market Mood has never been computed",
        detail="No DMMI snapshot exists yet.",
    )

    now_iso = datetime.now(UTC).isoformat()
    raw = [alert_with_since, alert_no_since]
    recent: list[RecentAlert] = [
        RecentAlert(
            type=a.key,
            message=a.title + (" — " + a.detail if a.detail else ""),
            severity=a.severity,
            created_at=a.since or now_iso,
        )
        for a in raw[:10]
    ]

    assert len(recent) == 2

    r0 = recent[0]
    assert r0.type == "mood_stale"
    assert "Market Mood snapshot is stale" in r0.message
    assert "21h old" in r0.message
    assert r0.severity == "critical"
    assert r0.created_at == ts

    r1 = recent[1]
    assert r1.type == "mood_missing"
    assert "Market Mood has never been computed" in r1.message
    assert "No DMMI snapshot exists yet." in r1.message
    assert r1.severity == "critical"
    # since=None → falls back to now_iso; must be parseable
    datetime.fromisoformat(r1.created_at)
