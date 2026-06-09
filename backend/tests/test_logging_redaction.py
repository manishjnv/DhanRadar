"""
DhanRadar — Structured-logging redaction tests (P1 compliance).

These tests prove that the _redaction_processor in core/logging.py
scrubs or hashes ALL PII / secret material BEFORE a log line is rendered,
for BOTH structlog-native loggers AND stdlib logging.getLogger() callers.

Run:
    cd e:/code/DhanRadar/backend
    python -m pytest tests/test_logging_redaction.py -q
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any

import pytest
import structlog
import structlog.contextvars

# ---------------------------------------------------------------------------
# The module under test
# ---------------------------------------------------------------------------
from dhanradar.core.logging import configure_logging, get_logger, hash_user_ref

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RAW_USER_ID = "123e4567-e89b-12d3-a456-426614174000"
RAW_EMAIL = "victim@example.com"
RAW_PAN = "ABCDE1234F"
RAW_PASSWORD = "hunter2"
# Only the header+payload parts — enough to trigger the JWT pattern
RAW_JWT = "eyJhbGciOiJIUzI1Ni8.eyJzdWIiOiIxMjM0.QWxpY2U"
RAW_COOKIE = "__Host-session=abc.def.ghi"
RAW_OR_KEY = "sk-or-abcdef0123456789abcdef"
RAW_RZP_KEY = "rzp_live_ABCDEF123456"
RAW_PROMPT = "full secret prompt text"
RAW_RESPONSE = "full secret response"
RAW_CAS_BYTES = b"%PDF-1.4 secret bytes"

# Substrings that must NEVER appear in any emitted JSON line
FORBIDDEN = [
    RAW_EMAIL,
    RAW_PAN,
    RAW_PASSWORD,
    # Only check the non-trivial prefix (header.payload portion)
    "eyJhbGciOiJIUzI1Ni8",
    "sk-or-abcdef",
    "rzp_live_ABCDEF",
    "%PDF-1.4",
    RAW_PROMPT,
    RAW_RESPONSE,
    RAW_USER_ID,
]

# Event message that embeds PII — value-based redaction must scrub these too
EVENT_MSG = (
    f"user {RAW_EMAIL} filed PAN {RAW_PAN} token {RAW_JWT}"
)


@pytest.fixture(autouse=True)
def _clear_contextvars():
    """Ensure structlog contextvars don't bleed between tests."""
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()


def _capture_json_lines(emit_fn) -> list[dict[str, Any]]:
    """
    Replace the root logging handler temporarily with one that writes to a
    StringIO buffer, call emit_fn(), then parse and return the JSON lines.

    We work at the stdlib root level because configure_logging() installs a
    StreamHandler there that both structlog and legacy callers share.
    """
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)

    root = logging.getLogger()
    old_handlers = root.handlers[:]
    root.handlers = [handler]
    # Reuse the formatter already on the first real handler (set by configure_logging)
    if old_handlers:
        handler.setFormatter(old_handlers[0].formatter)

    try:
        emit_fn()
        # flush
        handler.flush()
    finally:
        root.handlers = old_handlers

    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    parsed = []
    for ln in lines:
        try:
            parsed.append(json.loads(ln))
        except json.JSONDecodeError:
            # Surface the raw line so test failures are debuggable
            parsed.append({"_raw": ln})
    return parsed


# ---------------------------------------------------------------------------
# Core PII / secrets redaction test
# ---------------------------------------------------------------------------


class TestRedactionFields:
    """All sensitive fields are scrubbed before the line hits stdout."""

    def test_structlog_redaction(self):
        configure_logging(level="DEBUG")
        log = get_logger("test.structlog")

        lines = _capture_json_lines(
            lambda: log.info(
                EVENT_MSG,
                user_id=RAW_USER_ID,
                email=RAW_EMAIL,
                pan=RAW_PAN,
                password=RAW_PASSWORD,
                jwt=RAW_JWT,
                cookie=RAW_COOKIE,
                openrouter_api_key=RAW_OR_KEY,
                razorpay_key=RAW_RZP_KEY,
                prompt=RAW_PROMPT,
                response=RAW_RESPONSE,
                cas_bytes=RAW_CAS_BYTES,
            )
        )

        assert lines, "No log lines were captured"
        combined = json.dumps(lines)

        # 1 — none of the raw forbidden strings appear anywhere
        for forbidden in FORBIDDEN:
            assert forbidden not in combined, (
                f"Raw secret/PII leaked into log: {forbidden!r}"
            )

        # 2 — user_id was hashed (16 hex chars), not redacted to "[REDACTED]"
        record = lines[0]
        assert record.get("user_id") == hash_user_ref(RAW_USER_ID), (
            f"user_id not hashed correctly: {record.get('user_id')!r}"
        )

        # 3 — sentinels present
        assert record.get("email") == "[REDACTED]"
        assert record.get("pan") == "[REDACTED]"
        assert record.get("password") == "[REDACTED]"
        assert record.get("jwt") == "[REDACTED]"
        assert record.get("cookie") == "[REDACTED]"
        assert record.get("openrouter_api_key") == "[REDACTED:key]"
        assert record.get("razorpay_key") in ("[REDACTED]", "[REDACTED:key]"), (
            f"razorpay_key sentinel unexpected: {record.get('razorpay_key')!r}"
        )
        assert record.get("prompt") == "[REDACTED:prompt]"
        assert record.get("response") == "[REDACTED:response]"
        assert record.get("cas_bytes") == "[REDACTED]"

    def test_stdlib_logging_redaction(self):
        """A raw stdlib logging.getLogger() call is also scrubbed."""
        configure_logging(level="DEBUG")
        stdlib_log = logging.getLogger("test.stdlib")

        lines = _capture_json_lines(
            lambda: stdlib_log.info(
                "stdlib test %s",
                RAW_EMAIL,
                extra={
                    "pan": RAW_PAN,
                    "password": RAW_PASSWORD,
                    "openrouter_api_key": RAW_OR_KEY,
                },
            )
        )

        assert lines, "No log lines captured for stdlib logger"
        combined = json.dumps(lines)

        for forbidden in [RAW_EMAIL, RAW_PAN, RAW_PASSWORD, "sk-or-abcdef"]:
            assert forbidden not in combined, (
                f"Raw PII leaked via stdlib logger: {forbidden!r}"
            )

    def test_event_message_value_redaction(self):
        """Value-based regex redaction fires on the event string itself."""
        configure_logging(level="DEBUG")
        log = get_logger("test.event_msg")

        lines = _capture_json_lines(lambda: log.warning(EVENT_MSG))

        assert lines, "No log lines captured"
        combined = json.dumps(lines)

        for forbidden in [RAW_EMAIL, RAW_PAN, "eyJhbGciOiJIUzI1Ni8"]:
            assert forbidden not in combined, (
                f"Event message PII not redacted: {forbidden!r}"
            )

    def test_nested_dict_redaction(self):
        """Redaction recurses into nested dicts."""
        configure_logging(level="DEBUG")
        log = get_logger("test.nested")

        lines = _capture_json_lines(
            lambda: log.info(
                "nested test",
                outer={"inner": {"password": RAW_PASSWORD, "safe": "hello"}},
            )
        )

        assert lines, "No log lines captured"
        combined = json.dumps(lines)
        assert RAW_PASSWORD not in combined, "password inside nested dict leaked"
        assert "hello" in combined, "non-sensitive nested value was over-redacted"

    def test_list_of_dicts_redaction(self):
        """Redaction recurses into lists."""
        configure_logging(level="DEBUG")
        log = get_logger("test.list")

        lines = _capture_json_lines(
            lambda: log.info(
                "list test",
                items=[{"email": RAW_EMAIL}, {"safe": "ok"}],
            )
        )

        assert lines, "No log lines captured"
        combined = json.dumps(lines)
        assert RAW_EMAIL not in combined, "email inside list item leaked"
        assert "ok" in combined, "non-sensitive list value was over-redacted"

    def test_stdlib_positional_pan_in_message(self):
        """A PAN passed as a positional %-arg (no extra=) is scrubbed via the
        event-message value regex (adversarial review M1/N1)."""
        configure_logging(level="DEBUG")
        stdlib_log = logging.getLogger("test.stdlib.positional")

        lines = _capture_json_lines(
            lambda: stdlib_log.warning("user filed PAN=%s phone=%s", RAW_PAN, "9876543210")
        )
        combined = json.dumps(lines)
        assert RAW_PAN not in combined, "PAN in positional %-arg leaked"
        assert "9876543210" not in combined, "bare Indian phone in message leaked"

    def test_phone_value_backstop(self):
        """A bare Indian mobile under a key the rules don't name is still
        scrubbed by the value regex (adversarial review S2)."""
        configure_logging(level="DEBUG")
        log = get_logger("test.phone")

        lines = _capture_json_lines(
            lambda: log.info("contact", contact_number="9876543210", note="call back")
        )
        combined = json.dumps(lines)
        assert "9876543210" not in combined, "phone under contact_number leaked"
        assert "call back" in combined, "non-sensitive note over-redacted"

    def test_identity_keys_hashed(self):
        """owner_id / created_by are hashed, not echoed raw (adversarial S2)."""
        configure_logging(level="DEBUG")
        log = get_logger("test.identity")

        lines = _capture_json_lines(
            lambda: log.info("ownership", owner_id=RAW_USER_ID, created_by=RAW_USER_ID)
        )
        record = lines[0]
        assert RAW_USER_ID not in json.dumps(lines), "raw user UUID leaked under owner_id/created_by"
        assert record.get("owner_id") == hash_user_ref(RAW_USER_ID)
        assert record.get("created_by") == hash_user_ref(RAW_USER_ID)

    def test_tuple_nested_dict_redaction(self):
        """A secret inside a dict nested in a TUPLE is reached by recursion
        (adversarial review N3 — tuples previously passed through unredacted)."""
        configure_logging(level="DEBUG")
        log = get_logger("test.tuple")

        lines = _capture_json_lines(
            lambda: log.info("tuple test", items=({"password": RAW_PASSWORD}, {"safe": "ok"}))
        )
        combined = json.dumps(lines)
        assert RAW_PASSWORD not in combined, "password inside tuple-nested dict leaked"
        assert "ok" in combined, "non-sensitive tuple value over-redacted"


# ---------------------------------------------------------------------------
# Idempotency test
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_configure_logging_twice_no_duplicate_handlers(self):
        """Calling configure_logging() twice must not add duplicate handlers."""
        configure_logging(level="INFO")
        count_after_first = len(logging.getLogger().handlers)

        configure_logging(level="INFO")
        count_after_second = len(logging.getLogger().handlers)

        assert count_after_first == count_after_second, (
            f"Duplicate handlers added: {count_after_first} → {count_after_second}"
        )

    def test_configure_logging_twice_no_double_emit(self):
        """Calling configure_logging() twice must not double-emit lines."""
        configure_logging(level="DEBUG")
        configure_logging(level="DEBUG")

        log = get_logger("test.idempotent")
        lines = _capture_json_lines(lambda: log.info("idempotency check"))

        assert len(lines) == 1, (
            f"Expected 1 line, got {len(lines)} (possible double-emit)"
        )


# ---------------------------------------------------------------------------
# Contextvar propagation test
# ---------------------------------------------------------------------------


class TestContextvarPropagation:
    def test_request_id_in_output(self):
        """A bound contextvar appears in every subsequent log line."""
        configure_logging(level="DEBUG")
        structlog.contextvars.bind_contextvars(request_id="rid-test")
        log = get_logger("test.ctx")

        lines = _capture_json_lines(lambda: log.info("ctx propagation"))

        structlog.contextvars.clear_contextvars()

        assert lines, "No log lines captured"
        record = lines[0]
        assert record.get("request_id") == "rid-test", (
            f"request_id not found in log output: {record}"
        )


# ---------------------------------------------------------------------------
# hash_user_ref unit tests
# ---------------------------------------------------------------------------


class TestHashUserRef:
    def test_known_hash(self):
        import hashlib
        uid = "abc123"
        expected = hashlib.sha256(uid.encode()).hexdigest()[:16]
        assert hash_user_ref(uid) == expected

    def test_empty_input(self):
        assert hash_user_ref("") == ""

    def test_none_like_falsy(self):
        # hash_user_ref is typed str but the spec says return "" for falsy
        # We pass an empty string as the falsy case; None would be a type error
        assert hash_user_ref("") == ""

    def test_returns_16_chars(self):
        result = hash_user_ref("some-user-id")
        assert len(result) == 16
        assert result.isalnum()  # hex chars only
