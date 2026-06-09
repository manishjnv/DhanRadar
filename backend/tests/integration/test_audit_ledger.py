"""
Integration tests for the Audit Ledger module (B57 P2).

Infrastructure contract (same as test_compliance):
  - db_session   — function-scoped AsyncSession; truncates between tests.
  - monkeypatch.setattr(dhanradar.db, "engine", db_session.bind) — redirects
    the own-session audit helpers to the test DB.

Covered (in order):
  1. record_admin_action   — writes one row; row_hash is 64-char hex;
                              row_hash is REPRODUCIBLE.
  2. record_payment_event  — writes one row; row_hash reproducible.
  3. record_security_event — writes one row; row_hash reproducible;
                              stored user_ref == hash_user_ref(input);
                              raw user_id does NOT appear in the stored row.
  4. Fire-and-forget safety — monkeypatch engine to raise; assert each helper
                              returns False without raising.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

import dhanradar.db as _db_mod
from dhanradar.audit.service import (
    _row_hash,
    record_admin_action,
    record_payment_event,
    record_security_event,
)
from dhanradar.core.logging import hash_user_ref
from dhanradar.models.audit import AdminAction, PaymentEvent, SecurityEvent

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Teardown helper: truncate audit tables between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _truncate_audit(db_session):
    """Truncate audit tables after each test so rows don't bleed across.

    Must use the SAME connection as db_session (see test_compliance for the
    ACCESS SHARE / ACCESS EXCLUSIVE deadlock explanation).
    """
    yield
    from sqlalchemy import text

    await db_session.rollback()
    await db_session.execute(
        text(
            "TRUNCATE TABLE audit.admin_actions, "
            "audit.payment_events, "
            "audit.security_events RESTART IDENTITY CASCADE"
        )
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# 1. record_admin_action
# ---------------------------------------------------------------------------


async def test_record_admin_action_writes_row(db_session, monkeypatch):
    """record_admin_action returns True and persists one row with correct fields
    and a reproducible 64-char hex row_hash."""
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    result = await record_admin_action(
        admin_id="admin-uuid-001",
        action="activate_disclaimer",
        target_type="disclaimer",
        target_id="2026-06-09.v1",
        result="success",
        request_id="req-abc123",
    )
    assert result is True

    await db_session.commit()
    rows = (await db_session.scalars(select(AdminAction))).all()
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"

    row = rows[0]
    assert row.admin_id == "admin-uuid-001"
    assert row.action == "activate_disclaimer"
    assert row.target_type == "disclaimer"
    assert row.target_id == "2026-06-09.v1"
    assert row.result == "success"
    assert row.request_id == "req-abc123"

    # row_hash must be a 64-char hex string
    assert row.row_hash and len(row.row_hash) == 64
    assert all(c in "0123456789abcdef" for c in row.row_hash)

    # row_hash must be reproducible from the stored fields
    expected_hash = _row_hash(
        {
            "ts": row.ts,
            "admin_id": row.admin_id,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "result": row.result,
            "request_id": row.request_id,
        }
    )
    assert row.row_hash == expected_hash, (
        f"row_hash mismatch: stored={row.row_hash!r} recomputed={expected_hash!r}"
    )


# ---------------------------------------------------------------------------
# 2. record_payment_event
# ---------------------------------------------------------------------------


async def test_record_payment_event_writes_row(db_session, monkeypatch):
    """record_payment_event returns True and persists one row with correct fields
    and a reproducible 64-char hex row_hash."""
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    user_id = "user-uuid-999"
    result = await record_payment_event(
        user_id=user_id,
        order_id="sub_RAZORPAY001",
        razorpay_payment_id=None,
        status="active",
        request_id=None,
    )
    assert result is True

    await db_session.commit()
    rows = (await db_session.scalars(select(PaymentEvent))).all()
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"

    row = rows[0]
    assert row.user_id == user_id
    assert row.order_id == "sub_RAZORPAY001"
    assert row.razorpay_payment_id is None
    assert row.status == "active"
    assert row.request_id is None

    assert row.row_hash and len(row.row_hash) == 64
    assert all(c in "0123456789abcdef" for c in row.row_hash)

    expected_hash = _row_hash(
        {
            "ts": row.ts,
            "user_id": row.user_id,
            "order_id": row.order_id,
            "razorpay_payment_id": row.razorpay_payment_id,
            "status": row.status,
            "request_id": row.request_id,
        }
    )
    assert row.row_hash == expected_hash


# ---------------------------------------------------------------------------
# 3. record_security_event — user_ref hashed, raw user_id not stored
# ---------------------------------------------------------------------------


async def test_record_security_event_writes_row_and_hashes_user(db_session, monkeypatch):
    """record_security_event returns True; stored user_ref == hash_user_ref(input);
    raw user_id does NOT appear in user_ref; row_hash is reproducible."""
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    raw_user_id = "user-uuid-secret-42"
    result = await record_security_event(
        event_type="refresh_reuse_detected",
        user_id=raw_user_id,
        request_id="req-sec-001",
    )
    assert result is True

    await db_session.commit()
    rows = (await db_session.scalars(select(SecurityEvent))).all()
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"

    row = rows[0]
    assert row.event_type == "refresh_reuse_detected"
    assert row.request_id == "req-sec-001"

    # user_ref must be the hashed form, not the raw user_id
    expected_ref = hash_user_ref(raw_user_id)
    assert row.user_ref == expected_ref, (
        f"Expected user_ref={expected_ref!r}, got {row.user_ref!r}"
    )
    assert raw_user_id not in (row.user_ref or ""), (
        "raw user_id must not appear in stored user_ref"
    )

    assert row.row_hash and len(row.row_hash) == 64

    expected_hash = _row_hash(
        {
            "ts": row.ts,
            "event_type": row.event_type,
            "user_ref": row.user_ref,
            "request_id": row.request_id,
        }
    )
    assert row.row_hash == expected_hash


# ---------------------------------------------------------------------------
# 4. Fire-and-forget safety — engine raises → helper returns False, never raises
# ---------------------------------------------------------------------------


class _BrokenEngine:
    """Stand-in for dhanradar.db.engine that always raises on use."""

    def connect(self, *_a, **_kw):  # noqa: ANN001
        raise RuntimeError("injected DB failure")

    def dispose(self, *_a, **_kw) -> None:  # noqa: ANN001
        pass


async def test_record_admin_action_returns_false_on_db_error(db_session, monkeypatch):
    """record_admin_action returns False (never raises) when the DB is broken."""
    monkeypatch.setattr(_db_mod, "engine", _BrokenEngine())
    result = await record_admin_action(
        admin_id="a",
        action="test",
        target_type=None,
        target_id=None,
        result="success",
    )
    assert result is False


async def test_record_payment_event_returns_false_on_db_error(db_session, monkeypatch):
    """record_payment_event returns False (never raises) when the DB is broken."""
    monkeypatch.setattr(_db_mod, "engine", _BrokenEngine())
    result = await record_payment_event(
        user_id="u",
        order_id=None,
        razorpay_payment_id=None,
        status="active",
    )
    assert result is False


async def test_record_security_event_returns_false_on_db_error(db_session, monkeypatch):
    """record_security_event returns False (never raises) when the DB is broken."""
    monkeypatch.setattr(_db_mod, "engine", _BrokenEngine())
    result = await record_security_event(
        event_type="totp_locked",
        user_id="u",
    )
    assert result is False
