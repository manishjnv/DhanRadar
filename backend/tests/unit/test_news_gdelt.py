"""
Unit tests for the GDELT DOC 2.0 news adapter (B56-f5) — no live network.

Covers:
  - canonical mapping (title / source / canonical_url / published_at /
    provenance_source="gdelt"), against a recorded fixture
  - V2Tone / tone / sentiment / body is NEVER carried into the canonical dict
  - malformed / empty / non-dict response → [] (no raise)
  - HTTP 429 path returns [] after the single retry (get called twice)
  - the MF relevance filter drops an off-topic item
  - fetch_and_upsert_gdelt_news: a GDELT item lands once; a duplicate
    canonical_url updates (ON CONFLICT) rather than duplicating; is_active is
    never flipped on update (B56-f4)

asyncio_mode = "auto" (pyproject.toml) — async tests need no decorator.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from dhanradar.news import gdelt

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "gdelt"


def _fixture(name: str) -> dict:
    return json.loads((_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


# The exact canonical keys the service upsert contract expects — nothing else.
_EXPECTED_KEYS = {
    "scope",
    "category",
    "title",
    "source",
    "canonical_url",
    "published_at",
    "provenance_source",
}


# ---------------------------------------------------------------------------
# Fake httpx transport (no network)
# ---------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, status_code: int, body: object, *, raise_on_json: bool = False):
        self.status_code = status_code
        self._body = body
        self._raise_on_json = raise_on_json

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> object:
        if self._raise_on_json:
            raise ValueError("malformed JSON")
        return self._body


class _FakeClient:
    """Async stand-in for httpx.AsyncClient: replays a queue of responses."""

    def __init__(self, responses: list[_FakeResponse]):
        self._responses = responses
        self.calls = 0

    async def get(self, url, params=None):  # noqa: ANN001
        self.calls += 1
        idx = min(self.calls - 1, len(self._responses) - 1)
        return self._responses[idx]

    async def aclose(self) -> None:
        return None


# ---------------------------------------------------------------------------
# _parse_seendate
# ---------------------------------------------------------------------------
def test_parse_seendate_compact_utc():
    dt = gdelt._parse_seendate("20260621T123000Z")
    assert dt == datetime(2026, 6, 21, 12, 30, 0, tzinfo=UTC)
    assert dt.tzinfo is not None  # tz-aware


def test_parse_seendate_bare_variant_and_garbage():
    assert gdelt._parse_seendate("20260621123000") == datetime(2026, 6, 21, 12, 30, 0, tzinfo=UTC)
    assert gdelt._parse_seendate("not-a-date") is None
    assert gdelt._parse_seendate("") is None
    assert gdelt._parse_seendate(None) is None


# ---------------------------------------------------------------------------
# _map_articles — canonical mapping + tone discard + relevance + malformed
# ---------------------------------------------------------------------------
def test_map_articles_canonical_shape_and_provenance():
    items = gdelt._map_articles(_fixture("doc_artlist"))
    # 2 relevant (MF + macro); off-topic cricket + empty-title item dropped.
    assert len(items) == 2

    mf = items[0]
    assert mf["title"].startswith("Mutual fund inflows")
    assert mf["source"] == "economictimes.indiatimes.com"          # domain
    assert mf["canonical_url"].startswith("https://economictimes")  # the article URL
    assert mf["provenance_source"] == "gdelt"
    assert mf["scope"] == "market"
    assert mf["category"] == "mutual_funds"                          # MF keyword override
    assert isinstance(mf["published_at"], datetime)
    assert mf["published_at"].tzinfo is not None

    macro = items[1]
    assert "repo rate" in macro["title"].lower()
    assert macro["category"] == "market"                            # macro keeps base category


def test_v2tone_and_sentiment_never_carried():
    items = gdelt._map_articles(_fixture("doc_artlist"))
    for item in items:
        assert set(item.keys()) == _EXPECTED_KEYS, "only headline metadata may be stored"
        # explicit: no tone / sentiment / body fields leak through
        for banned in ("tone", "V2Tone", "v2tone", "sentiment", "body", "socialimage"):
            assert banned not in item


def test_relevance_filter_drops_off_topic():
    payload = {
        "articles": [
            {
                "url": "https://example.com/film/star-buys-bungalow.html",
                "title": "Film star buys a sea-facing bungalow in Mumbai",
                "seendate": "20260621T123000Z",
                "domain": "example.com",
            }
        ]
    }
    assert gdelt._map_articles(payload) == []  # no MF/macro keyword → dropped


def test_malformed_and_empty_payloads_return_empty_list():
    assert gdelt._map_articles({}) == []
    assert gdelt._map_articles({"articles": []}) == []
    assert gdelt._map_articles({"articles": "nope"}) == []
    assert gdelt._map_articles(None) == []
    # article missing url / title / seendate → skipped, no raise
    assert gdelt._map_articles({"articles": [{"url": "https://x.com/a"}]}) == []
    assert gdelt._map_articles({"articles": [{"title": "Mutual fund news"}]}) == []


# ---------------------------------------------------------------------------
# fetch_gdelt_news — network paths (fake client, no live calls)
# ---------------------------------------------------------------------------
async def test_fetch_happy_path_maps_fixture():
    client = _FakeClient([_FakeResponse(200, _fixture("doc_artlist"))])
    items = await gdelt.fetch_gdelt_news(client=client)
    assert len(items) == 2
    assert all(i["provenance_source"] == "gdelt" for i in items)
    assert client.calls == 1


async def test_fetch_429_returns_empty_after_single_retry(monkeypatch):
    # Avoid real backoff sleep.
    monkeypatch.setattr(gdelt.asyncio, "sleep", AsyncMock())
    client = _FakeClient([_FakeResponse(429, {}), _FakeResponse(429, {})])

    items = await gdelt.fetch_gdelt_news(client=client)

    assert items == []
    assert client.calls == 2          # initial attempt + one retry, then give up
    gdelt.asyncio.sleep.assert_awaited_once()


async def test_fetch_non_200_returns_empty():
    client = _FakeClient([_FakeResponse(503, {})])
    assert await gdelt.fetch_gdelt_news(client=client) == []


async def test_fetch_malformed_json_returns_empty():
    client = _FakeClient([_FakeResponse(200, None, raise_on_json=True)])
    assert await gdelt.fetch_gdelt_news(client=client) == []


# ---------------------------------------------------------------------------
# fetch_and_upsert_gdelt_news — upsert lands once, duplicate updates
# ---------------------------------------------------------------------------
async def test_upsert_gdelt_lands_once_and_duplicate_updates():
    """A GDELT item upserts; a duplicate canonical_url goes through the SAME
    ON CONFLICT (canonical_url) DO UPDATE path (DB-level dedup) rather than
    inserting a second row. provenance 'gdelt' is on the values; is_active is
    never flipped on update (B56-f4)."""
    from sqlalchemy.dialects import postgresql

    from dhanradar.news import service as svc

    same_url = "https://economictimes.indiatimes.com/mf/x.cms"
    items = [
        {
            "scope": "market",
            "category": "mutual_funds",
            "title": "Mutual fund inflows rise",
            "source": "economictimes.indiatimes.com",
            "canonical_url": same_url,
            "published_at": datetime(2026, 6, 21, tzinfo=UTC),
            "provenance_source": "gdelt",
        },
        {
            "scope": "market",
            "category": "mutual_funds",
            "title": "Mutual fund inflows rise (updated)",
            "source": "economictimes.indiatimes.com",
            "canonical_url": same_url,  # duplicate → ON CONFLICT updates
            "published_at": datetime(2026, 6, 21, tzinfo=UTC),
            "provenance_source": "gdelt",
        },
    ]

    db = AsyncMock()
    with patch("dhanradar.news.gdelt.fetch_gdelt_news", new=AsyncMock(return_value=items)):
        count = await svc.fetch_and_upsert_gdelt_news(db)

    # Both rows submitted; DB ON CONFLICT collapses them to one stored row.
    assert count == 2
    assert db.execute.call_count == 2
    db.commit.assert_called_once()

    compiled = str(db.execute.call_args[0][0].compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT" in compiled.upper()
    assert "provenance_source" in compiled  # provenance column carried (value bound)
    set_clause = compiled.split("DO UPDATE SET", 1)[1]
    assert "is_active" not in set_clause, "ingestion must not flip is_active (B56-f4)"
    assert "updated_at" in set_clause


async def test_upsert_gdelt_empty_returns_zero_no_commit():
    from dhanradar.news import service as svc

    db = AsyncMock()
    with patch("dhanradar.news.gdelt.fetch_gdelt_news", new=AsyncMock(return_value=[])):
        count = await svc.fetch_and_upsert_gdelt_news(db)

    assert count == 0
    db.execute.assert_not_called()
    db.commit.assert_not_called()
