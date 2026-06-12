"""
DhanRadar — Unit tests for admin news CRUD service helpers (B56-f4).

Tests the service layer only; no DB/Redis/network.  The DB is replaced with
an AsyncMock that mimics the SQLAlchemy AsyncSession interface: execute returns
a result whose scalar_one_or_none / scalars().all() can be controlled per test.

Covered:
  1. create_news_item: item lands as draft (is_active=False, provenance_source
     "admin_curated", published_at defaulted to now when not supplied).
  2. Duplicate canonical_url raises DuplicateUrlError.
  3. Advisory titles rejected (word-bounded _ADVISORY_RE):
       - "Buy these 5 funds now" → rejected
       - "Investors should avoid mid-caps" → rejected
       - "Strong buy signals everywhere" → rejected
       - "AMFI monthly SIP data hits record" → accepted (no advisory verb)
       - "SEBI circular on expense ratios" → accepted
       - "Shareholding pattern disclosures" → accepted (substring "hold" is NOT
         word-bounded next to "Sharehold…", so must NOT trip the regex)
  4. Empty / whitespace fields raise ValueError("empty_field: <name>").
  5. Invalid URL scheme raises ValueError("invalid_url").
  6. update_news_item applies partial fields + validates title advisory screen.
  7. update_news_item of unknown id raises KeyError.
  8. delete_news_item of unknown id raises KeyError.
  9. admin_list_news returns inactive + old items (no recency cutoff);
     scope and is_active filters applied.
 10. update_news_item rejects explicit None values and unknown fields before
     touching the DB; string fields are stored stripped (matching create).

asyncio_mode = "auto" (pyproject.toml) — async tests need no decorator.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlalchemy.exc

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(**kwargs) -> MagicMock:
    """Build a minimal NewsItem-like mock row."""
    from dhanradar.models.news import NewsItem as NewsItemModel

    row = MagicMock(spec=NewsItemModel)
    row.id = kwargs.get("id", str(uuid.uuid4()))
    row.scope = kwargs.get("scope", "market")
    row.category = kwargs.get("category", "mutual_funds")
    row.title = kwargs.get("title", "AMFI SIP data")
    row.source = kwargs.get("source", "AMFI")
    row.canonical_url = kwargs.get("canonical_url", "https://amfiindia.com/sip")
    row.published_at = kwargs.get("published_at", datetime.now(UTC))
    row.provenance_source = kwargs.get("provenance_source", "admin_curated")
    row.fetched_at = kwargs.get("fetched_at", datetime.now(UTC))
    row.is_active = kwargs.get("is_active", False)
    row.created_at = kwargs.get("created_at", datetime.now(UTC))
    row.updated_at = kwargs.get("updated_at", datetime.now(UTC))
    return row


def _db_with_no_row() -> AsyncMock:
    """Return a mock db session whose SELECT returns no row."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)
    return db


def _db_with_row(row: MagicMock) -> AsyncMock:
    """Return a mock db session whose SELECT returns `row`."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = row
    db.execute = AsyncMock(return_value=mock_result)
    return db


# ---------------------------------------------------------------------------
# 1. create_news_item: draft defaults
# ---------------------------------------------------------------------------


async def test_create_lands_as_draft():
    """create_news_item must set is_active=False and provenance_source='admin_curated'."""
    from dhanradar.news.service import create_news_item

    db = AsyncMock()
    captured = {}

    def _capture_add(row):
        captured["row"] = row

    db.add = MagicMock(side_effect=_capture_add)
    db.refresh = AsyncMock()

    await create_news_item(
        db,
        title="AMFI monthly SIP data hits record",
        source="AMFI",
        canonical_url="https://amfiindia.com/sip-data",
        category="mutual_funds",
    )

    row = captured["row"]
    assert row.is_active is False, "New items must be drafts"
    assert row.provenance_source == "admin_curated"
    db.flush.assert_called_once()
    db.commit.assert_called_once()


async def test_create_published_at_defaults_to_now():
    """When published_at is not supplied, it should default to ~now (UTC)."""
    from dhanradar.news.service import create_news_item

    db = AsyncMock()
    captured = {}

    def _capture_add(row):
        captured["row"] = row

    db.add = MagicMock(side_effect=_capture_add)
    db.refresh = AsyncMock()

    before = datetime.now(UTC)
    await create_news_item(
        db,
        title="SEBI circular on expense ratios",
        source="SEBI",
        canonical_url="https://sebi.gov.in/circular/001",
        category="regulation",
    )
    after = datetime.now(UTC)

    row = captured["row"]
    assert before <= row.published_at <= after, (
        f"published_at {row.published_at} should be between {before} and {after}"
    )


async def test_create_honours_explicit_published_at():
    """When published_at is explicitly supplied, it must be stored as-is."""
    from dhanradar.news.service import create_news_item

    db = AsyncMock()
    captured = {}

    def _capture_add(row):
        captured["row"] = row

    db.add = MagicMock(side_effect=_capture_add)
    db.refresh = AsyncMock()

    explicit_ts = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    await create_news_item(
        db,
        title="AMFI AUM data",
        source="AMFI",
        canonical_url="https://amfiindia.com/aum",
        category="mutual_funds",
        published_at=explicit_ts,
    )

    assert captured["row"].published_at == explicit_ts


# ---------------------------------------------------------------------------
# 2. Duplicate canonical_url → DuplicateUrlError
# ---------------------------------------------------------------------------


async def test_duplicate_url_raises():
    """IntegrityError from flush must be caught and re-raised as DuplicateUrlError."""
    from dhanradar.news.service import DuplicateUrlError, create_news_item

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock(side_effect=sqlalchemy.exc.IntegrityError("dup", {}, None))
    db.rollback = AsyncMock()

    with pytest.raises(DuplicateUrlError):
        await create_news_item(
            db,
            title="Duplicate title",
            source="AMFI",
            canonical_url="https://amfiindia.com/existing",
            category="mutual_funds",
        )

    db.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Advisory title screen
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "Buy these 5 funds now",
        "Investors should avoid mid-caps",
        "Strong buy signals everywhere",
        "HOLD your SIP — market commentary",  # "HOLD" is advisory
        "Caution: sector rotation underway",
        "Why you should sell now",
    ],
)
async def test_advisory_titles_rejected(title: str):
    """Titles containing advisory verbs must raise ValueError('advisory_title_rejected')."""
    from dhanradar.news.service import create_news_item

    db = AsyncMock()
    with pytest.raises(ValueError, match="advisory_title_rejected"):
        await create_news_item(
            db,
            title=title,
            source="Source",
            canonical_url="https://example.com/article",
            category="mutual_funds",
        )


@pytest.mark.parametrize(
    "title",
    [
        "AMFI monthly SIP data hits record",
        "SEBI circular on expense ratios",
        "Shareholding pattern disclosures Q1 2026",  # "hold" substring NOT word-bounded
        "RBI keeps repo rate unchanged for third time",  # no advisory verb
        "Nifty 50 crosses 25,000 milestone",
        "Tax treatment of debt mutual fund gains post-2023",
    ],
)
async def test_benign_titles_pass(title: str):
    """Titles with no advisory verbs must not raise ValueError."""
    from dhanradar.news.service import create_news_item

    db = AsyncMock()
    captured = {}

    def _capture_add(row):
        captured["row"] = row

    db.add = MagicMock(side_effect=_capture_add)
    db.refresh = AsyncMock()

    # Should not raise.
    await create_news_item(
        db,
        title=title,
        source="Source",
        canonical_url=f"https://example.com/{hash(title)}",
        category="mutual_funds",
    )
    assert "row" in captured


# ---------------------------------------------------------------------------
# 4. Empty / whitespace field validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"title": ""},
        {"title": "   "},
        {"source": ""},
        {"source": "  "},
        {"canonical_url": ""},
        {"category": ""},
        {"scope": "  "},
    ],
)
async def test_empty_fields_rejected(kwargs: dict):
    """Empty or whitespace-only required string fields must raise ValueError('empty_field: ...')."""
    from dhanradar.news.service import create_news_item

    db = AsyncMock()
    defaults = dict(
        title="Safe title",
        source="SEBI",
        canonical_url="https://sebi.gov.in/ok",
        category="regulation",
    )
    defaults.update(kwargs)

    with pytest.raises(ValueError, match="empty_field:"):
        await create_news_item(db, **defaults)


# ---------------------------------------------------------------------------
# 5. Invalid URL scheme
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_url",
    [
        "ftp://example.com/article",
        "javascript:alert(1)",
        "//example.com/no-scheme",
        "example.com/no-scheme",
        "file:///etc/passwd",
    ],
)
async def test_invalid_url_scheme_rejected(bad_url: str):
    """canonical_url must start with http:// or https:// else ValueError('invalid_url')."""
    from dhanradar.news.service import create_news_item

    db = AsyncMock()
    with pytest.raises(ValueError, match="invalid_url"):
        await create_news_item(
            db,
            title="Safe title",
            source="SEBI",
            canonical_url=bad_url,
            category="regulation",
        )


# ---------------------------------------------------------------------------
# 6. update_news_item: partial update + advisory screen
# ---------------------------------------------------------------------------


async def test_update_applies_partial_fields():
    """update_news_item applies only the supplied kwargs."""
    from dhanradar.news.service import update_news_item

    row = _make_row(title="Old title", is_active=False)
    db = _db_with_row(row)
    db.refresh = AsyncMock()

    await update_news_item(db, row.id, title="New safe title", is_active=True)

    assert row.title == "New safe title"
    assert row.is_active is True
    db.commit.assert_called_once()


async def test_update_rejects_advisory_title():
    """update_news_item must enforce advisory screen when title is provided."""
    from dhanradar.news.service import update_news_item

    row = _make_row(title="Safe old title")
    db = _db_with_row(row)

    with pytest.raises(ValueError, match="advisory_title_rejected"):
        await update_news_item(db, row.id, title="Strong buy: 3 funds to watch")


async def test_update_duplicate_url_raises():
    """IntegrityError from flush during update → DuplicateUrlError."""
    from dhanradar.news.service import DuplicateUrlError, update_news_item

    row = _make_row()
    db = _db_with_row(row)
    db.flush = AsyncMock(side_effect=sqlalchemy.exc.IntegrityError("dup", {}, None))
    db.rollback = AsyncMock()

    with pytest.raises(DuplicateUrlError):
        await update_news_item(db, row.id, canonical_url="https://example.com/taken")

    db.rollback.assert_called_once()


async def test_update_rejects_explicit_none():
    """Explicit None must raise ValueError('null_field: ...') — never fall through
    to the NOT-NULL IntegrityError (which would mislabel the error as a 409)."""
    from dhanradar.news.service import update_news_item

    db = AsyncMock()
    with pytest.raises(ValueError, match="null_field: title"):
        await update_news_item(db, str(uuid.uuid4()), title=None)
    db.execute.assert_not_called()


async def test_update_rejects_unknown_field():
    """Fields outside the PATCH whitelist must raise ValueError('unknown_field: ...')."""
    from dhanradar.news.service import update_news_item

    db = AsyncMock()
    with pytest.raises(ValueError, match="unknown_field: provenance_source"):
        await update_news_item(db, str(uuid.uuid4()), provenance_source="rss")
    db.execute.assert_not_called()


async def test_update_strips_string_fields():
    """String fields are stored stripped, matching create_news_item."""
    from dhanradar.news.service import update_news_item

    row = _make_row(title="Old title")
    db = _db_with_row(row)
    db.refresh = AsyncMock()

    await update_news_item(db, row.id, title="  New safe title  ")

    assert row.title == "New safe title"


# ---------------------------------------------------------------------------
# 7. update_news_item: unknown id → KeyError
# ---------------------------------------------------------------------------


async def test_update_unknown_id_raises_keyerror():
    """update_news_item with a non-existent id must raise KeyError."""
    from dhanradar.news.service import update_news_item

    db = _db_with_no_row()
    with pytest.raises(KeyError):
        await update_news_item(db, str(uuid.uuid4()), title="New title")


# ---------------------------------------------------------------------------
# 8. delete_news_item: unknown id → KeyError
# ---------------------------------------------------------------------------


async def test_delete_unknown_id_raises_keyerror():
    """delete_news_item with a non-existent id must raise KeyError."""
    from dhanradar.news.service import delete_news_item

    db = _db_with_no_row()
    with pytest.raises(KeyError):
        await delete_news_item(db, str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# 9. admin_list_news: no recency cutoff, scope/is_active filters
# ---------------------------------------------------------------------------


async def test_admin_list_returns_inactive_items():
    """admin_list_news must return inactive items (no is_active filter by default)."""
    from dhanradar.news.service import admin_list_news

    old_inactive = _make_row(
        is_active=False,
        published_at=datetime.now(UTC) - timedelta(days=60),
    )
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [old_inactive]
    db.execute = AsyncMock(return_value=mock_result)

    rows = await admin_list_news(db)
    assert len(rows) == 1
    assert rows[0].is_active is False


async def test_admin_list_scope_filter_applied():
    """admin_list_news passes scope filter into the query WHERE clause."""
    from dhanradar.news.service import admin_list_news

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    await admin_list_news(db, scope="equity")

    call_args = db.execute.call_args[0][0]
    compiled = str(call_args.compile(compile_kwargs={"literal_binds": False}))
    assert "scope" in compiled, "Scope filter must appear in the compiled query"


async def test_admin_list_is_active_filter_applied():
    """admin_list_news passes is_active filter into the query WHERE clause."""
    from dhanradar.news.service import admin_list_news

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    await admin_list_news(db, is_active=True)

    call_args = db.execute.call_args[0][0]
    compiled = str(call_args.compile(compile_kwargs={"literal_binds": False}))
    assert "is_active" in compiled, "is_active filter must appear in the compiled query"


async def test_admin_list_no_recency_cutoff():
    """admin_list_news must NOT apply a published_at cutoff filter."""
    from dhanradar.news.service import admin_list_news

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    await admin_list_news(db)

    call_args = db.execute.call_args[0][0]
    compiled = str(call_args.compile(compile_kwargs={"literal_binds": False}))
    # The public list_news adds ">= cutoff"; admin_list_news must not add any
    # cutoff comparison — check that there is no "published_at >=" in the query.
    assert ">=" not in compiled, (
        "admin_list_news must not add a recency cutoff; found '>=' in compiled query"
    )
