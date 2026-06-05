"""
DhanRadar — RFC7807 problem+json error handling.

Canonical error contract (docs/project-state/CANONICAL_OPENAPI_ALIGNMENT.md §4):
every error response is `application/problem+json` with at least
`{type, title, status, request_id}` and an optional `detail`.

Backward-compatibility (important): the existing handlers raise
`HTTPException(status, detail="<machine_code>")` (e.g. "missing_signature",
"invalid_credentials") and tests assert `resp.json()["detail"] == "<code>"`.
This module therefore PRESERVES the original `detail` string verbatim in the
Problem body and derives `type` from it when it looks like a machine code, so
no existing response contract is broken — we only ADD fields.

Security: the unhandled-exception handler never leaks `str(exc)` / stack traces
/ PII into the response — it returns a generic `internal` problem and logs the
detail server-side keyed by request_id.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"
_ERROR_BASE = "https://dhanradar.com/errors/"
# A "machine code" detail like invalid_signature / upgrade_required.
_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
# RFC7807 reserved members that extension data must never overwrite.
_RESERVED_MEMBERS = frozenset({"type", "title", "status", "request_id", "instance", "detail"})

# Canonical status → type-slug / title (CANONICAL_OPENAPI_ALIGNMENT §4).
_STATUS_SLUG: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    402: "upgrade_required",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "unprocessable",
    429: "rate_limited",
    500: "internal",
    502: "upstream_unavailable",
    503: "upstream_unavailable",
}
_STATUS_TITLE: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
}


def get_request_id(request: Request) -> str:
    """Return the request_id set by RequestIDMiddleware, or a fresh one."""
    rid = getattr(request.state, "request_id", None)
    return rid if isinstance(rid, str) and rid else str(uuid.uuid4())


def build_problem(
    status: int,
    request_id: str,
    *,
    detail: Optional[Any] = None,
    type_slug: Optional[str] = None,
    title: Optional[str] = None,
    instance: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Construct an RFC7807 problem body (dict)."""
    slug = type_slug or _STATUS_SLUG.get(status, "error")
    body: dict[str, Any] = {
        "type": f"{_ERROR_BASE}{slug}",
        "title": title or _STATUS_TITLE.get(status, "Error"),
        "status": status,
        "request_id": request_id,
    }
    if detail is not None:
        body["detail"] = detail
    if instance:
        body["instance"] = instance
    if extra:
        # Extension members (RFC7807 §3.2) — e.g. upgrade_url, errors.
        # Never let extension members overwrite the reserved Problem members
        # (a dict-detail raise must not be able to forge type/status/request_id).
        safe_extra = {k: v for k, v in extra.items() if k not in _RESERVED_MEMBERS}
        body.update(safe_extra)
    return body


def _problem_response(status: int, body: dict[str, Any], headers: Optional[dict] = None) -> JSONResponse:
    # jsonable_encoder guarantees the body is serializable — a non-serializable
    # extension value can never crash the handler mid-response (→ raw 500).
    return JSONResponse(
        status_code=status,
        content=jsonable_encoder(body),
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Map (Starlette/FastAPI) HTTPException → problem+json, preserving detail."""
    status = exc.status_code
    detail = exc.detail
    type_slug: Optional[str] = None
    detail_value: Optional[Any] = None
    extra: dict[str, Any] = {}

    if isinstance(detail, dict):
        # e.g. tier gate: {"error": "upgrade_required", "upgrade_url": "/pricing"}
        err = detail.get("error")
        if isinstance(err, str) and _CODE_RE.match(err):
            type_slug = err
            detail_value = err  # keep the machine code accessible
        extra = {k: v for k, v in detail.items() if k != "error"}
    elif isinstance(detail, str):
        detail_value = detail
        if _CODE_RE.match(detail):
            type_slug = detail
    elif detail is not None:
        detail_value = str(detail)

    rid = get_request_id(request)
    body = build_problem(
        status,
        rid,
        detail=detail_value,
        type_slug=type_slug,
        instance=request.url.path,
        extra=extra or None,
    )
    return _problem_response(status, body, headers=getattr(exc, "headers", None))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Map request validation errors → 422 problem with a trimmed errors list."""
    rid = get_request_id(request)
    # Trim each error to loc/msg/type only — never echo `input`/`ctx` (may hold PII).
    trimmed = [
        {"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")}
        for e in exc.errors()
    ]
    body = build_problem(
        422,
        rid,
        detail="validation_error",
        type_slug="validation_error",
        instance=request.url.path,
        extra={"errors": jsonable_encoder(trimmed)},
    )
    return _problem_response(422, body)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all → generic 500 problem. NEVER leak the exception detail."""
    rid = get_request_id(request)
    logger.exception("Unhandled exception [request_id=%s] %s", rid, request.url.path)
    body = build_problem(
        500,
        rid,
        detail="internal",
        type_slug="internal",
        instance=request.url.path,
    )
    return _problem_response(500, body)
