"""
DhanRadar — ASGI middleware.

RequestIDMiddleware: assigns a request id to every request (honouring an inbound
`X-Request-ID` if present, else generating a UUID), stores it on
`request.state.request_id` for the RFC7807 handlers (errors.py), and echoes it
back as the `X-Request-ID` response header. This is the correlation key across
API logs, Sentry, and the audit trail.
"""

from __future__ import annotations

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

# An inbound request id is echoed into logs, a response header, and the JSON
# error body. Only accept a conservative charset + length so a caller cannot
# inject CRLF (log/response-header forging) or oversized values. Anything else
# is discarded and a fresh UUID is generated.
# NOTE: \Z (not $) — Python's $ also matches just before a trailing newline,
# which would let "abc\n" through and re-open the log-forging vector.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}\Z")


class RequestIDMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID") -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next):
        inbound = request.headers.get(self.header_name)
        request_id = inbound if inbound and _SAFE_REQUEST_ID.match(inbound) else str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[self.header_name] = request_id
        return response
