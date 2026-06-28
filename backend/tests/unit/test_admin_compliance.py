"""Unit tests for admin compliance service helpers (no DB required).

Covers:
  1. _snapshot_from_rows — grouping, latest-label-per-key-wins, user_id vs fallback keying.
  2. label_churn governance wiring — review_batch hold/publish at real thresholds.
  3. Migration revision chain — 0008.revision == "0008" and down_revision == "0007".
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from dhanradar.compliance.service import _snapshot_from_rows
from dhanradar.scoring.engine import governance

# ---------------------------------------------------------------------------
# 1. _snapshot_from_rows
# ---------------------------------------------------------------------------

def _row(served_at, label, user_id=None, session_id=None, request_id=None, content_hash="x" * 64):
    return SimpleNamespace(
        served_at=served_at,
        label=label,
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        content_hash=content_hash,
    )


def test_snapshot_from_rows_keys_and_latest_wins():
    """Rows must be grouped by UTC date; user_id is preferred key; later row wins."""
    import uuid

    uid_a = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    uid_b = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    day1 = datetime(2026, 6, 5, 10, 0, 0, tzinfo=UTC)
    day2 = datetime(2026, 6, 6, 10, 0, 0, tzinfo=UTC)
    day2_later = datetime(2026, 6, 6, 14, 0, 0, tzinfo=UTC)

    rows = [
        # day1: user A → on_track, user B → off_track
        _row(day1, "on_track", user_id=uid_a),
        _row(day1, "off_track", user_id=uid_b),
        # day2: user A gets two rows — latest wins
        _row(day2, "on_track", user_id=uid_a),
        _row(day2_later, "in_form", user_id=uid_a),  # overwrites
        # day2: no user_id — falls back to session_id
        _row(day2, "out_of_form", session_id="sess-xyz"),
    ]

    snap = _snapshot_from_rows(rows)

    assert set(snap.keys()) == {"2026-06-05", "2026-06-06"}

    d1 = snap["2026-06-05"]
    assert d1[str(uid_a)] == "on_track"
    assert d1[str(uid_b)] == "off_track"

    d2 = snap["2026-06-06"]
    # Latest row for uid_a overwrites earlier on_track → in_form
    assert d2[str(uid_a)] == "in_form"
    # session_id fallback
    assert d2["sess-xyz"] == "out_of_form"


def test_snapshot_from_rows_request_id_fallback():
    """Falls back to request_id when both user_id and session_id are absent."""
    day = datetime(2026, 6, 6, 10, 0, 0, tzinfo=UTC)
    rows = [_row(day, "on_track", request_id="req-001")]
    snap = _snapshot_from_rows(rows)
    assert snap["2026-06-06"]["req-001"] == "on_track"


def test_snapshot_from_rows_content_hash_fallback():
    """Final fallback is content_hash when all other keys are None."""
    day = datetime(2026, 6, 6, 10, 0, 0, tzinfo=UTC)
    ch = "c" * 64
    rows = [_row(day, "off_track", content_hash=ch)]
    snap = _snapshot_from_rows(rows)
    assert snap["2026-06-06"][ch] == "off_track"


def test_snapshot_from_rows_empty():
    assert _snapshot_from_rows([]) == {}


# ---------------------------------------------------------------------------
# 2. label_churn governance wiring — sanity check at real thresholds
# ---------------------------------------------------------------------------

def test_label_churn_hold_when_over_threshold():
    """review_batch returns hold when churn > 5% (15% here)."""
    # 20 subjects; 3 change label (15% churn > 5% threshold)
    prev = {str(i): "on_track" for i in range(20)}
    curr = dict(prev)
    for i in range(3):
        curr[str(i)] = "off_track"

    review = governance.review_batch(prev, curr)
    assert review.decision is governance.BatchDecision.hold
    assert review.churn == pytest.approx(0.15)


def test_label_churn_publish_when_within_bounds():
    """review_batch returns publish when churn <= 5% and no distribution violation."""
    # 4 subjects; 2 labels evenly split (50/50, below 80% cap); 0 changes.
    prev = {"a": "on_track", "b": "on_track", "c": "off_track", "d": "off_track"}
    curr = dict(prev)  # no changes → churn 0.0, no distribution violation

    review = governance.review_batch(prev, curr)
    assert review.decision is governance.BatchDecision.publish
    assert review.churn == pytest.approx(0.0)


def test_label_churn_hold_distribution_violation():
    """review_batch triggers hold on distribution violation even with zero churn."""
    # Same subjects, same labels — but 90% share one label
    prev = {str(i): "on_track" for i in range(10)}
    curr = {str(i): "on_track" for i in range(10)}  # 100% on_track — violates 80% cap

    review = governance.review_batch(prev, curr)
    assert review.decision is governance.BatchDecision.hold
    assert len(review.distribution_violations) >= 1


# ---------------------------------------------------------------------------
# 3. Migration revision chain
# ---------------------------------------------------------------------------

def test_0008_revision_chain():
    """Migration 0008 must have revision='0008' and down_revision='0007'."""
    import importlib.util
    import pathlib

    # Module name starts with a digit — can't use importlib.import_module with
    # dotted package syntax.  Load by absolute file path instead.
    migration_path = (
        pathlib.Path(__file__).parent.parent.parent
        / "alembic" / "versions" / "0008_admin_compliance_tables.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0008", migration_path)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    assert mod.revision == "0008"
    assert mod.down_revision == "0007"


# ---------------------------------------------------------------------------
# 4. Input validation guards (reject before any DB access → db=None is safe)
# ---------------------------------------------------------------------------

async def test_create_disclaimer_rejects_oversized_content():
    """content over the 64 KiB bound is rejected with ValueError before DB access."""
    from dhanradar.compliance.service import _MAX_DISCLAIMER_CONTENT, create_disclaimer

    too_long = "x" * (_MAX_DISCLAIMER_CONTENT + 1)
    with pytest.raises(ValueError, match="exceeds"):
        await create_disclaimer(None, version="2026-07-01.v9", content=too_long, created_by="u")


async def test_create_disclaimer_rejects_unknown_type():
    """An unknown disclaimer type is rejected with ValueError before DB access."""
    from dhanradar.compliance.service import create_disclaimer

    with pytest.raises(ValueError, match="unknown disclaimer type"):
        await create_disclaimer(None, version="v", content="ok", type="not_a_type", created_by="u")


async def test_label_churn_rejects_non_allowlisted_type():
    """label_churn_review rejects a non-allowlisted recommendation_type (no fail-open
    insufficient_data) before any DB access."""
    from dhanradar.compliance.service import label_churn_review

    with pytest.raises(ValueError, match="unknown recommendation_type"):
        await label_churn_review(None, recommendation_type="buy_sell")
