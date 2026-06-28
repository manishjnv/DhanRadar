"""
DhanRadar — Circuit Breaker for market-data provider rungs.

States
------
CLOSED   : normal operation — calls pass through.
OPEN     : too many consecutive failures — calls are blocked.
HALF_OPEN: one trial call is allowed after the reset timeout has elapsed;
           success → CLOSED, failure → OPEN (restart timeout).

The clock is injected via ``now`` so tests can advance time deterministically
without sleeping.
"""

from __future__ import annotations

import enum
import time as _time
from collections.abc import Callable


class _State(str, enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Per-provider circuit breaker with injectable clock.

    Parameters
    ----------
    failure_threshold:
        Number of consecutive failures before tripping to OPEN.
    reset_timeout:
        Seconds to wait in OPEN before trying HALF_OPEN.
    now:
        Callable returning the current monotonic time as a float.
        Defaults to ``time.monotonic``.  Inject a fake in tests.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        now: Callable[[], float] = _time.monotonic,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._now = now

        self._state: _State = _State.CLOSED
        self._failure_count: int = 0
        self._opened_at: float | None = None   # monotonic ts when we entered OPEN

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def state(self) -> _State:
        """Current circuit-breaker state (may auto-transition OPEN→HALF_OPEN)."""
        self._check_half_open_transition()
        return self._state

    def allow(self) -> bool:
        """
        Return True if a call should be allowed through.

        CLOSED  → True (always)
        OPEN    → False, unless ``reset_timeout`` has elapsed → then HALF_OPEN → True
        HALF_OPEN → True (one trial call is permitted)
        """
        self._check_half_open_transition()
        return self._state in (_State.CLOSED, _State.HALF_OPEN)

    def record_success(self) -> None:
        """
        Record a successful call.

        Resets failure count and transitions to CLOSED from any state.
        """
        self._failure_count = 0
        self._opened_at = None
        self._state = _State.CLOSED

    def record_failure(self) -> None:
        """
        Record a failed call.

        CLOSED: increment counter; if threshold reached → OPEN.
        HALF_OPEN trial failed → OPEN (restart timeout).
        OPEN: noop (already open — don't double-count callers that somehow slipped through).
        """
        if self._state == _State.OPEN:
            return

        self._failure_count += 1

        if self._state == _State.HALF_OPEN or self._failure_count >= self._failure_threshold:
            self._trip_open()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trip_open(self) -> None:
        """Transition to OPEN and record the open timestamp."""
        self._state = _State.OPEN
        self._opened_at = self._now()

    def _check_half_open_transition(self) -> None:
        """If OPEN and reset_timeout has elapsed, transition to HALF_OPEN."""
        if self._state == _State.OPEN and self._opened_at is not None:
            if self._now() - self._opened_at >= self._reset_timeout:
                self._state = _State.HALF_OPEN
