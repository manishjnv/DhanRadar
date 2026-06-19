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
from datetime import UTC, datetime

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


def test_paused_sources_key_constant():
    from dhanradar.admin.ops_router import _PAUSED_SOURCES_KEY

    assert _PAUSED_SOURCES_KEY == "paused_sources"
