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

import json
import logging
import re
from datetime import date, datetime
from typing import Any, Callable, Optional

from dhanradar.mood.compute import WEIGHTS, MoodResult, compute_mood
from dhanradar.mood.schemas import MoodHistoryItem, MoodPublic, WhyToday
from dhanradar.scoring.engine.schemas import (
    DISCLAIMER_VERSION,
    DISCLOSURE_BUNDLE,
    NOT_ADVICE,
)

logger = logging.getLogger(__name__)

_LATEST_KEY = "mood:latest"
_WHY_KEY = "mood:why-today"
_TTL_12H = 12 * 3600
MODEL_VERSION = "mood_v1"

# Defense-in-depth advisory screen over the FREE-TEXT commentary before publish — no
# advisory verb may reach a public surface (non-neg #1). This is the CORE set; the
# versioned, domain-signed taxonomy lives with the AI gateway (B23).
_ADVISORY_RE = re.compile(
    r"\b(strong[\s_]?buy|strong[\s_]?sell|buy|sell|hold|switch|avoid|caution)\b", re.IGNORECASE
)


def default_fetch_inputs() -> dict[str, Optional[float]]:
    """Stubbed ingestion — all inputs missing until the Market Data Adapter providers
    are wired (deferred). Returns the 11 keys mapped to None."""
    return {k: None for k in WEIGHTS}


async def compute_and_store(
    *,
    snapshot_date: date,
    snapshot_time: datetime,
    fetch: Callable[[], dict[str, Optional[float]]] = default_fetch_inputs,
    generate_commentary: Optional[Callable[[MoodResult], Optional[str]]] = None,
) -> Optional[MoodResult]:
    """Run one snapshot. Returns the MoodResult, or None if ALL inputs are missing
    (caller skips + retries)."""
    result = compute_mood(fetch())
    if result is None:
        logger.warning("mood: all inputs missing for %s — skip", snapshot_date)
        return None

    commentary = None
    if result.commentary_allowed and generate_commentary is not None:
        try:
            commentary = generate_commentary(result)
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


async def _persist(result: MoodResult, snapshot_date: date, snapshot_time: datetime, commentary: Optional[str]) -> None:
    from sqlalchemy.dialects.postgresql import insert
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from dhanradar.db import engine
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
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with SessionLocal() as db:
        stmt = insert(MarketMood).values(**values).on_conflict_do_update(
            index_elements=["snapshot_date"],
            set_={k: values[k] for k in values if k != "snapshot_date"},
        )
        await db.execute(stmt)
        await db.commit()


def _public_dict(result: MoodResult, snapshot_date: date, commentary: Optional[str]) -> dict:
    return {
        "snapshot_date": snapshot_date.isoformat(),
        "regime": result.regime,
        "confidence_band": result.confidence_band,
        "data_quality": result.data_quality,
        "contributing_factors": result.contributing_factors,
        "contradicting_factors": result.contradicting_factors,
        "commentary": commentary,
        "disclosure": DISCLOSURE_BUNDLE,
        "not_advice": NOT_ADVICE,
        "disclaimer_version": DISCLAIMER_VERSION,
    }


async def _cache_latest(result: MoodResult, snapshot_date: date, commentary: Optional[str]) -> None:
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

async def get_latest(db: Any) -> Optional[MoodPublic]:
    from sqlalchemy import select

    from dhanradar.models.mood import MarketMood

    row = await db.scalar(select(MarketMood).order_by(MarketMood.snapshot_date.desc()))
    if row is None:
        return None
    return MoodPublic(
        snapshot_date=row.snapshot_date.isoformat(), regime=row.regime,
        confidence_band=row.confidence_band, data_quality=row.data_quality,
        contributing_factors=list(row.contributing_factors or []),
        contradicting_factors=list(row.contradicting_factors or []),
        commentary=row.ai_commentary, disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE, disclaimer_version=DISCLAIMER_VERSION,
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


async def get_why_today(db: Any) -> Optional[WhyToday]:
    from sqlalchemy import select

    from dhanradar.models.mood import MarketMood

    row = await db.scalar(select(MarketMood).order_by(MarketMood.snapshot_date.desc()))
    if row is None:
        return None
    return WhyToday(
        snapshot_date=row.snapshot_date.isoformat(), regime=row.regime,
        commentary=row.ai_commentary,
        contributing_factors=list(row.contributing_factors or []),
        contradicting_factors=list(row.contradicting_factors or []),
        disclosure=DISCLOSURE_BUNDLE, not_advice=NOT_ADVICE,
        disclaimer_version=DISCLAIMER_VERSION,
    )
