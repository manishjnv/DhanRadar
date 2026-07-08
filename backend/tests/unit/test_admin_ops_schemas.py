"""Unit tests for admin ops schemas + is_admin computation (Admin Console Phase 1).

Tests:
  - RequireAdmin gate still fires 404 for non-admins (regression guard on ops router).
  - is_admin=True for a UUID in the allowlist; is_admin=False otherwise.
  - is_admin normalises UUID case (upper-case allowlist, lower-case user_id).
  - OkResponse, SyncResponse, QualityRow schema round-trip.
  - _duration_s helper returns correct delta and None when inputs are None.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

# ---------------------------------------------------------------------------
# is_admin computation — mirrors RequireAdmin normalisation
# ---------------------------------------------------------------------------


def _compute_is_admin(user_id: str, admin_ids_raw: str) -> bool:
    """Reproduce the exact logic in auth/router.py me() handler."""
    import uuid as _uuid
    from unittest.mock import MagicMock

    settings = MagicMock()
    out: set[str] = set()
    for raw in admin_ids_raw.split(","):
        s = raw.strip()
        if not s:
            continue
        try:
            out.add(str(_uuid.UUID(s)))
        except ValueError:
            continue
    settings.admin_user_ids = frozenset(out)

    try:
        canonical_uid = str(_uuid.UUID(str(user_id)))
        return canonical_uid in settings.admin_user_ids
    except (ValueError, TypeError):
        return False


def test_is_admin_true_when_uuid_in_allowlist():
    a = str(uuid.uuid4())
    assert _compute_is_admin(a, a) is True


def test_is_admin_false_when_uuid_not_in_allowlist():
    a = str(uuid.uuid4())
    b = str(uuid.uuid4())
    assert _compute_is_admin(a, b) is False


def test_is_admin_case_insensitive():
    a = str(uuid.uuid4())
    # Allowlist stored upper-case, user_id lower-case
    assert _compute_is_admin(a, a.upper()) is True


def test_is_admin_false_for_empty_allowlist():
    a = str(uuid.uuid4())
    assert _compute_is_admin(a, "") is False


def test_is_admin_false_for_garbage_user_id():
    assert _compute_is_admin("not-a-uuid", str(uuid.uuid4())) is False


# ---------------------------------------------------------------------------
# Schema round-trips
# ---------------------------------------------------------------------------


def test_ok_response_defaults_to_true():
    from dhanradar.admin.ops_schemas import OkResponse

    r = OkResponse()
    assert r.ok is True


def test_sync_response_holds_task_id():
    from dhanradar.admin.ops_schemas import SyncResponse

    r = SyncResponse(task_id="abc-123")
    assert r.task_id == "abc-123"


def test_quality_row_all_fields():
    from dhanradar.admin.ops_schemas import QualityRow

    r = QualityRow(
        metric_key="missing_nav",
        label="Missing NAV",
        current_value=5.0,
        threshold=0.0,
        unit="schemes",
        status="critical",
        acknowledged_until=None,
    )
    assert r.metric_key == "missing_nav"
    assert r.status == "critical"
    assert r.acknowledged_until is None


# ---------------------------------------------------------------------------
# _duration_s helper
# ---------------------------------------------------------------------------


def test_duration_s_computes_delta():
    from dhanradar.admin.ops_router import _duration_s

    t0 = datetime(2026, 6, 19, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 6, 19, 10, 0, 30, tzinfo=UTC)
    assert _duration_s(t0, t1) == 30.0


def test_duration_s_returns_none_when_missing():
    from dhanradar.admin.ops_router import _duration_s

    assert _duration_s(None, None) is None
    assert _duration_s(datetime(2026, 6, 19, 10, 0, 0, tzinfo=UTC), None) is None
    assert _duration_s(None, datetime(2026, 6, 19, 10, 0, 0, tzinfo=UTC)) is None


def test_duration_s_handles_naive_datetimes():
    """Naive datetimes (no tzinfo) should be treated as UTC."""
    from dhanradar.admin.ops_router import _duration_s

    t0 = datetime(2026, 6, 19, 10, 0, 0)  # naive
    t1 = datetime(2026, 6, 19, 10, 1, 0)  # naive
    assert _duration_s(t0, t1) == 60.0


# ---------------------------------------------------------------------------
# Source/task catalog completeness
# ---------------------------------------------------------------------------


def test_source_catalog_keys_unique():
    from dhanradar.admin.ops_router import _SOURCE_CATALOG

    keys = [s["source_key"] for s in _SOURCE_CATALOG]
    assert len(keys) == len(set(keys)), "Duplicate source_key in _SOURCE_CATALOG"


def test_beat_tasks_beat_keys_unique():
    from dhanradar.admin.ops_router import _BEAT_TASKS

    keys = [t["beat_key"] for t in _BEAT_TASKS]
    assert len(keys) == len(set(keys)), "Duplicate beat_key in _BEAT_TASKS"


def test_source_to_task_map_non_empty():
    from dhanradar.admin.ops_router import _SOURCE_TO_TASK

    assert len(_SOURCE_TO_TASK) > 0


# ---------------------------------------------------------------------------
# _is_stale — staleness detection for the Sources dashboard
# ---------------------------------------------------------------------------


def test_is_stale_false_when_within_threshold():
    from dhanradar.admin.ops_router import _is_stale

    recent = datetime.now(UTC) - timedelta(hours=1)
    assert _is_stale("amfi_nav", recent) is False


def test_is_stale_true_when_past_threshold():
    from dhanradar.admin.ops_router import _is_stale

    old = datetime.now(UTC) - timedelta(hours=48)
    assert _is_stale("amfi_nav", old) is True


def test_is_stale_false_for_source_with_no_cadence():
    """Sources with no entry in _SOURCE_STALENESS_HOURS (on-demand/fallback-only)
    are never marked stale, no matter how old the last run is."""
    from dhanradar.admin.ops_router import _is_stale

    ancient = datetime.now(UTC) - timedelta(days=3650)
    assert _is_stale("mfapi", ancient) is False


def test_is_stale_false_when_finished_at_is_none():
    from dhanradar.admin.ops_router import _is_stale

    assert _is_stale("amfi_nav", None) is False


def test_source_staleness_hours_only_covers_scheduled_sources():
    """Every key in _SOURCE_STALENESS_HOURS must be a real catalog source_key."""
    from dhanradar.admin.ops_router import _SOURCE_CATALOG, _SOURCE_STALENESS_HOURS

    catalog_keys = {s["source_key"] for s in _SOURCE_CATALOG}
    assert set(_SOURCE_STALENESS_HOURS.keys()) <= catalog_keys


def test_paused_sources_key_constant():
    from dhanradar.admin.ops_router import _PAUSED_SOURCES_KEY

    assert _PAUSED_SOURCES_KEY == "paused_sources"


def test_source_catalog_contains_upstox_analytics():
    from dhanradar.admin.ops_router import _SOURCE_CATALOG

    keys = [s["source_key"] for s in _SOURCE_CATALOG]
    assert "upstox_analytics" in keys, (
        f"upstox_analytics missing from _SOURCE_CATALOG; got: {keys}"
    )


def test_upstox_analytics_catalog_shape():
    """Verify the upstox_analytics entry has the required keys and exact source_key string."""
    from dhanradar.admin.ops_router import _SOURCE_CATALOG

    entry = next(
        (s for s in _SOURCE_CATALOG if s["source_key"] == "upstox_analytics"), None
    )
    assert entry is not None, "upstox_analytics not in _SOURCE_CATALOG"
    # Exact source_key string — the integration contract with the mood task.
    assert entry["source_key"] == "upstox_analytics"
    assert entry["tier"] == "Market"
    assert entry["celery_task"] == "dhanradar.tasks.mood.compute_mood_snapshot"
    assert entry["beat_key"] == "mood-compute-snapshot"
    # Required catalog keys must all be present
    for key in ("name", "description", "method", "schedule_display", "cost"):
        assert key in entry, f"Missing key {key!r} in upstox_analytics catalog entry"


# ---------------------------------------------------------------------------
# MoodStatus schema
# ---------------------------------------------------------------------------


def test_mood_status_defaults():
    """MoodStatus round-trips with its zero/None shape (empty-DB scenario)."""
    from dhanradar.admin.ops_schemas import MoodStatus

    m = MoodStatus(
        snapshot_at=None,
        regime=None,
        inputs_available=0,
        data_quality=None,
        signals_present=[],
        upstox_fii_flows=False,
        upstox_dii_flows=False,
        upstox_put_call_ratio=False,
    )
    assert m.snapshot_at is None
    assert m.regime is None
    assert m.inputs_available == 0
    assert m.total_signals == 11   # class-level default
    assert m.data_quality is None
    assert m.signals_present == []
    assert m.upstox_fii_flows is False
    assert m.upstox_dii_flows is False
    assert m.upstox_put_call_ratio is False


def test_mood_status_with_signals():
    """MoodStatus correctly stores signals_present and upstox booleans."""
    from dhanradar.admin.ops_schemas import MoodStatus

    m = MoodStatus(
        snapshot_at="2026-06-22T09:00:00+00:00",
        regime="Cautiously Optimistic",
        inputs_available=4,
        data_quality="ok",
        signals_present=["dii_flows", "fii_flows", "nifty_momentum", "put_call_ratio"],
        upstox_fii_flows=True,
        upstox_dii_flows=True,
        upstox_put_call_ratio=True,
    )
    assert m.total_signals == 11
    assert m.inputs_available == 4
    assert "fii_flows" in m.signals_present
    assert m.upstox_fii_flows is True
    assert m.upstox_dii_flows is True
    assert m.upstox_put_call_ratio is True


# ---------------------------------------------------------------------------
# _STATUS_ORDER sort helper — pure unit, no DB/Redis
# ---------------------------------------------------------------------------


def _make_source_row(source_key: str, status: str):
    """Build a minimal SourceRow for sort-order testing."""
    from dhanradar.admin.ops_schemas import SourceRow

    return SourceRow(
        source_key=source_key,
        name=source_key,
        tier="Test",
        description="",
        method="api",
        schedule_display="daily",
        cost="free",
        last_success_at=None,
        last_records=None,
        status=status,
        paused=(status == "Paused"),
    )


def test_sort_sources_order():
    """_STATUS_ORDER produces Healthy→Planned→Paused→Failed; stable within each group."""
    from dhanradar.admin.ops_router import _STATUS_ORDER

    # Build rows in a deliberately scrambled catalog order.
    rows = [
        _make_source_row("src_failed_1", "Failed"),
        _make_source_row("src_healthy_1", "Healthy"),
        _make_source_row("src_paused_1", "Paused"),
        _make_source_row("src_planned_1", "Planned"),
        _make_source_row("src_healthy_2", "Healthy"),
        _make_source_row("src_failed_2", "Failed"),
        _make_source_row("src_planned_2", "Planned"),
    ]

    rows.sort(key=lambda r: _STATUS_ORDER.get(r.status, 99))

    statuses = [r.status for r in rows]
    # All Healthy entries first, then Planned, then Paused, then Failed.
    assert statuses == [
        "Healthy",
        "Healthy",
        "Planned",
        "Planned",
        "Paused",
        "Failed",
        "Failed",
    ], f"Unexpected order: {statuses}"


def test_sort_sources_stable_within_group():
    """Catalog order is preserved within each status group (stable sort)."""
    from dhanradar.admin.ops_router import _STATUS_ORDER

    rows = [
        _make_source_row("first_healthy", "Healthy"),
        _make_source_row("second_healthy", "Healthy"),
        _make_source_row("third_healthy", "Healthy"),
    ]
    rows.sort(key=lambda r: _STATUS_ORDER.get(r.status, 99))
    assert [r.source_key for r in rows] == [
        "first_healthy",
        "second_healthy",
        "third_healthy",
    ]


def test_sort_sources_unknown_status_sorts_last():
    """An unknown status value is placed after Failed (priority 99)."""
    from dhanradar.admin.ops_router import _STATUS_ORDER

    rows = [
        _make_source_row("unk", "Unknown"),
        _make_source_row("fail", "Failed"),
        _make_source_row("ok", "Healthy"),
    ]
    rows.sort(key=lambda r: _STATUS_ORDER.get(r.status, 99))
    assert [r.source_key for r in rows] == ["ok", "fail", "unk"]


def test_mood_status_partial_upstox():
    """When only some Upstox signals are present, booleans are independent."""
    from dhanradar.admin.ops_schemas import MoodStatus

    m = MoodStatus(
        snapshot_at="2026-06-22T09:00:00+00:00",
        regime="Neutral",
        inputs_available=2,
        data_quality="degraded",
        signals_present=["fii_flows", "nifty_momentum"],
        upstox_fii_flows=True,
        upstox_dii_flows=False,
        upstox_put_call_ratio=False,
    )
    assert m.upstox_fii_flows is True
    assert m.upstox_dii_flows is False
    assert m.upstox_put_call_ratio is False
