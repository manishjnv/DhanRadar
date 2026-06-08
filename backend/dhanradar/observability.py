"""
DhanRadar — Observability: Sentry error capture + Prometheus metrics (B38).

Design constraints
------------------
* DPDP compliance: Sentry MUST NOT ship PII cross-border.
  - send_default_pii=False  (belt)
  - max_request_body_size="never"  (belt)
  - _scrub_event before_send hook strips cookies, sensitive headers, body,
    and user fields  (suspenders)
* Prometheus label cardinality: ONLY method / template / status labels.
  `template` is ALWAYS the matched route template (e.g. /api/v1/mf/{job_id}),
  NEVER the raw URL path, so user/job ids never leak into metric series.
* A dedicated CollectorRegistry (REGISTRY) avoids duplicate-timeseries errors
  on test re-import (never registers on the global default registry).
* /metrics is mounted OUTSIDE /api/v1 and is NOT reachable through the public
  Cloudflare tunnel (which routes only ^/api/.* to FastAPI).
"""

from __future__ import annotations

import time
from typing import Any

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match

from dhanradar.config import settings

# ---------------------------------------------------------------------------
# Prometheus: dedicated registry (safe for test re-import)
# ---------------------------------------------------------------------------

REGISTRY = CollectorRegistry()

REQUEST_COUNT = Counter(
    "dhanradar_http_requests_total",
    "Total HTTP requests handled by DhanRadar",
    ["method", "template", "status"],
    registry=REGISTRY,
)

REQUEST_LATENCY = Histogram(
    "dhanradar_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "template"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Sentry: DPDP-safe scrubber
# ---------------------------------------------------------------------------

_SCRUB_HEADERS: frozenset[str] = frozenset(
    {"authorization", "cookie", "x-internal-token"}
)


def _scrub_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """
    before_send hook — defensively strips PII fields from every Sentry event.

    Removes:
    - request.cookies        (cookie jar)
    - request headers whose lowercased name is in _SCRUB_HEADERS
      (handles both dict and list-of-pairs shapes; unknown shapes dropped wholesale)
    - request.data           (body — belt on top of max_request_body_size="never")
    - request.query_string   (can carry ?token= / ?email= PII)
    - request.env            (WSGI/ASGI env carries REMOTE_ADDR = client IP)
    - top-level breadcrumbs  (may carry SQL / outbound-URL / log PII)
    - top-level user         (user identity)

    Returns the mutated event so Sentry still captures the error trace.
    """
    request = event.get("request", {})

    # Strip cookie jar
    request.pop("cookies", None)

    # Strip raw query string (can carry ?token= / ?email= PII)
    request.pop("query_string", None)

    # Strip WSGI/ASGI env (carries REMOTE_ADDR = client IP)
    request.pop("env", None)

    # Strip sensitive request headers — handle dict OR list-of-pairs shape
    headers = request.get("headers")
    if isinstance(headers, dict):
        request["headers"] = {
            k: v for k, v in headers.items() if k.lower() not in _SCRUB_HEADERS
        }
    elif isinstance(headers, list):
        request["headers"] = [
            pair for pair in headers
            if not (
                isinstance(pair, (list, tuple)) and len(pair) == 2
                and str(pair[0]).lower() in _SCRUB_HEADERS
            )
        ]
    elif headers is not None:
        request.pop("headers", None)

    # Strip request body (belt on top of max_request_body_size="never")
    request.pop("data", None)

    if request:
        event["request"] = request

    # Strip breadcrumbs (can carry SQL / outbound-URL / log PII)
    event.pop("breadcrumbs", None)

    # Strip user identity
    event.pop("user", None)

    # Strip exception messages + log message. A RequestValidationError (and
    # similar) embeds the raw submitted value (e.g. an email / PAN / phone) in
    # its message string, which would otherwise ship cross-border to Sentry
    # (DPDP). The exception type and stacktrace are retained for diagnosis.
    for _exc in event.get("exception", {}).get("values", []):
        if isinstance(_exc, dict) and "value" in _exc:
            _exc["value"] = "<scrubbed>"
    event.pop("logentry", None)

    return event


def init_sentry() -> bool:
    """
    Initialise Sentry SDK if SENTRY_DSN is configured.

    Returns True when Sentry was initialised, False when DSN is absent/empty
    (the default dev/test case — this is a deliberate no-op, not an error).

    DPDP constraints enforced here:
    - send_default_pii=False        → SDK never auto-attaches user/IP/cookies
    - max_request_body_size="never" → request bodies are never captured
    - before_send=_scrub_event      → belt-and-suspenders PII scrubber
    - traces_sample_rate=0.0        → performance tracing off (no span data)
    """
    dsn = settings.SENTRY_DSN
    if not dsn:
        return False

    import sentry_sdk  # lazy import — only pay the cost when DSN is set

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.ENV,
        traces_sample_rate=0.0,
        # DPDP constraint 1: never auto-attach PII (belt)
        send_default_pii=False,
        # DPDP constraint 2: never capture request bodies (belt)
        max_request_body_size="never",
        # DPDP constraint 3: scrub hook strips cookies/headers/body/user (suspenders)
        before_send=_scrub_event,
    )
    return True


# ---------------------------------------------------------------------------
# Route template resolution (no raw-URL leakage into metric labels)
# ---------------------------------------------------------------------------


def route_template(app: Any, scope: dict[str, Any]) -> str:
    """
    Resolve the matched route template for a Starlette/FastAPI scope.

    Iterates app.routes and uses route.matches(scope) to find the FULL match.
    Returns the route.path template (e.g. '/api/v1/mf/{job_id}') so that
    dynamic segments (user ids, job ids) NEVER appear in metric label values.

    Falls back to '__unmatched__' when no route matches (404 paths, static
    assets that fell through, etc.). Each route.matches() call is wrapped in
    try/except so a malformed route definition cannot crash the middleware.
    """
    routes = getattr(app, "routes", [])
    for route in routes:
        try:
            match, _ = route.matches(scope)
            if match == Match.FULL:
                return route.path  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            continue
    return "__unmatched__"


# ---------------------------------------------------------------------------
# Prometheus middleware
# ---------------------------------------------------------------------------


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that records per-request counts and latency.

    Label safety:
    - method   : HTTP verb (GET, POST, …)
    - template : matched route template, never the raw path
    - status   : HTTP status code as a string

    The /metrics endpoint itself is intentionally excluded from instrumentation
    to avoid scrape-induced noise in the latency histogram.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Do not instrument the scrape endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        template = route_template(request.app, request.scope)
        start = time.perf_counter()
        status = 500  # default; overwritten in try block

        try:
            response: Response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - start
            REQUEST_COUNT.labels(method, template, str(status)).inc()
            REQUEST_LATENCY.labels(method, template).observe(elapsed)


# ---------------------------------------------------------------------------
# /metrics scrape endpoint
# ---------------------------------------------------------------------------


async def metrics_endpoint(request: Request) -> Response:
    """
    Expose Prometheus metrics for server-to-server scraping.

    Mounted at /metrics (NOT under /api/v1). The Cloudflare tunnel ingress
    routes only ^/api/.* to FastAPI, so this path is NOT publicly reachable —
    it is scraped server-to-server on the Docker network by Prometheus.

    Access control is docker-network isolation. The payload carries NO PII —
    only route templates + request counts/latencies (see route_template). No
    header/bearer auth is used here: non-neg #5 makes the public API cookie-only,
    and a co-tenant scrape token (shared etip_prometheus) would have to use a
    NON-Authorization header — tracked as a B38 residual, not implemented here.
    """
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
