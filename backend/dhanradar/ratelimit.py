"""
DhanRadar — Redis fixed-window rate limiter dependency.

Architecture substitution note:
  The DhanRadar architecture document specifies "Nginx anon:10m rate=30r/m"
  for anonymous endpoint rate limiting.  This deployment currently has NO
  Nginx in the request path (Cloudflared → uvicorn directly).  This module
  provides an equivalent application-layer fixed-window limiter backed by
  Redis so that the same 30 req/min/IP limit is enforced at the FastAPI layer
  until Nginx is introduced.  When Nginx is added, these FastAPI-level guards
  can be removed or left as defence-in-depth.

Usage::

    from dhanradar.ratelimit import RateLimit

    @router.post("/auth/login")
    async def login(
        request: Request,
        _: None = Depends(RateLimit(max_requests=30, window_seconds=60)),
    ): ...

Class-based (not closure) to comply with the project anti-pattern rule.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from dhanradar.redis_client import get_redis


class RateLimit:
    """
    Fixed-window rate limiter keyed by client IP address.

    Args:
        max_requests: Maximum allowed requests in the window (default 30).
        window_seconds: Window duration in seconds (default 60 → 30 req/min).
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(self, request: Request) -> None:
        client_ip = self._get_client_ip(request)
        redis = get_redis()

        key = f"ratelimit:{client_ip}:{request.url.path}"
        count_str = await redis.get(key)
        count = int(count_str) if count_str is not None else 0

        if count >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate_limit_exceeded",
                headers={"Retry-After": str(self.window_seconds)},
            )

        # INCR + set TTL on first request in window
        new_count = await redis.incr(key)
        if new_count == 1:
            await redis.expire(key, self.window_seconds)

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """
        Extract the real client IP for rate-limit keying.

        SECURITY: do NOT trust `X-Forwarded-For` — it is fully client-supplied
        and an attacker can rotate it per request to defeat the per-IP limiter.
        This origin is reachable ONLY via the dedicated Cloudflare Tunnel, so
        `CF-Connecting-IP` is set by Cloudflare's edge and cannot be forged by
        the client through the tunnel. Use it as the trusted source; fall back
        to the direct connection IP only if it is absent.
        """
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip.strip()
        if request.client:
            return request.client.host
        return "unknown"
