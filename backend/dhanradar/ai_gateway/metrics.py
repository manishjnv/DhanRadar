"""
DhanRadar — AI-gateway latency instrumentation (Redis rolling daily stats).

Records per-call LLM response latency into per-UTC-day Redis sum+count counters
so the Admin AI-Ops surface can show an average over a rolling window. There is
NO migration and NO audit-table change: the gateway is the only writer and it
does not own the ai_recommendation_audit insert (that lives on the serve path),
so a Redis rolling stat is the lowest-blast-radius store for this signal.

EVERY function here is best-effort and NON-FATAL: a Redis failure NEVER
propagates. An observational metric must never break an AI call (record path) or
500 a monitoring read (read path). This mirrors the strike/budget Redis pattern
already in gateway.py and the fire-and-forget audit write in
compliance.service.record_served_label.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from dhanradar.redis_client import get_redis

logger = logging.getLogger(__name__)

# Per-UTC-day keys. Sum is float milliseconds; count is an integer call tally.
_LATENCY_SUM_KEY = "ai:latency:sum:{day}"
_LATENCY_COUNT_KEY = "ai:latency:count:{day}"

# Keep a couple of days beyond the default 7-day read window so a window read
# never straddles an expired key, while still bounding Redis growth.
_RETENTION_DAYS = 9
_RETENTION_SECONDS = _RETENTION_DAYS * 86_400

# Defensive ceiling: ignore absurd samples (a stuck clock / bad caller) so one
# outlier cannot dominate the rolling average. 10 minutes is far above any real
# LLM round-trip.
_MAX_SANE_LATENCY_MS = 600_000.0

# Per-model spend (PR-2). Per-UTC-day keys, keyed by model id. ``calls`` is a
# billed-response tally (free + paid); ``usd`` accumulates only for paid/premium
# responses (free models stay at 0). A per-day SET enumerates the models seen
# that day so the read side never needs KEYS/SCAN. Redis keys are binary-safe,
# so model ids containing "/" and ":" (the usual "vendor/model:tier" shape) are
# fine embedded in a key unescaped.
_SPEND_CALLS_KEY = "ai:spend:calls:{model}:{day}"
_SPEND_USD_KEY = "ai:spend:usd:{model}:{day}"
_SPEND_MODELS_KEY = "ai:spend:models:{day}"

# Advice-boundary breaches (PR-3): per-UTC-day count of LLM responses REJECTED by
# the quality validator's SEBI advisory screen (a banned verb reached output).
# This is a compliance-observability counter for non-neg #1 — it does NOT mean
# advisory text reached a user (rejected output is never served), it means the
# model TRIED and the gate held.
_ADVISORY_BREACH_KEY = "ai:advisory_breach:{day}"


def _day(dt: datetime.datetime) -> str:
    return dt.strftime("%Y%m%d")


async def record_latency(latency_ms: float, *, redis: Any = None) -> None:
    """Add one latency sample to today's rolling Redis counters. Never raises.

    Args:
        latency_ms: Measured wall-clock latency of one served LLM response, in ms.
        redis: Optional injected client (tests); falls back to the shared client.
    """
    try:
        if latency_ms < 0 or latency_ms > _MAX_SANE_LATENCY_MS:
            return  # ignore non-physical samples; do not pollute the average
        r = redis or get_redis()
        day = _day(datetime.datetime.now(datetime.UTC))
        count_key = _LATENCY_COUNT_KEY.format(day=day)
        sum_key = _LATENCY_SUM_KEY.format(day=day)
        await r.incrbyfloat(sum_key, float(latency_ms))
        await r.incr(count_key)
        # Refresh the TTL UNCONDITIONALLY on every write — never gate it on
        # "first write of the day". If a prior write partially failed (e.g. the
        # outer except fired between incr and expire), a conditional guard would
        # leave a key with no TTL, so it would persist forever and later deflate
        # the rolling average. EXPIRE is idempotent; re-setting it is cheap and
        # keeps both keys bounded to the retention window from their last write.
        await r.expire(sum_key, _RETENTION_SECONDS)
        await r.expire(count_key, _RETENTION_SECONDS)
    except Exception:  # noqa: BLE001 — observational metric must never break an AI call
        logger.debug("ai latency record failed", exc_info=True)


async def read_latency_window(days: int = 7, *, redis: Any = None) -> dict:
    """Aggregate the rolling latency counters over the last ``days`` UTC days.

    Returns a dict shaped for ``LatencyInfo`` (aiops_schemas):
        {instrumented, value_ms, sample_count, window_days}

    On a Redis failure OR when no samples exist yet, returns
    ``instrumented=False`` with ``value_ms=None`` rather than raising — the
    monitoring surface stays up (no 500) and renders a clean "not yet recorded"
    state. ``days`` is clamped to the retention window so a read never asks for
    keys that have already expired.
    """
    days = max(1, min(days, _RETENTION_DAYS))
    absent = {"instrumented": False, "value_ms": None, "sample_count": 0, "window_days": days}
    try:
        r = redis or get_redis()
        now = datetime.datetime.now(datetime.UTC)
        total_sum = 0.0
        total_count = 0
        for i in range(days):
            day = _day(now - datetime.timedelta(days=i))
            raw_count = await r.get(_LATENCY_COUNT_KEY.format(day=day))
            raw_sum = await r.get(_LATENCY_SUM_KEY.format(day=day))
            if raw_count:
                total_count += int(raw_count)
            if raw_sum:
                total_sum += float(raw_sum)
        if total_count <= 0:
            return absent
        return {
            "instrumented": True,
            "value_ms": round(total_sum / total_count, 1),
            "sample_count": total_count,
            "window_days": days,
        }
    except Exception:  # noqa: BLE001 — degraded monitoring read, never a 500
        logger.debug("ai latency read failed", exc_info=True)
        return absent


async def record_model_spend(
    model: str, *, calls: int = 0, usd: float = 0.0, redis: Any = None
) -> None:
    """Add per-model spend to today's rolling counters. Never raises.

    Called at the gateway's debit points: ``calls`` (=1) is recorded once per
    served response in ``_call`` (free + paid + sonnet); ``usd`` is recorded
    separately at the paid/sonnet sites where the charge is computed, with
    ``calls=0`` so the call tally is never double-counted. TTL is set
    UNCONDITIONALLY on every write (a partial failure must not orphan a key).
    """
    try:
        if not model:
            return
        r: Any = redis or get_redis()
        day = _day(datetime.datetime.now(datetime.UTC))
        models_key = _SPEND_MODELS_KEY.format(day=day)
        await r.sadd(models_key, model)
        await r.expire(models_key, _RETENTION_SECONDS)
        # `if calls`/`if usd` skip the no-op write for the other site's shape:
        # _call passes calls=1 (usd default 0); the paid/sonnet sites pass usd>0
        # (calls default 0). A free model never reaches the USD branch, so a 0.0
        # USD is never recorded — by design, free models read back as usd=0.
        if calls:
            calls_key = _SPEND_CALLS_KEY.format(model=model, day=day)
            await r.incrby(calls_key, int(calls))
            await r.expire(calls_key, _RETENTION_SECONDS)
        if usd:
            usd_key = _SPEND_USD_KEY.format(model=model, day=day)
            await r.incrbyfloat(usd_key, float(usd))
            await r.expire(usd_key, _RETENTION_SECONDS)
    except Exception:  # noqa: BLE001 — observational metric must never break an AI call
        logger.debug("ai model-spend record failed", exc_info=True)


async def read_spend_window(days: int = 7, *, redis: Any = None) -> dict:
    """Aggregate per-model spend over the last ``days`` UTC days.

    Returns a dict shaped for ``PerModelSpend`` (aiops_schemas):
        {instrumented, window_days, models: [{model, calls, usd}], total_calls,
         total_usd}
    ``models`` is sorted by usd desc, then calls desc, then name. On a Redis
    failure or when no spend has been recorded, returns ``instrumented=False``
    rather than raising — the monitoring surface stays up (no 500).
    """
    days = max(1, min(days, _RETENTION_DAYS))
    absent = {
        "instrumented": False,
        "window_days": days,
        "models": [],
        "total_calls": 0,
        "total_usd": 0.0,
    }
    try:
        r: Any = redis or get_redis()
        now = datetime.datetime.now(datetime.UTC)
        model_names: set[str] = set()
        for i in range(days):
            day = _day(now - datetime.timedelta(days=i))
            members = await r.smembers(_SPEND_MODELS_KEY.format(day=day))
            if members:
                model_names.update(members)
        if not model_names:
            return absent
        rows: list[dict] = []
        total_calls = 0
        total_usd = 0.0
        for model in model_names:
            calls = 0
            usd = 0.0
            for i in range(days):
                day = _day(now - datetime.timedelta(days=i))
                raw_calls = await r.get(_SPEND_CALLS_KEY.format(model=model, day=day))
                raw_usd = await r.get(_SPEND_USD_KEY.format(model=model, day=day))
                if raw_calls:
                    calls += int(raw_calls)
                if raw_usd:
                    usd += float(raw_usd)
            total_calls += calls
            total_usd += usd
            rows.append({"model": model, "calls": calls, "usd": round(usd, 6)})
        rows.sort(key=lambda x: (-x["usd"], -x["calls"], x["model"]))
        return {
            "instrumented": True,
            "window_days": days,
            "models": rows,
            "total_calls": total_calls,
            "total_usd": round(total_usd, 6),
        }
    except Exception:  # noqa: BLE001 — degraded monitoring read, never a 500
        logger.debug("ai model-spend read failed", exc_info=True)
        return absent


async def record_advisory_breach(*, redis: Any = None) -> None:
    """Increment today's advice-boundary breach counter. Never raises.

    Called when the quality validator rejects an LLM response for advisory
    language (the SEBI educational boundary held). Non-fatal: a Redis failure
    must not break the gateway's reject/spillover/skip path.
    """
    try:
        r: Any = redis or get_redis()
        day = _day(datetime.datetime.now(datetime.UTC))
        key = _ADVISORY_BREACH_KEY.format(day=day)
        await r.incr(key)
        await r.expire(key, _RETENTION_SECONDS)
    except Exception:  # noqa: BLE001 — observational metric must never break the gateway
        logger.debug("ai advisory-breach record failed", exc_info=True)


async def read_advisory_breaches(days: int = 7, *, redis: Any = None) -> dict:
    """Sum the advice-boundary breach counter over the last ``days`` UTC days.

    Returns {"instrumented", "value", "window_days"}. ``instrumented`` is True
    whenever the Redis read succeeds (even at 0) — unlike latency/spend, a 0 here
    is a MEANINGFUL clean reading (the boundary held with no breaches), so the
    surface must not present it as "not measured". Degrades to instrumented=False
    only on a Redis failure.
    """
    days = max(1, min(days, _RETENTION_DAYS))
    try:
        r: Any = redis or get_redis()
        now = datetime.datetime.now(datetime.UTC)
        total = 0
        for i in range(days):
            day = _day(now - datetime.timedelta(days=i))
            raw = await r.get(_ADVISORY_BREACH_KEY.format(day=day))
            if raw:
                total += int(raw)
        return {"instrumented": True, "value": total, "window_days": days}
    except Exception:  # noqa: BLE001 — degraded monitoring read, never a 500
        logger.debug("ai advisory-breach read failed", exc_info=True)
        return {"instrumented": False, "value": 0, "window_days": days}
