"""
DhanRadar — Centralised structured-JSON logging with PII/secret redaction (P1).

Design goals
------------
* ONE JSON object per line on stdout — structlog renders it; stdlib
  ``logging.getLogger()`` callers are routed through the same chain so legacy
  code gains redaction and contextvars automatically.
* Compliance-critical ``_redaction_processor`` runs BEFORE the line is
  rendered, in BOTH the structlog chain and the stdlib foreign_pre_chain
  (defense-in-depth: a raw ``logging.info("pan=%s", pan)`` is also scrubbed).
* ``hash_user_ref`` replaces user IDs with a 16-hex-char SHA-256 prefix —
  opaque enough for privacy, stable enough for log correlation.
* ``configure_logging`` is idempotent: safe to call from tests and app startup.

Public API imported by other modules
-------------------------------------
    from dhanradar.core.logging import configure_logging, get_logger, hash_user_ref

Module isolation: this file imports ONLY stdlib + structlog.
"""

from __future__ import annotations

import hashlib
import logging
import re
import sys
from typing import Any

import structlog
import structlog.contextvars
import structlog.processors
import structlog.stdlib

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

_configured: bool = False

# ---------------------------------------------------------------------------
# Compiled regexes for value-based redaction (module-level = compiled once)
# ---------------------------------------------------------------------------

_RE_JWT = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_RE_PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
# Indian mobile (10 digits, starts 6-9) — value-based backstop for a phone that
# lands under a key the key-rules don't recognise (e.g. "contact_number"). The
# 6-9 start + word boundaries avoid eating 10-digit epochs/amounts.
_RE_PHONE = re.compile(r"\b[6-9]\d{9}\b")
_RE_EMAIL = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_RE_APIKEY = re.compile(
    r"sk-or-[A-Za-z0-9_-]{10,}"
    r"|sk-[A-Za-z0-9_-]{20,}"
    r"|rzp_(test|live)_[A-Za-z0-9]+"
    r"|AKIA[0-9A-Z]{16}"
)

# Keys whose values must NEVER reach the log stream — checked case-insensitively
# as substring matches.  ORDER MATTERS: the loop is first-match, so a more
# specific trigger must appear BEFORE a more general one that is its substring
# (e.g. "totp_secret" before "secret"). A wrong order never causes a LEAK here
# (both still redact) — only a less precise sentinel — but keep specifics first.
#
# Each entry is (substring_trigger, replacement_sentinel).
_KEY_RULES: list[tuple[str, str]] = [
    # Identity / user — hashed so correlation survives without exposing the id.
    ("user_id",     "__HASH__"),
    ("userid",      "__HASH__"),
    ("owner_id",    "__HASH__"),
    ("created_by",  "__HASH__"),
    ("actor_id",    "__HASH__"),
    ("recipient_id", "__HASH__"),
    # Note: bare "uid" is intentionally NOT substring-matched to avoid hitting
    # innocent keys like "fluid", "build_id"; exact match only for uid.
    # PAN / contact
    ("email",       "[REDACTED]"),
    ("phone",       "[REDACTED]"),
    ("mobile",      "[REDACTED]"),
    ("contact_number", "[REDACTED]"),
    ("msisdn",      "[REDACTED]"),
    ("whatsapp",    "[REDACTED]"),
    ("pan",         "[REDACTED]"),
    # Auth secrets
    ("password",    "[REDACTED]"),
    ("passwd",      "[REDACTED]"),
    ("pwd",         "[REDACTED]"),
    ("otp",         "[REDACTED]"),
    ("totp_secret", "[REDACTED]"),
    ("secret",      "[REDACTED]"),
    ("authorization", "[REDACTED]"),
    ("cookie",      "[REDACTED]"),
    ("jwt",         "[REDACTED]"),
    ("token",       "[REDACTED]"),
    ("access_token",    "[REDACTED]"),
    ("refresh_token",   "[REDACTED]"),
    # Infra / vendor keys
    ("api_key",     "[REDACTED:key]"),
    ("apikey",      "[REDACTED:key]"),
    ("openrouter",  "[REDACTED:key]"),
    ("razorpay",    "[REDACTED:key]"),
    ("r2_",         "[REDACTED:key]"),
    ("aws_secret",  "[REDACTED:key]"),
    ("smtp",        "[REDACTED:key]"),
    # LLM payloads
    ("prompt",      "[REDACTED:prompt]"),
    ("messages",    "[REDACTED:prompt]"),
    ("response",    "[REDACTED:response]"),
    ("completion",  "[REDACTED:response]"),
    # Raw bytes / uploads
    ("cas_bytes",   "[REDACTED]"),
    ("file_bytes",  "[REDACTED]"),
    ("multipart",   "[REDACTED]"),
    ("raw_body",    "[REDACTED]"),
]

# Exact-match set for "uid" so it fires only when the key IS "uid"
_UID_EXACT = frozenset({"uid"})


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


def hash_user_ref(user_id: str) -> str:
    """Return the first 16 hex chars of SHA-256(user_id).

    Returns ``""`` for falsy input (empty string, None-like).  This value is
    safe to store in structured log lines for correlation without exposing PII.
    """
    if not user_id:
        return ""
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Redaction processor — THE compliance filter
# ---------------------------------------------------------------------------


def _redact_value(key: str, value: Any) -> Any:  # noqa: ANN401
    """Apply key-based rules to a single (key, value) pair.

    Returns the (possibly replaced) value.  Does NOT recurse — recursion is
    handled by ``_redact_recursive``.
    """
    key_lower = key.lower()

    # Bytes → always redacted regardless of key name
    if isinstance(value, (bytes, bytearray)):
        return "[REDACTED]"

    # Exact uid match
    if key_lower in _UID_EXACT:
        return hash_user_ref(str(value))

    for trigger, sentinel in _KEY_RULES:
        if trigger in key_lower:
            if sentinel == "__HASH__":
                return hash_user_ref(str(value))
            return sentinel

    # Value-based regex scan on strings only (key not matched above)
    if isinstance(value, str):
        value = _RE_JWT.sub("[REDACTED]", value)
        value = _RE_PAN.sub("[REDACTED]", value)
        value = _RE_PHONE.sub("[REDACTED]", value)
        value = _RE_EMAIL.sub("[REDACTED]", value)
        value = _RE_APIKEY.sub("[REDACTED:key]", value)

    return value


def _redact_recursive(obj: Any) -> Any:  # noqa: ANN401
    """Recursively redact a value that may be a dict, list, or scalar."""
    if isinstance(obj, dict):
        return {k: _redact_value(k, _redact_recursive(v)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        # No key context for items, but we DO recurse into nested dicts and
        # apply value-based regex to strings. tuple/set are normalised to list
        # (a dict nested inside a tuple would otherwise pass through unredacted,
        # and set/frozenset are not JSON-serialisable anyway).
        return [_redact_recursive(item) for item in obj]
    if isinstance(obj, (bytes, bytearray)):
        return "[REDACTED]"
    if isinstance(obj, str):
        v = _RE_JWT.sub("[REDACTED]", obj)
        v = _RE_PAN.sub("[REDACTED]", v)
        v = _RE_PHONE.sub("[REDACTED]", v)
        v = _RE_EMAIL.sub("[REDACTED]", v)
        v = _RE_APIKEY.sub("[REDACTED:key]", v)
        return v
    return obj


def _redaction_processor(
    logger: Any,  # noqa: ANN401
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """structlog processor that scrubs/hashes PII and secrets.

    Runs in BOTH the structlog chain (for structlog callers) and the stdlib
    foreign_pre_chain (for ``logging.getLogger()`` callers).

    Never raises — a bug in here must not crash the application's logging.
    """
    try:
        redacted: dict[str, Any] = {}
        for k, v in event_dict.items():
            if k == "event":
                # Apply value-based regex to the human-readable message
                redacted[k] = _redact_recursive(v) if isinstance(v, str) else v
            else:
                # Recurse into the value first, then apply key-based rules to
                # the top-level key so nested sub-keys are handled before the
                # parent key hides everything.
                inner = _redact_recursive(v)
                redacted[k] = _redact_value(k, inner)
        return redacted
    except Exception:  # noqa: BLE001
        # A redaction bug must NOT leak the raw event_dict. Emit a safe sentinel,
        # but carry forward the non-PII correlation keys so the error line is
        # still attributable to a request/job (request_id/job_id are UUIDs;
        # user_ref is already hashed — none are raw PII).
        safe = {
            k: event_dict[k]
            for k in ("request_id", "job_id", "task", "task_id", "user_ref", "log_level")
            if k in event_dict
        }
        safe["event"] = "[REDACTION_ERROR]"
        safe.setdefault("log_level", method_name)
        return safe


# ---------------------------------------------------------------------------
# Shared processor chain (used by both structlog and stdlib foreign_pre_chain)
# ---------------------------------------------------------------------------

_SHARED_CHAIN = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.CallsiteParameterAdder(
        {
            structlog.processors.CallsiteParameter.FILENAME,
            structlog.processors.CallsiteParameter.FUNC_NAME,
            structlog.processors.CallsiteParameter.LINENO,
        }
    ),
    _redaction_processor,
]


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def configure_logging(*, level: str = "INFO") -> None:
    """Configure structlog + stdlib root logger to emit redacted JSON lines.

    Idempotent: a second call is a no-op (guarded by ``_configured`` flag).
    Both structlog-native loggers and any ``logging.getLogger()`` callers in
    existing code emit through the same processor chain, so PII redaction and
    contextvar enrichment are applied uniformly.
    """
    global _configured  # noqa: PLW0603
    if _configured:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # ------------------------------------------------------------------
    # stdlib root handler with ProcessorFormatter
    # The foreign_pre_chain handles log records that arrive from plain
    # ``logging.getLogger()`` callers BEFORE structlog sees them.
    # ------------------------------------------------------------------
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_SHARED_CHAIN,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Clear existing handlers to avoid double-emit on re-configure attempts
    # (the idempotency guard means this only runs once, but defence-in-depth).
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)

    # ------------------------------------------------------------------
    # structlog configuration
    # ------------------------------------------------------------------
    structlog.configure(
        processors=[
            *_SHARED_CHAIN,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str | None = None):  # noqa: ANN201
    """Return a structlog logger, optionally named.

    Drop-in replacement for ``logging.getLogger()`` in new code.  The returned
    logger automatically picks up bound contextvars (request_id, user_ref, …).
    """
    return structlog.get_logger(name)
