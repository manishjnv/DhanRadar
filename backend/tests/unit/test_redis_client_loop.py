"""
Regression: get_redis() must be EVENT-LOOP-AWARE (RCA 2026-06-11).

A module-level client created under Celery task #1's asyncio.run() loop is
bound to that loop; after asyncio.run closes it, task #2's first Redis call
raised "RuntimeError: Event loop is closed" — every 2nd+ CAS upload in a
prefork child failed. get_redis() must hand a FRESH client to a new loop and
the SAME client within one loop. from_url() is lazy → no server needed.
"""

from __future__ import annotations

import asyncio

import dhanradar.redis_client as rc


def _reset():
    rc._client = None
    rc._client_loop = None


def test_new_loop_gets_new_client_same_loop_reuses():
    _reset()

    async def _grab_twice():
        return rc.get_redis(), rc.get_redis()

    a1, a2 = asyncio.run(_grab_twice())
    assert a1 is a2  # same loop → same client (singleton behaviour preserved)

    b1, _ = asyncio.run(_grab_twice())
    assert b1 is not a1  # NEW loop → fresh client (the closed-loop bug)
    _reset()


def test_no_loop_caller_reuses_cached_client():
    _reset()
    c1 = rc.get_redis()  # no running loop (sync/legacy path)
    c2 = rc.get_redis()
    assert c1 is c2
    _reset()


def test_injected_fake_client_is_never_replaced():
    # conftest's patch_redis assigns _client directly (loop None); a loop-bound
    # caller must NOT evict it (CI broke on exactly this before the narrow rule).
    _reset()
    sentinel = object()
    rc._client = sentinel

    async def _grab():
        return rc.get_redis()

    assert asyncio.run(_grab()) is sentinel
    assert asyncio.run(_grab()) is sentinel  # across loops too
    _reset()
