"""
Integration tests for the Compliance Audit module (B26).

Infrastructure contract (same as test_notifications / test_billing):
  - async_client      — httpx.AsyncClient over ASGITransport(app); no lifespan.
  - db_session        — function-scoped AsyncSession; truncates between tests.
  - fake_redis        — fakeredis.aioredis.FakeRedis; flushed between tests.
  - patch_redis       — routes get_redis() to fake_redis.
  - patch_settings_keys — ephemeral RSA keypair; COOKIE_SECURE=False.
  - monkeypatch.setattr(dhanradar.db, "engine", db_session.bind) — redirects the
    own-session services (_archive, record_served_label) to the test DB.

Seed rows are committed via db_session BEFORE the service call so that the
service's *separate* AsyncSession can see them.

Covered (in order):
  1. GET /api/v1/disclaimers/<type>  → 200 with seeded disclaimer; 404 for unknown.
  2. record_served_label (valid) → True; one audit row written with correct fields.
  3. record_served_label(buy_sell) → False; zero audit rows.
  4. DB CHECK constraint rejects AiRecommendationAudit(recommendation_type='buy_sell').
  5. _archive() exports yesterday's rows to a recorder (no network); result contains
     "r2://audit/". Also: _archive() with no matching rows returns "0 rows" string.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy.exc
from sqlalchemy import select

import dhanradar.db as _db_mod
from dhanradar.models.compliance import AiRecommendationAudit, Disclaimer

pytestmark = pytest.mark.integration

_IST = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------------------------
# Teardown helper: truncate compliance tables between tests (conftest only
# handles auth/billing). Applied automatically by the function-scoped fixture.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _truncate_compliance(db_session):
    """Truncate compliance tables after each test so rows don't bleed across.

    MUST run on `db_session`'s OWN connection — NOT a separate `db_session.bind.begin()`
    connection. The test may leave an open read transaction on `db_session` (e.g. a
    trailing SELECT) holding an ACCESS SHARE lock on these tables; a TRUNCATE from a
    second connection would wait forever for ACCESS EXCLUSIVE (the test's lock only
    releases when db_session tears down, which happens AFTER this fixture) → deadlock /
    CI hang. Same-connection TRUNCATE upgrades the lock in-transaction, no wait.
    """
    yield
    from sqlalchemy import text

    await db_session.rollback()  # drop any open read txn so the TRUNCATE is clean
    await db_session.execute(
        text(
            "TRUNCATE TABLE compliance.ai_recommendation_audit, "
            "compliance.disclaimers RESTART IDENTITY CASCADE"
        )
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# 1. GET /api/v1/disclaimers/{type}
# ---------------------------------------------------------------------------


async def test_get_disclaimer_200(async_client, db_session, patch_redis):
    """Seed a disclaimer; GET returns 200 with matching version and content."""
    disc = Disclaimer(
        version="2026-06-06.v1",
        type="ai_recommendation",
        content="Educational analysis only — not investment advice.",
        active=True,
    )
    db_session.add(disc)
    await db_session.commit()

    r = await async_client.get("/api/v1/disclaimers/ai_recommendation")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == "2026-06-06.v1"
    assert body["content"] == "Educational analysis only — not investment advice."
    assert body["type"] == "ai_recommendation"


async def test_get_disclaimer_404_unknown_type(async_client, db_session, patch_redis):
    """No disclaimer seeded for type → 404 disclaimer_not_found."""
    r = await async_client.get("/api/v1/disclaimers/nope")
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "disclaimer_not_found"


# ---------------------------------------------------------------------------
# 2. record_served_label — valid call writes one row
# ---------------------------------------------------------------------------


async def test_record_served_label_writes_row(db_session, monkeypatch, patch_redis):
    """record_served_label with valid args returns True and persists one row."""
    from dhanradar.compliance.service import record_served_label

    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    user_id = str(uuid.uuid4())
    result = await record_served_label(
        surface="mf_report",
        label="on_track",
        model="v1",
        disclaimer_version="2026-06-06.v1",
        user_id=user_id,
        identifier="INF0001",
        confidence_band="medium",
    )
    assert result is True

    # The service commits via its own session; refresh our view.
    await db_session.commit()
    rows = (await db_session.scalars(select(AiRecommendationAudit))).all()
    assert len(rows) == 1, f"Expected 1 audit row, got {len(rows)}"

    row = rows[0]
    assert row.label == "on_track"
    assert row.surface == "mf_report"
    assert row.recommendation_type == "educational_label"
    assert row.disclaimer_version == "2026-06-06.v1"
    assert row.confidence_band == "medium"
    assert row.content_hash and len(row.content_hash) == 64
    assert row.user_id == uuid.UUID(user_id)


# ---------------------------------------------------------------------------
# 3. record_served_label — buy_sell → False + zero rows
# ---------------------------------------------------------------------------


async def test_record_served_label_buy_sell_no_row(db_session, monkeypatch, patch_redis):
    """recommendation_type='buy_sell' returns False and writes nothing."""
    from dhanradar.compliance.service import record_served_label

    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    result = await record_served_label(
        surface="mf_report",
        label="on_track",
        model="v1",
        disclaimer_version="2026-06-06.v1",
        recommendation_type="buy_sell",
    )
    assert result is False

    await db_session.commit()
    rows = (await db_session.scalars(select(AiRecommendationAudit))).all()
    assert len(rows) == 0, f"Expected 0 audit rows, got {len(rows)}"


# ---------------------------------------------------------------------------
# 4. DB CHECK constraint rejects buy_sell directly
# ---------------------------------------------------------------------------


async def test_audit_check_constraint_rejects_buy_sell(db_session):
    """INSERT with recommendation_type='buy_sell' must raise IntegrityError from
    the DB-level CHECK (ck_audit_no_buy_sell)."""
    bad_row = AiRecommendationAudit(
        served_at=datetime.now(timezone.utc),
        recommendation_type="buy_sell",
        content_hash="x" * 64,
        disclaimer_version="2026-06-06.v1",
    )
    db_session.add(bad_row)
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await db_session.flush()
    await db_session.rollback()


# ---------------------------------------------------------------------------
# 5. _archive() — exports yesterday's rows; "0 rows" when none
# ---------------------------------------------------------------------------


async def test_archive_exports_row(db_session, monkeypatch):
    """_archive() uploads one gzipped JSONL to R2 and returns a string with
    r2://audit/. No real boto3/network — storage.put_object is replaced by a
    recorder list."""
    import dhanradar.storage as _storage
    from dhanradar.tasks.compliance import _archive

    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    # Build a served_at that falls within yesterday's IST window.
    now_ist = datetime.now(_IST)
    yesterday_noon_ist = (now_ist - timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    yesterday_noon_utc = yesterday_noon_ist.astimezone(timezone.utc)

    # Seed one audit row with served_at = yesterday 12:00 IST.
    row = AiRecommendationAudit(
        served_at=yesterday_noon_utc,
        recommendation_type="educational_label",
        label="on_track",
        content_hash="a" * 64,
        model="v1",
        disclaimer_version="2026-06-06.v1",
        surface="mf_report",
    )
    db_session.add(row)
    await db_session.commit()

    # Replace storage.put_object with a recorder (no boto3, no network).
    uploads: list[tuple[str, bytes, str]] = []

    def _record_put(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        uploads.append((key, data, content_type))

    monkeypatch.setattr(_storage, "put_object", _record_put)

    result = await _archive()

    assert len(uploads) == 1, f"Expected 1 upload, got {len(uploads)}"
    key, data, ct = uploads[0]
    assert key.startswith("audit/"), f"Expected key under audit/, got {key!r}"
    assert ct == "application/gzip"
    assert "r2://audit/" in result, f"Unexpected result: {result!r}"


async def test_archive_zero_rows(db_session, monkeypatch):
    """_archive() with no rows in the prior-IST-day window returns a string
    containing '0 rows' and uploads nothing."""
    import dhanradar.storage as _storage
    from dhanradar.tasks.compliance import _archive

    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    uploads: list = []

    def _record_put(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        uploads.append((key, data, content_type))

    monkeypatch.setattr(_storage, "put_object", _record_put)

    result = await _archive()

    assert len(uploads) == 0, "No uploads expected when no rows exist"
    assert "0 rows" in result, f"Expected '0 rows' in result, got: {result!r}"
