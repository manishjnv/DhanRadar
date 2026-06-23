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
