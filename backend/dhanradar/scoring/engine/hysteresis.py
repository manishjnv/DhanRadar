"""
DhanRadar — label hysteresis (spec §4.3 / §7 governance).

Eval-count hysteresis: a label flip publishes only after **2 consecutive
evaluations** at the new label. Between the first divergent eval and the flip the
PREVIOUSLY published label is held. ``eval_seq`` increments every evaluation and
is exposed downstream for alert gating (an alert should fire on a real flip, not
on a one-off blip).

State is small and per-instrument; the store is injectable so the engine is unit
testable without Redis. The Redis-backed default carries a long TTL.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from dhanradar.scoring.engine.schemas import VerbLabel

_STATE_TTL_SECONDS = 180 * 24 * 3600  # ~180d; eval state outlives normal cadence


class HysteresisStore(Protocol):
    async def get(self, key: str) -> Optional[dict]: ...
    async def set(self, key: str, state: dict) -> None: ...


class RedisHysteresisStore:
    """Default store backed by the shared async Redis client."""

    def __init__(self, redis: Any = None) -> None:
        self._redis = redis

    def _r(self) -> Any:
        if self._redis is None:
            from dhanradar.redis_client import get_redis

            self._redis = get_redis()
        return self._redis

    async def get(self, key: str) -> Optional[dict]:
        raw = await self._r().get(key)
        return json.loads(raw) if raw else None

    async def set(self, key: str, state: dict) -> None:
        await self._r().set(key, json.dumps(state), ex=_STATE_TTL_SECONDS)


@dataclass(frozen=True)
class HysteresisOutcome:
    published_label: VerbLabel
    eval_seq: int
    flip_pending: bool  # a divergent label is accumulating but has not yet flipped


def _key(instrument_type: str, identifier: str) -> str:
    return f"scoring:hyst:{instrument_type}:{identifier}"


async def apply_hysteresis(
    store: HysteresisStore,
    instrument_type: str,
    identifier: str,
    candidate: VerbLabel,
) -> HysteresisOutcome:
    """Resolve the published label for ``candidate`` under 2-eval hysteresis.

    ``insufficient_data`` is published immediately (a refusal is not a label flip
    to be smoothed — we must not keep showing a stale label when data drops out).
    """
    key = _key(instrument_type, identifier)
    state = await store.get(key) or {}
    eval_seq = int(state.get("eval_seq", 0)) + 1
    published = state.get("published")

    # Refusals and first-ever evals publish immediately.
    if candidate == VerbLabel.insufficient_data or published is None:
        new_state = {
            "published": candidate.value,
            "pending": None,
            "pending_count": 0,
            "eval_seq": eval_seq,
        }
        await store.set(key, new_state)
        return HysteresisOutcome(candidate, eval_seq, flip_pending=False)

    published_label = VerbLabel(published)
    if candidate == published_label:
        # Confirmed — clear any pending divergence.
        await store.set(
            key,
            {"published": published, "pending": None, "pending_count": 0, "eval_seq": eval_seq},
        )
        return HysteresisOutcome(published_label, eval_seq, flip_pending=False)

    # Divergent candidate — accumulate consecutive count.
    pending = state.get("pending")
    pending_count = int(state.get("pending_count", 0))
    if pending == candidate.value:
        pending_count += 1
    else:
        pending, pending_count = candidate.value, 1

    if pending_count >= 2:
        # Flip confirmed by 2 consecutive evals.
        await store.set(
            key,
            {"published": candidate.value, "pending": None, "pending_count": 0, "eval_seq": eval_seq},
        )
        return HysteresisOutcome(candidate, eval_seq, flip_pending=False)

    # Suppress the flip — hold the previously published label.
    await store.set(
        key,
        {"published": published, "pending": pending, "pending_count": pending_count, "eval_seq": eval_seq},
    )
    return HysteresisOutcome(published_label, eval_seq, flip_pending=True)
