"""
DhanRadar — ASGI middleware.

RequestIDMiddleware: assigns a request id to every request (honouring an inbound
`X-Request-ID` if present, else generating a UUID), stores it on
`request.state.request_id` (via the ASGI scope) for the RFC7807 handlers
(errors.py), and echoes it back as the `X-Request-ID` response header. This is
the correlation key across API logs, Sentry, and the audit trail.

Implementation note — this is a PURE ASGI middleware, deliberately NOT
`starlette.middleware.base.BaseHTTPMiddleware`. BaseHTTPMiddleware runs the
downstream app inside a separate anyio task, which breaks request-scoped async
SQLAlchemy/asyncpg sessions ("got Future attached to a different loop" /
"another operation is in progress"). A pure ASGI middleware runs the app in the
same task, so it is safe with the async DB sessions and adds ~no overhead.
"""

from __future__ import annotations

import re
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send
from structlog.contextvars import bind_contextvars, clear_contextvars

# An inbound request id is echoed into logs, a response header, and the JSON
# error body. Only accept a conservative charset + length so a caller cannot
# inject CRLF (log/response-header forging) or oversized values. Anything else
# is discarded and a fresh UUID is generated.
# NOTE: \Z (not $) — Python's $ also matches just before a trailing newline,
# which would let "abc\n" through and re-open the log-forging vector.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}\Z")


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID") -> None:
        self.app = app
        self.header_name = header_name
        self._header_lower = header_name.lower().encode("latin-1")
        self._header_raw = header_name.encode("latin-1")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        inbound: str | None = None
        for key, value in scope.get("headers", []):
            if key == self._header_lower:
                inbound = value.decode("latin-1", "ignore")
                break

        request_id = (
            inbound if inbound and _SAFE_REQUEST_ID.match(inbound) else str(uuid.uuid4())
        )
        # request.state is backed by scope["state"].
        scope.setdefault("state", {})["request_id"] = request_id
        rid_bytes = request_id.encode("latin-1")
        header_lower = self._header_lower
        header_raw = self._header_raw

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (k, v) for (k, v) in message.get("headers", []) if k != header_lower
                ]
                headers.append((header_raw, rid_bytes))
                message["headers"] = headers
            await send(message)

        # user_ref is NOT bound here — auth runs later in a route dependency (deps.py).
        bind_contextvars(request_id=request_id)
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Clear on exit to prevent cross-request context leakage on reused
            # asyncio tasks (e.g. anyio worker threads in Starlette's routing).
            clear_contextvars()
