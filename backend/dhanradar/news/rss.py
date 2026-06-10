"""
DhanRadar — Sanctioned RSS feed adapter for news ingestion (B56).

Governance:
  - SANCTIONED SOURCES ONLY (B56-f5 closed): feeds listed in _FEED_REGISTRY have
    been evaluated for redistribution acceptability. RBI explicitly publishes and
    documents these URLs on rbi.org.in/Scripts/rss.aspx for syndication.
  - HEADLINE + SOURCE + REAL ITEM URL + FEED published_at + CATEGORY ONLY.
    Article body/excerpt is NEVER fetched or stored (copyright compliance).
  - URL LIVENESS: each item's canonical_url is HEAD-checked before it is accepted.
    Non-2xx responses are skipped at ingest, so dead links never reach the UI.
  - MF RELEVANCE FILTER: DhanRadar is MF-first. Each feed entry in _FEED_REGISTRY
    may carry a `keywords` list; when set, only items whose title contains at least
    one keyword (case-insensitive) are accepted. Items with no keyword match are
    silently dropped — they are not MF-relevant for this platform.
    For RBI feeds, monetary-policy items (repo rate, CPI, inflation) are included
    because they directly affect debt-fund and liquid-fund performance.
  - GRACEFUL DEGRADE: any feed-level fetch failure returns [] and is logged; caller
    (tasks/news.py) falls back to curated seed. No task crash, no 500 on the endpoint.
  - PROVENANCE: provenance_source is set to the feed URL so every DB row is traceable.

Source registry rationale:
  RBI press releases / notifications: government institution; explicitly provides RSS
  for syndication (rbi.org.in/Scripts/rss.aspx); content is factual regulatory
  announcements (informational, not advisory); SEBI educational boundary satisfied.
  Headline + link only = standard RSS aggregation.
  MF relevance gate: RBI publishes mostly banking/forex/G-Sec content. Only items
  matching `_RBI_MF_KEYWORDS` (mutual funds, AMFI, SIP, NAV, monetary policy) are
  retained; pure-banking items are dropped.

  SEBI: sebi.gov.in RSS URL was 404 on 2026-06-10 fetch — DISABLED in registry.
  AMFI: no public RSS feed located — SKIP.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from dhanradar.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MF-relevance keyword filter
# ---------------------------------------------------------------------------
# DhanRadar is an MF-first platform. RBI publishes broad regulatory/macro content
# (banking, forex, G-Secs, T-bills, NBFCs) that is NOT relevant to mutual fund
# investors. Only items matching at least one keyword below pass the relevance gate.
#
# Two groups:
#   _MF_KEYWORDS  — direct MF-specific terms → category promoted to "mutual_funds"
#   _MACRO_KEYWORDS — monetary-policy terms relevant to debt/liquid fund investors
#                     → category stays "macro" (as-configured in registry)
#
# Items matching neither group are dropped silently (not stored, not served).
# ---------------------------------------------------------------------------
_MF_KEYWORDS: frozenset[str] = frozenset(
    {
        "mutual fund",
        "mutual funds",
        "amfi",
        "scheme",
        "sip",
        "nav",
        "systematic investment",
        "open-ended",
        "closed-ended",
        "fund of funds",
        "fund manager",
        "aum",
        "asset management",
        "sebi/mutual",
        "category iii",
        "alternative investment fund",
        "aif",
        "portfolio management",
        "pms",
        "etf",
        "exchange traded fund",
        "index fund",
        "hybrid fund",
        "debt fund",
        "liquid fund",
        "overnight fund",
        "gilt fund",
        "equity fund",
        "balanced fund",
        "folio",
        "redemption",       # MF redemption (vs SGB premature redemption — filtered below)
        "new fund offer",
        "dividend",         # MF dividend re-categorisation
        "growth option",
        "direct plan",
        "regular plan",
        "expense ratio",
        "total expense ratio",
        "sebi (mutual fund",
        "sebi (mf)",
    }
)

_MACRO_KEYWORDS: frozenset[str] = frozenset(
    {
        "repo rate",
        "reverse repo",
        "monetary policy",
        "mpc",
        "monetary policy committee",
        "inflation",
        "cpi",
        "wpi",
        "interest rate",
        "rate cut",
        "rate hike",
        "liquidity",
        "overnight rate",
        "crr",
        "slr",
        "cash reserve ratio",
        "statutory liquidity ratio",
        "rbi policy",
        "policy statement",
        "policy rate",
    }
)


def _is_mf_relevant(title: str) -> tuple[bool, str | None]:
    """Return (True, override_category) when the title passes the MF relevance gate.

    Returns (False, None) for items that should be dropped.

    override_category is "mutual_funds" when direct MF keywords match, else None
    (caller keeps the registry-configured category, e.g. "macro").

    Exclusion guard: titles that contain SGB (Sovereign Gold Bond) are excluded
    even if they also contain "redemption" — SGB is not a mutual fund product.
    """
    lower = title.lower()

    # Hard exclusion: SGB premature-redemption items are RBI sovereign-bond items
    # and should not surface on a MF platform even if they contain "redemption".
    if "sovereign gold bond" in lower or " sgb " in lower or lower.startswith("sgb "):
        return False, None

    for kw in _MF_KEYWORDS:
        if kw in lower:
            return True, "mutual_funds"

    for kw in _MACRO_KEYWORDS:
        if kw in lower:
            return True, None  # keep registry category ("macro")

    return False, None

# ---------------------------------------------------------------------------
# Sanctioned-source registry
# ---------------------------------------------------------------------------
# Each entry:
#   url       : the RSS feed URL
#   source    : display name shown in the UI (never body/excerpt)
#   category  : canonical category label (regulation/macro/mutual_funds/market)
#   scope     : "market" (the only scope currently served)
#   enabled   : False = permanently skip (feed down or ToS unconfirmed)
# ---------------------------------------------------------------------------
_FEED_REGISTRY: list[dict] = [
    {
        "url": "https://rbi.org.in/pressreleases_rss.xml",
        "source": "RBI",
        "category": "macro",
        "scope": "market",
        "enabled": True,
        # MF relevance filter applied at item level via _is_mf_relevant().
    },
    {
        "url": "https://rbi.org.in/notifications_rss.xml",
        "source": "RBI",
        "category": "regulation",
        "scope": "market",
        "enabled": True,
        # MF relevance filter applied at item level via _is_mf_relevant().
    },
    # SEBI RSS — 404 confirmed 2026-06-10; disabled until URL is re-verified live.
    {
        "url": "https://www.sebi.gov.in/sebi_data/rss/rss_sebi_en.xml",
        "source": "SEBI",
        "category": "regulation",
        "scope": "market",
        "enabled": False,
    },
]


def _parse_published_at(entry: feedparser.FeedParserDict) -> datetime | None:
    """Extract and normalise a timezone-aware published datetime from an RSS entry.

    Tries `published_parsed` (struct_time set by feedparser), then falls back to
    parsing the raw `published` string via email.utils.  Returns None on failure
    so the caller can skip the item rather than storing a wrong timestamp.
    """
    try:
        if entry.get("published_parsed"):
            import calendar

            ts = calendar.timegm(entry.published_parsed)
            return datetime.fromtimestamp(ts, tz=UTC)
    except Exception:
        pass

    try:
        raw = entry.get("published") or entry.get("updated") or ""
        if raw:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
    except Exception:
        pass

    return None


async def _head_check(client: httpx.AsyncClient, url: str) -> bool:
    """Return True when the URL responds with a 2xx status (liveness check).

    Uses a HEAD request to minimise bandwidth.  Treats connection errors and
    timeouts as non-2xx (the link is considered dead for this ingest cycle).
    """
    try:
        r = await client.head(
            url,
            follow_redirects=True,
            timeout=settings.NEWS_URL_HEAD_TIMEOUT_S,
        )
        return r.is_success
    except Exception as exc:
        logger.debug("news.rss.head_check: %s → skipped (%s)", url, exc)
        return False


async def fetch_feed(feed_meta: dict) -> list[dict]:
    """Fetch one RSS feed and return a list of canonical news-item dicts.

    Each dict has keys matching the service.upsert_rss_news() contract:
        scope, category, title, source, canonical_url, published_at,
        provenance_source.

    Returns [] on any fetch or parse error (graceful degrade).
    """
    feed_url: str = feed_meta["url"]
    source: str = feed_meta["source"]
    category: str = feed_meta["category"]
    scope: str = feed_meta["scope"]

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "DhanRadar/1.0 (+https://dhanradar.com)"},
            timeout=settings.NEWS_FEED_FETCH_TIMEOUT_S,
        ) as client:
            resp = await client.get(feed_url)
            if not resp.is_success:
                logger.warning(
                    "news.rss.fetch: %s returned HTTP %s — skipping feed",
                    feed_url,
                    resp.status_code,
                )
                return []

            raw_text = resp.text

        parsed = feedparser.parse(raw_text)
        if parsed.bozo and not parsed.entries:
            logger.warning(
                "news.rss.parse: %s malformed feed (bozo=%s) — skipping",
                feed_url,
                parsed.bozo_exception,
            )
            return []

        items: list[dict] = []

        async with httpx.AsyncClient(
            headers={"User-Agent": "DhanRadar/1.0 (+https://dhanradar.com)"},
            timeout=settings.NEWS_URL_HEAD_TIMEOUT_S,
        ) as head_client:
            for entry in parsed.entries:
                link: str = (entry.get("link") or "").strip()
                title: str = (entry.get("title") or "").strip()

                if not link or not title:
                    logger.debug(
                        "news.rss.entry: missing link or title in %s — skip", feed_url
                    )
                    continue

                published_at = _parse_published_at(entry)
                if published_at is None:
                    logger.debug(
                        "news.rss.entry: no parseable date for %s — skip", link
                    )
                    continue

                # Normalise RBI http:// → https:// (feed publishes http links but
                # the server only responds on HTTPS; http returns 404 universally).
                if link.startswith("http://www.rbi.org.in/"):
                    link = "https://www.rbi.org.in/" + link[len("http://www.rbi.org.in/"):]

                # MF relevance gate — applied BEFORE HEAD check to avoid network
                # round-trips for items we will discard regardless.
                relevant, override_category = _is_mf_relevant(title)
                if not relevant:
                    logger.debug(
                        "news.rss.relevance: '%s' — not MF relevant, skipped", title[:80]
                    )
                    continue

                # Use overridden category when the item directly matches MF keywords.
                effective_category = override_category if override_category else category

                # URL liveness check — dead links are skipped at ingest.
                if not await _head_check(head_client, link):
                    logger.info(
                        "news.rss.liveness: %s failed HEAD check — skipped", link
                    )
                    continue

                items.append(
                    {
                        "scope": scope,
                        "category": effective_category,
                        "title": title,
                        "source": source,
                        "canonical_url": link,
                        "published_at": published_at,
                        "provenance_source": feed_url,
                    }
                )

        logger.info(
            "news.rss.fetch: %s → %d items (after liveness filter)",
            feed_url,
            len(items),
        )
        return items

    except Exception:
        logger.exception(
            "news.rss.fetch: unhandled error fetching %s — returning []", feed_url
        )
        return []


async def fetch_all_feeds() -> list[dict]:
    """Fetch all enabled sanctioned feeds and return the combined item list.

    Each feed is fetched independently; a failure on one feed does not affect
    the others.  Returns [] when all feeds fail (caller falls back to curated seed).
    """
    enabled = [f for f in _FEED_REGISTRY if f.get("enabled")]
    if not enabled:
        logger.warning("news.rss: no enabled feeds in registry — returning []")
        return []

    results = await asyncio.gather(
        *[fetch_feed(f) for f in enabled],
        return_exceptions=False,
    )

    all_items: list[dict] = []
    for items in results:
        all_items.extend(items)

    logger.info("news.rss.fetch_all: %d total items from %d feed(s)", len(all_items), len(enabled))
    return all_items
