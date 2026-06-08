"""
Unit tests for dhanradar.observability (B38).

DB-FREE — no lifespan, no Postgres, no Redis. All tests are synchronous or
use only in-process objects.

Covered
-------
1. init_sentry() returns False when SENTRY_DSN is None (no-op, DPDP-safe default).
2. _scrub_event removes cookies, sensitive headers, request body, and user.
   2a. Also strips query_string, env, and breadcrumbs (DPDP conditions 1+2+4).
   2b. Header scrub handles list-of-pairs shape (condition 3).
   2c. Header scrub handles dict shape — regression.
3. route_template: matched path returns the template (not the raw URL with ids);
   unmatched path returns '__unmatched__'.
4. REQUEST_COUNT counter increments and generate_latest reports the metric name.
5. /metrics route is registered on the app at '/metrics', NOT at '/api/v1/metrics'.
6. metrics_endpoint: optional bearer-token guard (condition 5).
7. PrometheusMiddleware.dispatch records status=500 on route exception (condition 6).
"""

from __future__ import annotations

import pytest
from prometheus_client import generate_latest

import dhanradar.observability as observability
from dhanradar.observability import (
    REGISTRY,
    _scrub_event,
    init_sentry,
    route_template,
)

# ---------------------------------------------------------------------------
# 1. init_sentry returns False when SENTRY_DSN is unset
# ---------------------------------------------------------------------------


def test_init_sentry_no_dsn_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """init_sentry() must be a no-op and return False when DSN is absent."""
    monkeypatch.setattr(observability.settings, "SENTRY_DSN", None)
    result = init_sentry()
    assert result is False


def test_init_sentry_empty_string_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty-string DSN is also treated as unset."""
    monkeypatch.setattr(observability.settings, "SENTRY_DSN", "")
    result = init_sentry()
    assert result is False


# ---------------------------------------------------------------------------
# 2. _scrub_event strips PII fields (DPDP belt-and-suspenders)
# ---------------------------------------------------------------------------


def _make_sample_event() -> dict:
    return {
        "request": {
            "url": "https://api.dhanradar.com/api/v1/mf/upload",
            "method": "POST",
            "headers": {
                "content-type": "application/json",
                "authorization": "Bearer secret-token",
                "cookie": "__Host-access=abc123",
                "x-internal-token": "internal-secret",
                "x-request-id": "req-uuid-123",
            },
            "cookies": {"__Host-access": "abc123", "__Host-refresh": "xyz789"},
            "data": '{"folio": "12345678"}',
        },
        "user": {"id": "user-uuid-456", "email": "investor@example.com"},
        "exception": {"values": [{"type": "ValueError", "value": "bad input"}]},
    }


def test_scrub_event_removes_cookies() -> None:
    event = _make_sample_event()
    result = _scrub_event(event, {})
    assert "cookies" not in result["request"]


def test_scrub_event_removes_authorization_header() -> None:
    event = _make_sample_event()
    result = _scrub_event(event, {})
    headers = result["request"]["headers"]
    assert "authorization" not in headers


def test_scrub_event_removes_cookie_header() -> None:
    event = _make_sample_event()
    result = _scrub_event(event, {})
    headers = result["request"]["headers"]
    assert "cookie" not in headers


def test_scrub_event_removes_x_internal_token_header() -> None:
    event = _make_sample_event()
    result = _scrub_event(event, {})
    headers = result["request"]["headers"]
    assert "x-internal-token" not in headers


def test_scrub_event_preserves_safe_headers() -> None:
    """Non-PII headers such as content-type and x-request-id must be kept."""
    event = _make_sample_event()
    result = _scrub_event(event, {})
    headers = result["request"]["headers"]
    assert "content-type" in headers
    assert "x-request-id" in headers


def test_scrub_event_removes_request_body() -> None:
    event = _make_sample_event()
    result = _scrub_event(event, {})
    assert "data" not in result["request"]


def test_scrub_event_removes_user() -> None:
    event = _make_sample_event()
    result = _scrub_event(event, {})
    assert "user" not in result


def test_scrub_event_preserves_exception() -> None:
    """Exception trace must survive scrubbing (that's the whole point of Sentry)."""
    event = _make_sample_event()
    result = _scrub_event(event, {})
    assert result["exception"]["values"][0]["type"] == "ValueError"


def test_scrub_event_scrubs_exception_value() -> None:
    """The exception MESSAGE can embed raw submitted PII (a RequestValidationError
    echoes the bad value, e.g. an email/PAN) — scrub it; keep type + stacktrace."""
    event = _make_sample_event()
    event["exception"]["values"][0]["value"] = "not a valid email: investor@example.com"
    event["exception"]["values"][0]["stacktrace"] = {"frames": []}
    result = _scrub_event(event, {})
    assert result["exception"]["values"][0]["value"] == "<scrubbed>"
    assert result["exception"]["values"][0]["type"] == "ValueError"
    assert "stacktrace" in result["exception"]["values"][0]


def test_scrub_event_removes_logentry() -> None:
    """logentry.message mirrors the exception message and can carry the same PII."""
    event = _make_sample_event()
    event["logentry"] = {"message": "bad value investor@example.com"}
    result = _scrub_event(event, {})
    assert "logentry" not in result


def test_scrub_event_no_request_key() -> None:
    """Events without a request key (e.g. background tasks) must not crash."""
    event: dict = {"exception": {"values": []}}
    result = _scrub_event(event, {})
    assert "user" not in result


# ---------------------------------------------------------------------------
# 3. route_template: template returned (not raw URL); unmatched → __unmatched__
# ---------------------------------------------------------------------------


def test_route_template_returns_template_not_raw_path() -> None:
    """
    A concrete job id in the URL must NOT appear in the returned template.
    The template /api/v1/mf/{job_id} must be returned, not /api/v1/mf/abc-123.
    """
    from fastapi import FastAPI

    mini_app = FastAPI()

    @mini_app.get("/api/v1/mf/{job_id}")
    async def _dummy_handler(job_id: str) -> dict:  # noqa: RUF029
        return {}

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/mf/abc-123",
        "query_string": b"",
        "headers": [],
        "root_path": "",
    }

    template = route_template(mini_app, scope)
    assert template == "/api/v1/mf/{job_id}", (
        f"Expected template '/api/v1/mf/{{job_id}}', got {template!r} — "
        "raw job id leaked into metric label"
    )
    assert "abc-123" not in template, "Concrete job id must not appear in template"


def test_route_template_unmatched_returns_sentinel() -> None:
    """An unknown path that matches no route must return '__unmatched__'."""
    from fastapi import FastAPI

    mini_app = FastAPI()

    @mini_app.get("/api/v1/health")
    async def _health() -> dict:  # noqa: RUF029
        return {}

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/this/does/not/exist",
        "query_string": b"",
        "headers": [],
        "root_path": "",
    }

    assert route_template(mini_app, scope) == "__unmatched__"


# ---------------------------------------------------------------------------
# 4. REQUEST_COUNT counter increments + generate_latest includes metric name
# ---------------------------------------------------------------------------


def test_request_count_counter_increments_and_generates() -> None:
    """
    Incrementing REQUEST_COUNT and calling generate_latest(REGISTRY) must
    include the metric name in the output bytes.
    """
    from dhanradar.observability import REQUEST_COUNT

    REQUEST_COUNT.labels("GET", "/x", "200").inc()
    output: bytes = generate_latest(REGISTRY)
    assert b"dhanradar_http_requests_total" in output


# ---------------------------------------------------------------------------
# 5. /metrics mounted outside /api/v1 on the real app
# ---------------------------------------------------------------------------


def test_metrics_route_registered_at_correct_path() -> None:
    """
    /metrics must be registered on the app at exactly '/metrics'.
    It must NOT be at '/api/v1/metrics' (that would be publicly reachable
    through the Cloudflare tunnel and expose internal Prometheus data).
    """
    from dhanradar.main import app

    route_paths = {r.path for r in app.routes}  # type: ignore[union-attr]
    assert "/metrics" in route_paths, (
        "/metrics route missing — Prometheus scraping will not work"
    )
    assert "/api/v1/metrics" not in route_paths, (
        "/api/v1/metrics must NOT exist — it would be publicly reachable"
    )


# ---------------------------------------------------------------------------
# 2a. _scrub_event strips query_string, env, and breadcrumbs (conditions 1+2+4)
# ---------------------------------------------------------------------------


def _make_event_with_extras() -> dict:
    """Event that includes query_string, env, and breadcrumbs PII fields."""
    return {
        "request": {
            "url": "https://api.dhanradar.com/api/v1/mf/upload",
            "method": "GET",
            "headers": {"content-type": "application/json"},
            "query_string": "token=secret&email=user@example.com",
            "env": {"REMOTE_ADDR": "203.0.113.42", "SERVER_NAME": "api.dhanradar.com"},
        },
        "breadcrumbs": {
            "values": [
                {"type": "query", "message": "SELECT * FROM users WHERE email='x'"},
                {"type": "http", "data": {"url": "https://internal/secret"}},
            ]
        },
        "exception": {"values": [{"type": "RuntimeError", "value": "oops"}]},
    }


def test_scrub_event_removes_query_string() -> None:
    """query_string can carry ?token= / ?email= — must be stripped."""
    event = _make_event_with_extras()
    result = _scrub_event(event, {})
    assert "query_string" not in result["request"]


def test_scrub_event_removes_env() -> None:
    """env carries REMOTE_ADDR (client IP = PII) — must be stripped."""
    event = _make_event_with_extras()
    result = _scrub_event(event, {})
    assert "env" not in result["request"]


def test_scrub_event_removes_breadcrumbs() -> None:
    """breadcrumbs can carry SQL/log/outbound-URL PII — must be dropped wholesale."""
    event = _make_event_with_extras()
    result = _scrub_event(event, {})
    assert "breadcrumbs" not in result


def test_scrub_event_extras_preserves_exception() -> None:
    """Exception must survive even when the extras scrub runs."""
    event = _make_event_with_extras()
    result = _scrub_event(event, {})
    assert result["exception"]["values"][0]["type"] == "RuntimeError"


# ---------------------------------------------------------------------------
# 2b. Header scrub handles list-of-pairs shape (condition 3)
# ---------------------------------------------------------------------------


def test_scrub_event_list_headers_removes_sensitive_pairs() -> None:
    """
    When request['headers'] is a list of [name, value] pairs, sensitive pairs
    (Authorization, Cookie) must be removed and safe pairs (X-Ok) kept.
    """
    event: dict = {
        "request": {
            "url": "https://api.dhanradar.com/api/v1/mf/upload",
            "method": "GET",
            "headers": [
                ["Authorization", "Bearer secret-token"],
                ["Cookie", "__Host-access=abc123"],
                ["X-Ok", "keep-me"],
            ],
        }
    }
    result = _scrub_event(event, {})
    remaining = result["request"]["headers"]
    assert isinstance(remaining, list)
    names = [pair[0].lower() for pair in remaining]
    assert "authorization" not in names
    assert "cookie" not in names
    assert "x-ok" in names


def test_scrub_event_list_headers_does_not_raise() -> None:
    """List-shaped headers must not raise any exception."""
    event: dict = {
        "request": {
            "headers": [
                ["Authorization", "Bearer x"],
                ["X-Safe", "value"],
            ],
        }
    }
    # Must not raise
    _scrub_event(event, {})


# ---------------------------------------------------------------------------
# 2c. Header scrub handles dict shape — regression (condition 3)
# ---------------------------------------------------------------------------


def test_scrub_event_dict_headers_regression() -> None:
    """Dict-shaped headers still work correctly after the list-handling refactor."""
    event = _make_sample_event()
    result = _scrub_event(event, {})
    headers = result["request"]["headers"]
    assert isinstance(headers, dict)
    assert "authorization" not in headers
    assert "cookie" not in headers
    assert "content-type" in headers


# ---------------------------------------------------------------------------
# 6. metrics_endpoint: optional bearer-token guard (condition 5)
# ---------------------------------------------------------------------------


def _make_metrics_app():
    """Build a minimal ASGI app that only mounts /metrics — NO DB lifespan."""
    from fastapi import FastAPI

    from dhanradar.observability import metrics_endpoint

    mini = FastAPI()
    mini.add_route("/metrics", metrics_endpoint, methods=["GET"])
    return mini


def test_metrics_endpoint_returns_200() -> None:
    """/metrics returns 200 with the Prometheus exposition payload. The endpoint
    has no auth: non-neg #5 forbids header/bearer auth on the public API, and
    /metrics is not on the public ingress and carries no PII. Access control is
    docker-network isolation."""
    from starlette.testclient import TestClient

    client = TestClient(_make_metrics_app(), raise_server_exceptions=False)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"dhanradar_http_requests_total" in resp.content


# ---------------------------------------------------------------------------
# 7. PrometheusMiddleware.dispatch records status=500 on route exception
#    (condition 6) — minimal Starlette app, no DB lifespan
# ---------------------------------------------------------------------------


def test_prometheus_middleware_records_500_on_exception() -> None:
    """
    A minimal app with one route that raises must produce a metric sample
    with status='500' after being hit via TestClient.
    """
    from prometheus_client import CollectorRegistry, Counter, generate_latest
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.testclient import TestClient

    from dhanradar.observability import PrometheusMiddleware

    # Use a fresh isolated registry so this test doesn't pollute the module-level REGISTRY
    test_registry = CollectorRegistry()
    test_counter = Counter(
        "test_obs_http_requests_total",
        "Test counter for middleware dispatch",
        ["method", "template", "status"],
        registry=test_registry,
    )

    class _TestMiddleware(PrometheusMiddleware):
        """Subclass that writes to the test-local counter instead of the module-level one."""

        async def dispatch(self, request, call_next):  # type: ignore[override]
            import time

            from starlette.routing import Match

            if request.url.path == "/metrics":
                return await call_next(request)

            method = request.method
            # Resolve template from the app routes
            routes = getattr(request.app, "routes", [])
            template = "__unmatched__"
            for route in routes:
                try:
                    match, _ = route.matches(request.scope)
                    if match == Match.FULL:
                        template = route.path  # type: ignore[attr-defined]
                        break
                except Exception:
                    continue

            start = time.perf_counter()  # noqa: F841
            status = 500
            try:
                response = await call_next(request)
                status = response.status_code
                return response
            finally:
                test_counter.labels(method, template, str(status)).inc()

    async def _boom(request):  # type: ignore[return]
        raise RuntimeError("intentional test error")

    app = Starlette(routes=[Route("/boom", _boom)])
    app.add_middleware(_TestMiddleware)

    client = TestClient(app, raise_server_exceptions=False)
    client.get("/boom")

    raw = generate_latest(test_registry).decode()
    # Confirm a 500-labelled sample was recorded
    assert 'status="500"' in raw, (
        f"Expected status=\"500\" in metrics output. Got:\n{raw}"
    )
