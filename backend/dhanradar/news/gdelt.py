"""
DhanRadar — Sanctioned GDELT DOC 2.0 adapter for news ingestion (B56-f5).

Governance (mirrors news.rss):
  - SANCTIONED SOURCE (newly added, B56-f5): GDELT DOC 2.0 is a free, no-key news
    INDEX whose licence explicitly permits "unlimited and unrestricted use for any
    academic, commercial, or governmental use … without fee" (attribution to
    gdeltproject.org required at the display layer). Evaluated VPS-reachable from
    KVM4, unlike the publisher RSS feeds which are IP-blocked from the cloud box
    (docs/research/mood-data-sourcing-2026-06-21.md §4).
  - HEADLINE + SOURCE DOMAIN + ARTICLE URL + seendate ONLY. Article body/excerpt is
    NEVER fetched or stored. GDELT's own V2Tone / sentiment fields are DISCARDED at
    ingestion (stack-lock: sentiment is computed in-house later by the governed AI
    gateway, never sourced here).
  - MF RELEVANCE: every item runs through the SAME `_is_mf_relevant` gate the RSS
    path uses (imported, not duplicated) before it is returned.
  - GRACEFUL DEGRADE: any fetch / parse failure returns [] and is logged; one retry
    on HTTP 429 (the only failure GDELT showed under normal cadence). Never raises.
  - PROVENANCE: provenance_source is "gdelt" on every row so each is auditable.

NOTE on date parsing: `_parse_published_at` in news.rss is shaped for feedparser
RSS entries (struct_time / RFC2822). GDELT's `seendate` is the compact basic format
`YYYYMMDDTHHMMSSZ`, which that helper cannot parse — so a small dedicated
`_parse_seendate` is used here. The genuinely reusable, format-agnostic
`_is_mf_relevant` IS imported and reused.

NOT yet smoke-tested against the live API (tested against a recorded fixture only) —
pending sanctioned-source review before it lands.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from dhanradar.config import settings

# Reused, format-agnostic relevance gate (import, do not duplicate — B56-f5).
from dhanradar.news.rss import _is_mf_relevant

logger = logging.getLogger(__name__)

# Real UA — mirrors the RSS adapter (GDELT rejects/limits bare agents).
_USER_AGENT = "DhanRadar/1.0 (+https://dhanradar.com)"

_GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# Market / MF query, India + English filtered. Exact string is reported for review.
_GDELT_QUERY = (
    '(nifty OR sensex OR "mutual fund" OR "stock market" OR SEBI OR AMFI) '
    "sourcecountry:india sourcelang:english"
)
_GDELT_PARAMS: dict[str, str] = {
    "query": _GDELT_QUERY,
    "mode": "ArtList",
    "format": "json",
    "timespan": "24h",
    "maxrecords": "75",
    "sort": "datedesc",
}

_SCOPE = "market"
_CATEGORY = "market"
_PROVENANCE = "gdelt"

# Retry policy: GDELT only 429s under burst-parallel load; one retry suffices.
_MAX_ATTEMPTS = 2
_RETRY_BACKOFF_S = 2.0


def _parse_seendate(raw: object) -> datetime | None:
    """Parse GDELT's `seendate` (compact basic format) to a tz-aware UTC datetime.

    Accepts `YYYYMMDDTHHMMSSZ` (the documented form) and the bare `YYYYMMDDHHMMSS`
    variant. Returns None on anything unparseable so the caller skips the item
    rather than storing a wrong timestamp (mirrors the RSS skip-on-bad-date rule).
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _domain_from_url(url: str) -> str:
    """Best-effort publisher domain from the article URL (fallback when GDELT's
    `domain` field is absent)."""
    try:
        return urlparse(url).netloc
    except Exception:  # noqa: BLE001
        return ""


def _map_articles(payload: object) -> list[dict]:
    """Map a GDELT DOC 2.0 ArtList payload to canonical news-item dicts.

    Output dicts match the service upsert contract EXACTLY:
        {scope, category, title, source, canonical_url, published_at,
         provenance_source}.

    Only headline metadata is carried. GDELT's V2Tone / tone / themes / social
    image / any sentiment or body field is intentionally NOT read. Off-topic
    items are dropped by the shared `_is_mf_relevant` gate.
    """
    if not isinstance(payload, dict):
        return []
    articles = payload.get("articles")
    if not isinstance(articles, list):
        return []

    items: list[dict] = []
    for art in articles:
        if not isinstance(art, dict):
            continue

        url = str(art.get("url") or "").strip()
        title = str(art.get("title") or "").strip()
        if not url or not title:
            continue

        published_at = _parse_seendate(art.get("seendate"))
        if published_at is None:
            continue

        relevant, override_category = _is_mf_relevant(title)
        if not relevant:
            logger.debug("news.gdelt.relevance: '%s' — not MF relevant, skipped", title[:80])
            continue

        source = str(art.get("domain") or "").strip() or _domain_from_url(url)
        if not source:
            continue

        # HEADLINE METADATA ONLY — no body, no tone/V2Tone, no sentiment.
        items.append(
            {
                "scope": _SCOPE,
                "category": override_category or _CATEGORY,
                "title": title,
                "source": source,
                "canonical_url": url,
                "published_at": published_at,
                "provenance_source": _PROVENANCE,
            }
        )

    return items


async def _get_with_retry(client: httpx.AsyncClient) -> dict | None:
    """GET the GDELT endpoint, retrying once on HTTP 429. Returns the parsed JSON
    dict, or None on any non-2xx / request error / malformed body (never raises)."""
    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = await client.get(_GDELT_URL, params=_GDELT_PARAMS)
        except Exception as exc:  # noqa: BLE001 — graceful degrade
            logger.warning("news.gdelt.get: request error — %s", exc)
            return None

        if resp.status_code == 429 and attempt + 1 < _MAX_ATTEMPTS:
            logger.warning("news.gdelt.get: HTTP 429 — retrying once after backoff")
            await asyncio.sleep(_RETRY_BACKOFF_S)
            continue

        if not resp.is_success:
            logger.warning("news.gdelt.get: HTTP %s — giving up", resp.status_code)
            return None

        try:
            parsed = resp.json()
        except Exception as exc:  # noqa: BLE001 — malformed response
            logger.warning("news.gdelt.get: malformed JSON — %s", exc)
            return None
        return parsed if isinstance(parsed, dict) else None

    # All attempts were 429.
    logger.warning("news.gdelt.get: exhausted retries on HTTP 429 — returning none")
    return None


async def fetch_gdelt_news(client: httpx.AsyncClient | None = None) -> list[dict]:
    """Fetch GDELT DOC 2.0 headlines and return canonical news-item dicts.

    Headline + URL + metadata only; V2Tone/sentiment/body are never stored.
    Returns [] on ANY failure (graceful degrade, logged) — never raises, so a
    GDELT outage cannot break the news ingest task or the /news endpoint.

    `client` may be injected (tests pass a fake transport); when None, a real
    httpx client with the DhanRadar UA is constructed and closed here.
    """
    own_client = client is None
    c = client or httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT},
        timeout=settings.NEWS_FEED_FETCH_TIMEOUT_S,
    )
    try:
        payload = await _get_with_retry(c)
    except Exception:
        logger.exception("news.gdelt.fetch: unhandled error — returning []")
        return []
    finally:
        if own_client:
            await c.aclose()

    if payload is None:
        return []

    items = _map_articles(payload)
    logger.info("news.gdelt.fetch: %d MF-relevant items (after relevance filter)", len(items))
    return items
