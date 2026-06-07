"""
DhanRadar — Compliance Audit service (architecture Global §4, B26).

Two responsibilities:
  * `record_served_label(...)` — fire-and-forget write of one served label to the
    7-yr `ai_recommendation_audit` trail. Opens its OWN DB session and swallows all
    errors (logged) so an audit failure NEVER breaks or corrupts the serving path;
    the table's DEFAULT partition + denormalized `disclaimer_version` mean the row is
    not lost to a missing partition or a referential hiccup.
  * `get_active_disclaimer(db, type)` — read the in-force disclaimer (Redis-cached 1h).

`recommendation_type='buy_sell'` is rejected at the DB (CHECK) AND defensively here.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

_DISCLAIMER_CACHE_PREFIX = "disclaimer:active:"
_DISCLAIMER_TTL = 3600

# POSITIVE allowlist of auditable recommendation types — only educational labels
# may be recorded as served (non-neg #1). Anything else (incl. any advisory verb)
# is refused before the DB. Mirrors the DB CHECK `ck_audit_recommendation_type`.
_ALLOWED_TYPES = frozenset({"educational_label", "mood_regime"})


async def bump_audit_metric(name: str, amount: int = 1) -> None:
    """Best-effort daily Redis counter for compliance-audit observability (B34).
    Ops/alerting reads ``metrics:compliance:{name}:{YYYYMMDD}``. NEVER raises — an
    observability failure must not touch the serve/audit path."""
    try:
        from dhanradar.redis_client import get_redis

        redis = get_redis()
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        key = f"metrics:compliance:{name}:{day}"
        await redis.incrby(key, amount)
        await redis.expire(key, 35 * 86400)  # self-clean; alerting reads are recent
    except Exception:  # noqa: BLE001 — observability is best-effort
        logger.debug("compliance: metric bump failed for %s", name, exc_info=True)


def active_disclaimer_version() -> str:
    """The in-force disclaimer version (compliance is the §4 authority for it).
    A sync constant for fire-and-forget call sites; the DB-backed
    `get_active_disclaimer` is the authoritative async lookup. Callers that know
    the version served at generation should pin THAT instead of calling this."""
    from dhanradar.scoring.engine.schemas import DISCLAIMER_VERSION

    return DISCLAIMER_VERSION


def content_hash(payload: dict) -> str:
    """SHA-256 over a canonical JSON of the served payload (integrity anchor)."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def record_served_label(
    *,
    surface: str,
    label: Optional[str],
    model: Optional[str],
    disclaimer_version: str,
    recommendation_type: str = "educational_label",
    user_id: Optional[str] = None,
    identifier: Optional[str] = None,
    confidence_band: Optional[str] = None,
    prompt_version: Optional[str] = None,
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> bool:
    """Persist one audit row. Returns True iff written. NEVER raises — a failure is
    logged and swallowed (the caller's serve path must not break on audit).

    `served_at` is ALWAYS the server's current UTC time (never caller-supplied), so
    an audit row cannot be backdated to misattribute a different in-force disclaimer."""
    if recommendation_type not in _ALLOWED_TYPES:
        # Defense-in-depth above the DB CHECK — never even attempt to audit a
        # non-educational (e.g. advisory) type (non-neg #1).
        logger.error("compliance: refused to audit non-allowlisted type=%r", recommendation_type)
        return False

    try:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from dhanradar.db import engine
        from dhanradar.models.compliance import AiRecommendationAudit

        payload = {
            "surface": surface, "label": label, "model": model,
            "disclaimer_version": disclaimer_version, "identifier": identifier,
            "recommendation_type": recommendation_type,
        }
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with SessionLocal() as db:
            db.add(
                AiRecommendationAudit(
                    served_at=datetime.now(timezone.utc),  # server-set, never caller-supplied
                    user_id=UUID(user_id) if user_id and user_id != "anonymous" else None,
                    recommendation_type=recommendation_type,
                    label=label,
                    content_hash=content_hash(payload),
                    model=model,
                    prompt_version=prompt_version,
                    confidence_band=confidence_band,
                    disclaimer_version=disclaimer_version,
                    surface=surface,
                    session_id=session_id,
                    request_id=request_id,
                )
            )
            await db.commit()
        return True
    except Exception:  # noqa: BLE001 — fire-and-forget: audit must not break the serve path
        logger.exception("compliance: audit write failed surface=%s label=%s", surface, label)
        await bump_audit_metric("audit_write_failures")
        return False


async def get_active_disclaimer(db: Any, disclaimer_type: str) -> Optional[dict]:
    """Return the active disclaimer for a type (Redis-cached 1h; Postgres fallback)."""
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    cache_key = f"{_DISCLAIMER_CACHE_PREFIX}{disclaimer_type}"
    try:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:  # noqa: BLE001 — cache is best-effort
        pass

    from sqlalchemy import select

    from dhanradar.models.compliance import Disclaimer

    row = await db.scalar(
        select(Disclaimer).where(
            Disclaimer.type == disclaimer_type, Disclaimer.active.is_(True)
        ).order_by(Disclaimer.effective_from.desc())
    )
    if row is None:
        return None
    result = {"type": row.type, "version": row.version, "content": row.content}
    try:
        await redis.set(cache_key, json.dumps(result), ex=_DISCLAIMER_TTL)
    except Exception:  # noqa: BLE001
        pass
    return result
