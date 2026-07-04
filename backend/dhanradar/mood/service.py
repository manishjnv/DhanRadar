"""
DhanRadar — Mood Compass service: fetch → compute → persist → cache → emit.

Signal ingestion is INJECTABLE: the Market Data Adapter providers are stubbed
(B29-class), so `default_fetch_inputs` returns all-missing and the snapshot is
`insufficient_data` until real signals are wired — the pipeline still runs end-to-end.

`mood.snapshot.published` is emitted by `emit_published`: it writes the B26 audit
row for the served regime label, posts the daily public card via the Notification
interface, and is what unblocks the notification mood consumer. All emission steps
are best-effort (a failure never breaks the snapshot).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time as _time_module
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from datetime import time as _time_type
from typing import Any
from zoneinfo import ZoneInfo

from dhanradar.ai_gateway.quality import _ADVISORY_RE
from dhanradar.market_data.breadth import fetch_nifty50_advances_declines_sync
from dhanradar.mood.compute import WEIGHTS, MoodResult, compute_mood, factor_tier
from dhanradar.mood.schemas import MoodHistoryItem, MoodPublic, WhyToday
from dhanradar.scoring.engine.schemas import (
    DISCLAIMER_VERSION,
    DISCLOSURE_BUNDLE,
    NOT_ADVICE,
)

logger = logging.getLogger(__name__)

_LATEST_KEY = "mood:latest"
_WHY_KEY = "mood:why-today"
_EMBED_KEY = "mood:embed"
_TTL_12H = 12 * 3600
MODEL_VERSION = "mood_v1"

# ---------------------------------------------------------------------------
# Human-readable factor labels (GAP d)
# ---------------------------------------------------------------------------

_FACTOR_LABELS: dict[str, str] = {
    "nifty_trend": "Nifty Trend",
    "market_breadth": "Market Breadth",
    "india_vix": "India VIX",
    "fii_flows": "FII Flows",
    "global_indices": "Global Indices",
    "dii_flows": "DII Flows",
    "us_bond_10y": "US 10Y Yield",
    "oil_brent": "Brent Crude",
    "usd_inr": "USD/INR",
    "put_call_ratio": "Put-Call Ratio",
    "news_sentiment": "News Sentiment",
}


def _labelize(keys: list[str]) -> list[str]:
    """Map raw signal keys to human-readable labels; unknown keys pass through unchanged."""
    return [_FACTOR_LABELS.get(k, k) for k in keys]


def _factor_objs(keys: list[str], input_vector: dict | None) -> list[dict]:
    """Build the public {label, tier} factor objects for the driver bars.

    The COARSE 3-way magnitude tier is derived server-side from the persisted
    normalized value (input_vector) and the factor weight — the numeric strength /
    value / weight is NEVER emitted, only the tier string (non-neg #2). A factor
    missing from the input vector falls back to the lowest tier safely.
    """
    iv = input_vector if isinstance(input_vector, dict) else {}
    return [
        {"label": _FACTOR_LABELS.get(k, k), "tier": factor_tier(iv.get(k), WEIGHTS.get(k, 0.0))}
        for k in keys
    ]

# Defense-in-depth advisory screen over the FREE-TEXT commentary before publish — no
# advisory verb may reach a public surface (non-neg #1). We REUSE the AI gateway's
# canonical compiled advisory regex (`_ADVISORY_RE`, imported above) — the exact term list
# QualityValidator screens model output with — rather than a second, NARROWER local copy.
# A narrower copy would silently pass terms the gateway covers (accumulate / book profits /
# overweight / top pick / go long / ...), defeating the defense-in-depth purpose. (B35-e
# review finding; closes the mood half of the B56-f1 _ADVISORY_RE duplication — news/service.py
# still carries its own copy and stays tracked under B56-f1.)


def default_fetch_inputs() -> dict[str, float | None]:
    """Stubbed ingestion — all inputs missing until the Market Data Adapter providers
    are wired (deferred). Returns the 11 keys mapped to None."""
    return {k: None for k in WEIGHTS}


async def compute_and_store(
    *,
    snapshot_date: date,
    snapshot_time: datetime,
    fetch: Callable[[], dict[str, float | None]] = default_fetch_inputs,
    generate_commentary: Callable[[MoodResult], Awaitable[str | None]] | None = None,
) -> MoodResult | None:
    """Run one snapshot. Returns the MoodResult, or None if ALL inputs are missing
    (caller skips + retries).

    `generate_commentary` is an ASYNC, best-effort hook (B35-e): it is awaited only when
    the snapshot's own `commentary_allowed` gate is set (>= 7 signals, confidence >= 0.40)
    and is expected to return the commentary string or None. It must not raise — but we
    still guard it so a hook failure never breaks the snapshot."""
    result = compute_mood(fetch())
    if result is None:
        logger.warning("mood: all inputs missing for %s — skip", snapshot_date)
        return None

    commentary = None
    if result.commentary_allowed and generate_commentary is not None:
        try:
            commentary = await generate_commentary(result)
        except Exception:  # noqa: BLE001 — commentary is best-effort spillover
            logger.warning("mood: commentary generation failed; publishing without it")
        # Never publish commentary that slipped an advisory verb past the model's own
        # guard — drop it and publish the regime label alone (non-neg #1).
        if commentary and _ADVISORY_RE.search(commentary):
            logger.error("mood: commentary contained an advisory verb — withheld")
            commentary = None

    await _persist(result, snapshot_date, snapshot_time, commentary)
    await _cache_latest(result, snapshot_date, commentary)
    await emit_published(result, snapshot_date)
    return result


async def _persist(result: MoodResult, snapshot_date: date, snapshot_time: datetime, commentary: str | None) -> None:
    from sqlalchemy.dialects.postgresql import insert

    from dhanradar.db import TaskSessionLocal
    from dhanradar.models.mood import MarketMood

    values = dict(
        snapshot_date=snapshot_date, snapshot_time=snapshot_time,
        mood_score=result.mood_score, confidence_score=result.confidence_score,
        regime=result.regime, confidence_band=result.confidence_band,
        inputs_available=result.inputs_available, input_vector=result.input_vector,
        contributing_factors=result.contributing_factors,
        contradicting_factors=result.contradicting_factors,
        ai_commentary=commentary, model_used=MODEL_VERSION, data_quality=result.data_quality,
    )
    async with TaskSessionLocal() as db:
        stmt = insert(MarketMood).values(**values).on_conflict_do_update(
            index_elements=["snapshot_date"],
            set_={k: values[k] for k in values if k != "snapshot_date"},
        )
        await db.execute(stmt)
        await db.commit()


def _public_dict(result: MoodResult, snapshot_date: date, commentary: str | None) -> dict:
    return {
        "snapshot_date": snapshot_date.isoformat(),
        "regime": result.regime,
        "confidence_band": result.confidence_band,
        "data_quality": result.data_quality,
        "contributing_factors": _factor_objs(list(result.contributing_factors), result.input_vector),
        "contradicting_factors": _factor_objs(list(result.contradicting_factors), result.input_vector),
        "commentary": commentary,
        "disclosure": DISCLOSURE_BUNDLE,
        "not_advice": NOT_ADVICE,
        "disclaimer_version": DISCLAIMER_VERSION,
    }


async def _cache_latest(result: MoodResult, snapshot_date: date, commentary: str | None) -> None:
    from dhanradar.redis_client import get_redis

    try:
        await get_redis().set(_LATEST_KEY, json.dumps(_public_dict(result, snapshot_date, commentary)), ex=_TTL_12H)
    except Exception:  # noqa: BLE001 — cache is best-effort
        logger.warning("mood: failed to cache mood:latest")


async def emit_published(result: MoodResult, snapshot_date: date) -> None:
    """`mood.snapshot.published`: audit the served regime label (B26) + post the daily
    public card via the Notification interface. Best-effort end to end."""
    # B26 — the regime IS a served educational label; persist its provenance.
    try:
        from dhanradar.compliance import service as compliance_service

        await compliance_service.record_served_label(
            surface="mood",
            label=result.regime,
            model=MODEL_VERSION,
            disclaimer_version=DISCLAIMER_VERSION,
            recommendation_type="mood_regime",
            identifier=snapshot_date.isoformat(),
            confidence_band=result.confidence_band,
        )
    except Exception:  # noqa: BLE001 — audit is fire-and-forget
        logger.exception("mood: audit write failed for %s", snapshot_date)

    # Daily public card (Notification owns delivery; Mood only hands it the copy).
    try:
        from dhanradar.notifications import service as notif_service

        text = (
            f"Market Mood today: {result.regime.replace('_', ' ')} "
            f"({result.confidence_band.replace('_', ' ')} confidence). "
            f"Educational market-regime read, not advice. [{NOT_ADVICE}]"
        )
        await notif_service.post_public_card(text)
    except Exception:  # noqa: BLE001 — delivery is best-effort
        logger.warning("mood: public card post failed for %s", snapshot_date)


# ---------------------------------------------------------------------------
# Public reads (anon).
# ---------------------------------------------------------------------------

def unavailable_public() -> MoodPublic:
    """Return a structured MoodPublic for when no snapshot exists (GAP c).

    Returns regime='data_unavailable' instead of raising 404 so the GET /mood
    endpoint always returns 200 with the disclosure bundle.
    """
    return MoodPublic(
        snapshot_date="",
        snapshot_at=None,
        regime="data_unavailable",
        confidence_band="insufficient_data",
        data_quality="unavailable",
        contributing_factors=[],
        contradicting_factors=[],
        commentary=None,
        disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE,
        disclaimer_version=DISCLAIMER_VERSION,
        trend=None,
    )


def why_today_unavailable() -> WhyToday:
    """Structured WhyToday for when no snapshot exists — returns
    regime='data_unavailable' instead of 404 so the anon /why-today surface always
    renders something compliant (mirrors unavailable_public for GAP c)."""
    return WhyToday(
        snapshot_date="",
        regime="data_unavailable",
        commentary=None,
        contributing_factors=[],
        contradicting_factors=[],
        disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE,
        disclaimer_version=DISCLAIMER_VERSION,
    )


async def _compute_trend(db: Any) -> str | None:
    """Derive a non-numeric trend label from the two most recent snapshots (GAP g / ADR-0023).

    Reads server-side mood_score from the two most recent MarketMood rows.
    Returns 'improving' (diff > +2.0), 'deteriorating' (diff < -2.0),
    'stable' (|diff| ≤ 2.0), or None when fewer than 2 rows exist.
    The numeric diff is never exposed — only the label is returned.
    """
    from sqlalchemy import select

    from dhanradar.models.mood import MarketMood

    rows = (
        await db.scalars(
            select(MarketMood).order_by(MarketMood.snapshot_date.desc()).limit(2)
        )
    ).all()

    if len(rows) < 2:
        return None

    latest_score = float(rows[0].mood_score or 0)
    prior_score = float(rows[1].mood_score or 0)
    diff = latest_score - prior_score

    if diff > 2.0:
        return "improving"
    if diff < -2.0:
        return "deteriorating"
    return "stable"


async def get_latest(db: Any) -> MoodPublic | None:
    """Return the most recent MoodPublic snapshot, or None if no snapshot exists."""
    from sqlalchemy import select

    from dhanradar.models.mood import MarketMood

    row = await db.scalar(select(MarketMood).order_by(MarketMood.snapshot_date.desc()))
    if row is None:
        return None
    trend = await _compute_trend(db)
    return MoodPublic(
        snapshot_date=row.snapshot_date.isoformat(),
        snapshot_at=row.snapshot_time.isoformat() if row.snapshot_time else None,
        regime=row.regime,
        confidence_band=row.confidence_band, data_quality=row.data_quality,
        contributing_factors=_factor_objs(list(row.contributing_factors or []), row.input_vector),
        contradicting_factors=_factor_objs(list(row.contradicting_factors or []), row.input_vector),
        commentary=row.ai_commentary, disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE, disclaimer_version=DISCLAIMER_VERSION,
        trend=trend,
    )


async def get_history(db: Any, days: int) -> list[MoodHistoryItem]:
    from sqlalchemy import select

    from dhanradar.models.mood import MarketMood

    days = max(1, min(days, 365))  # cap per architecture (≤365d)
    rows = (
        await db.scalars(
            select(MarketMood).order_by(MarketMood.snapshot_date.desc()).limit(days)
        )
    ).all()
    return [MoodHistoryItem(snapshot_date=r.snapshot_date.isoformat(), regime=r.regime) for r in rows]


async def get_regime_series(db: Any, from_date: date, to_date: date) -> list[dict]:
    """Return [{date, regime}] from `mood.mood_regime_history` between `from_date`
    and `to_date` inclusive, ordered chronologically.

    Feeds the future per-fund "performance by market phase" consumer
    (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §10.8) — no public endpoint yet (YAGNI,
    the consumer is a later wave). Read-only; never writes.
    """
    from sqlalchemy import select

    from dhanradar.models.mood import MoodRegimeHistory

    rows = (
        await db.scalars(
            select(MoodRegimeHistory)
            .where(
                MoodRegimeHistory.snapshot_date >= from_date,
                MoodRegimeHistory.snapshot_date <= to_date,
            )
            .order_by(MoodRegimeHistory.snapshot_date.asc())
        )
    ).all()
    return [{"date": r.snapshot_date.isoformat(), "regime": r.regime} for r in rows]


async def get_why_today(db: Any) -> WhyToday | None:
    """Return the WhyToday breakdown with human-readable factor labels."""
    from sqlalchemy import select

    from dhanradar.models.mood import MarketMood

    row = await db.scalar(select(MarketMood).order_by(MarketMood.snapshot_date.desc()))
    if row is None:
        return None
    return WhyToday(
        snapshot_date=row.snapshot_date.isoformat(), regime=row.regime,
        commentary=row.ai_commentary,
        contributing_factors=_labelize(list(row.contributing_factors or [])),
        contradicting_factors=_labelize(list(row.contradicting_factors or [])),
        disclosure=DISCLOSURE_BUNDLE, not_advice=NOT_ADVICE,
        disclaimer_version=DISCLAIMER_VERSION,
    )


# ---------------------------------------------------------------------------
# Part A — Live VIX  |  Part B — Market Breadth  (Phase 4)
# Part C — FII/DII Flows + PCR cache (Upstox Analytics, Phase 5)
# ---------------------------------------------------------------------------

_VIX_CACHE_KEY = "signal:vix:last"
_BREADTH_CACHE_KEY = "signal:breadth:last"
_FLOWS_CACHE_KEY = "signal:flows:last"
_TTL_VIX_SEC = 24 * 3600
_TTL_BREADTH_SEC = 3600
_TTL_FLOWS_SEC = _TTL_12H  # 12 h — matches the twice-daily snapshot cadence

_IST = ZoneInfo("Asia/Kolkata")


def _market_open_now() -> bool:
    """Return True if current IST time is Mon–Fri 09:15–15:30."""
    now_ist = datetime.now(_IST)
    if now_ist.weekday() >= 5:
        return False
    t = now_ist.time()
    return _time_type(9, 15) <= t <= _time_type(15, 30)


def _fetch_vix_sync() -> dict:
    import yfinance as yf
    hist = yf.Ticker("^INDIAVIX").history(period="2d")
    if hist.empty or len(hist) < 1:
        raise ValueError("empty VIX response")
    latest = float(hist["Close"].iloc[-1])
    prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else latest
    change_pct = round((latest - prev) / prev * 100, 2) if prev else 0.0
    return {
        "value": round(latest, 2),
        "change_pct": change_pct,
        "fetched_at": datetime.now(UTC).isoformat(),
    }


def _fetch_breadth_sync() -> dict:
    import yfinance as yf
    start = _time_module.monotonic()

    advances, declines = fetch_nifty50_advances_declines_sync()
    ad_ratio = round(advances / max(declines, 1), 3)

    # Also fetch Nifty index pct change — stored in breadth cache for signal_alert task
    nifty_pct = 0.0
    try:
        nifty_hist = yf.Ticker("^NSEI").history(period="2d")
        if not nifty_hist.empty and len(nifty_hist) >= 2:
            n_today = float(nifty_hist["Close"].iloc[-1])
            n_prev = float(nifty_hist["Close"].iloc[-2])
            nifty_pct = round((n_today - n_prev) / n_prev * 100, 2) if n_prev else 0.0
    except Exception:  # noqa: BLE001
        pass

    elapsed_ms = round((_time_module.monotonic() - start) * 1000)
    logger.info("signal.breadth_fetch advances=%d declines=%d ad_ratio=%.3f elapsed_ms=%d",
                advances, declines, ad_ratio, elapsed_ms)

    return {
        "advances": advances,
        "declines": declines,
        "ad_ratio": ad_ratio,
        "nifty_change_pct": nifty_pct,
    }


async def get_vix():  # returns VIXOut but avoids a circular import at module level
    """Fetch India VIX from Yahoo Finance; falls back to Redis cache then hardcoded default."""
    from dhanradar.redis_client import get_redis
    from dhanradar.signal.schemas import VIXOut

    redis = get_redis()

    try:
        data = await asyncio.to_thread(_fetch_vix_sync)
        try:
            await redis.set(_VIX_CACHE_KEY, json.dumps(data), ex=_TTL_VIX_SEC)
        except Exception:  # noqa: BLE001
            pass
        return VIXOut(value=data["value"], change_pct=data["change_pct"], market_open=_market_open_now())
    except Exception as exc:  # noqa: BLE001
        logger.warning("signal.vix_fetch_error: %s", type(exc).__name__)

    try:
        raw = await redis.get(_VIX_CACHE_KEY)
        if raw:
            data = json.loads(raw if isinstance(raw, str) else raw.decode())
            fetched_at = datetime.fromisoformat(data["fetched_at"])
            fresh = (datetime.now(UTC) - fetched_at).total_seconds() < 1800
            return VIXOut(
                value=data["value"],
                change_pct=data["change_pct"],
                market_open=_market_open_now() and fresh,
            )
    except Exception:  # noqa: BLE001
        pass

    return VIXOut(value=18.5, change_pct=0.0, market_open=False)


async def get_breadth():  # returns BreadthOut
    """Derive A/D breadth from Nifty 50 constituents via Yahoo Finance.

    NSE is geo-blocked from KVM4 (HTTP 403), so we use Yahoo Finance tickers.
    This call takes 2–5 s; a background Celery task pre-warms the cache every 15 min.
    """
    from dhanradar.redis_client import get_redis
    from dhanradar.signal.schemas import BreadthOut

    redis = get_redis()

    try:
        data = await asyncio.to_thread(_fetch_breadth_sync)
        try:
            await redis.set(_BREADTH_CACHE_KEY, json.dumps(data), ex=_TTL_BREADTH_SEC)
        except Exception:  # noqa: BLE001
            pass
        return BreadthOut(
            advances=data["advances"],
            declines=data["declines"],
            ad_ratio=data["ad_ratio"],
            market_open=_market_open_now(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("signal.breadth_fetch_error: %s", type(exc).__name__)

    try:
        raw = await redis.get(_BREADTH_CACHE_KEY)
        if raw:
            data = json.loads(raw if isinstance(raw, str) else raw.decode())
            return BreadthOut(
                advances=data["advances"],
                declines=data["declines"],
                ad_ratio=data["ad_ratio"],
                market_open=_market_open_now(),
            )
    except Exception:  # noqa: BLE001
        pass

    return BreadthOut(advances=25, declines=25, ad_ratio=1.0, market_open=False)


async def get_breadth_raw() -> dict:
    """Return the raw breadth dict including ``nifty_change_pct``.

    This is the server-internal counterpart of :func:`get_breadth`.  ``get_breadth``
    returns a :class:`~dhanradar.signal.schemas.BreadthOut` which intentionally omits
    ``nifty_change_pct`` from the public schema; callers that need the Nifty change-% for
    server-side scoring (e.g. ``GET /signal/state``) use this function instead.

    Fallback chain (mirrors ``get_breadth`` exactly):
      1. Live fetch via ``_fetch_breadth_sync`` — result is also written to the Redis cache.
      2. Redis cache (``signal:breadth:last``).
      3. Hard-coded safe defaults: ``advances=25, declines=25, ad_ratio=1.0,
         nifty_change_pct=0.0``.
    """
    from dhanradar.redis_client import get_redis

    redis = get_redis()

    try:
        data = await asyncio.to_thread(_fetch_breadth_sync)
        try:
            await redis.set(_BREADTH_CACHE_KEY, json.dumps(data), ex=_TTL_BREADTH_SEC)
        except Exception:  # noqa: BLE001
            pass
        return data
    except Exception as exc:  # noqa: BLE001
        logger.warning("signal.breadth_raw_fetch_error: %s", type(exc).__name__)

    try:
        raw = await redis.get(_BREADTH_CACHE_KEY)
        if raw:
            return json.loads(raw if isinstance(raw, str) else raw.decode())
    except Exception:  # noqa: BLE001
        pass

    return {
        "advances": 25,
        "declines": 25,
        "ad_ratio": 1.0,
        "nifty_change_pct": 0.0,
    }


async def cache_market_flows(raw_signals: dict) -> None:
    """Write FII/DII flows + PCR from the Upstox snapshot into Redis.

    Best-effort: a Redis failure logs a warning and is swallowed — it must never
    crash the mood pipeline.  Called from tasks/mood.py OUTSIDE the ingestion_run
    context so a cache hiccup does not mark the ingestion run as failed.
    """
    from dhanradar.redis_client import get_redis

    payload = json.dumps({
        "fii_cr": raw_signals.get("fii_flows"),
        "dii_cr": raw_signals.get("dii_flows"),
        "pcr": raw_signals.get("put_call_ratio"),
        "as_of": datetime.now(UTC).isoformat(),
    })
    try:
        await get_redis().set(_FLOWS_CACHE_KEY, payload, ex=_TTL_FLOWS_SEC)
    except Exception:  # noqa: BLE001
        logger.warning("mood: cache_market_flows failed — flows cache not updated")


async def get_flows():  # returns FlowsOut
    """Return the latest cached FII/DII flows + PCR from the Upstox snapshot.

    Populated by the twice-daily compute_mood_snapshot task when
    UPSTOX_ANALYTICS_TOKEN is set.  Returns all-None when the cache is cold
    (token not set, or snapshot not yet run since restart).

    Raw public market data — DOM-allowed (same rule as /vix, /breadth).
    """
    from dhanradar.mood.schemas import FlowsOut
    from dhanradar.redis_client import get_redis

    try:
        raw = await get_redis().get(_FLOWS_CACHE_KEY)
        if raw:
            data = json.loads(raw if isinstance(raw, str) else raw.decode())
            return FlowsOut(**data)
    except Exception:  # noqa: BLE001
        pass

    return FlowsOut(fii_cr=None, dii_cr=None, pcr=None, as_of=None)


async def get_embed_html(db: Any) -> str:
    """Return a self-contained embeddable widget HTML for the Mood Compass (GAP b).

    Read-through Redis cache (key 'mood:embed', TTL 12h).  The HTML is
    inline-styled, contains no external JS/CSS, and MUST NOT expose any
    numeric mood_score or confidence_score (non-neg #2).  Shows the humanized
    regime, confidence band, trend, and the full disclosure bundle + NOT_ADVICE.
    """
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    try:
        cached = await redis.get(_EMBED_KEY)
        if cached:
            return cached if isinstance(cached, str) else cached.decode()
    except Exception:  # noqa: BLE001 — cache miss is fine
        pass

    latest = await get_latest(db)
    pub = latest or unavailable_public()
    trend = pub.trend

    regime_display = pub.regime.replace("_", " ").title()
    band_display = pub.confidence_band.replace("_", " ").title()
    trend_display = trend.replace("_", " ").title() if trend else ""

    contrib_html = ""
    if pub.contributing_factors:
        items = "".join(f"<li>{f.label}</li>" for f in pub.contributing_factors)
        contrib_html = f"<p style='margin:6px 0 2px;font-weight:600;font-size:12px;'>Supporting signals:</p><ul style='margin:0;padding-left:18px;font-size:12px;'>{items}</ul>"

    contra_html = ""
    if pub.contradicting_factors:
        items = "".join(f"<li>{f.label}</li>" for f in pub.contradicting_factors)
        contra_html = f"<p style='margin:6px 0 2px;font-weight:600;font-size:12px;'>Contradicting signals:</p><ul style='margin:0;padding-left:18px;font-size:12px;'>{items}</ul>"

    trend_html = (
        f"<p style='margin:4px 0;font-size:13px;'>Trend: <strong>{trend_display}</strong></p>"
        if trend_display else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DhanRadar Market Mood</title>
</head>
<body style="margin:0;padding:0;background:transparent;">
<article
  role="region"
  aria-label="DhanRadar Market Mood Compass"
  style="font-family:system-ui,sans-serif;max-width:340px;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.07);"
>
  <header>
    <h2 style="margin:0 0 4px;font-size:15px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.05em;">
      Market Mood
    </h2>
    <p style="margin:0 0 8px;font-size:22px;font-weight:700;color:#1e293b;">{regime_display}</p>
  </header>
  <p style="margin:4px 0;font-size:13px;">Confidence: <strong>{band_display}</strong></p>
  {trend_html}
  {contrib_html}
  {contra_html}
  <footer style="margin-top:12px;border-top:1px solid #f1f5f9;padding-top:10px;">
    <p style="margin:0 0 4px;font-size:11px;color:#94a3b8;font-weight:700;">{pub.not_advice}</p>
    <p style="margin:0 0 4px;font-size:10px;color:#94a3b8;">{pub.disclosure}</p>
    <p style="margin:0;font-size:10px;color:#cbd5e1;">Disclaimer version: {pub.disclaimer_version} &middot; <a href="https://dhanradar.com" style="color:#94a3b8;">DhanRadar</a></p>
  </footer>
</article>
</body>
</html>"""

    try:
        await redis.set(_EMBED_KEY, html, ex=_TTL_12H)
    except Exception:  # noqa: BLE001 — cache write is best-effort
        pass

    return html
