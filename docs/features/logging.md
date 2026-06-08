# Feature — Centralised Structured Logging

**Status:** P1 built (structlog JSON + request_id correlation + two-layer redaction +
Docker rotation); P2–P4 deferred · **Phase:** B57 · **Last updated:** 2026-06-08

## Purpose & scope

Two-tier observability model:

- **Tier 1 — Debug stream (P1, this doc):** every log line is a structured JSON object
  emitted to stdout, captured by Docker `json-file`, and readable via `docker logs`. All
  ~19 existing `logging.getLogger()` call sites are covered without code changes.
- **Tier 2 — Centralised collection (P3, deferred):** Grafana Loki collector + dashboard.
  P3 also upgrades `request_id` to W3C 16-byte OpenTelemetry trace IDs.

P1 DOES NOT add new audit tables or Alembic migrations (those are P2:
`audit.admin_actions`, `payment_events`, `security_events`). P4 = alerting + retention
automation.

## Module API

`backend/dhanradar/core/logging.py` — imports stdlib + structlog only (module isolation).

| Symbol | Signature | Notes |
|---|---|---|
| `configure_logging` | `configure_logging(*, level="INFO") -> None` | Idempotent; call once at app startup. Clears root handlers and installs a single JSON handler. |
| `get_logger` | `get_logger(name=None) -> BoundLogger` | Preferred call site for all new log lines. |
| `hash_user_ref` | `hash_user_ref(user_id: str) -> str` | Returns `sha256(user_id)[:16]`. Pass this as `user_ref=` — NEVER a raw `user_id`. |

## Processor chain

The same chain serves both structlog-native loggers and all stdlib `logging.getLogger()`
callers (via `ProcessorFormatter` + `foreign_pre_chain`):

```
merge_contextvars
  → add_log_level
  → TimeStamper(fmt="iso", utc=True)
  → CallsiteParameterAdder
  → _redaction_processor          ← COMPLIANCE-CRITICAL (see below)
  → JSONRenderer
```

One JSON object per line to stdout. `ProcessorFormatter` wires the chain onto the stdlib
root logger so existing callers emit redacted JSON without modification.

## Redaction filter (`_redaction_processor`)

COMPLIANCE-CRITICAL — DPDP non-neg #10. Runs before `JSONRenderer`; never raises (on
internal error returns a `[REDACTED_ERROR]` sentinel that preserves only the non-PII
correlation keys `request_id`, `job_id`, `task`, `task_id`, `user_ref`). Recurses
dict / list / tuple / set.

### Key-based rules

| Key pattern (case-insensitive, substring) | Action |
|---|---|
| `user_id`, `uid`, `userid`, `owner_id`, `created_by`, `actor_id`, `recipient_id` | SHA-256[:16] hash |
| `email`, `phone`, `mobile`, `contact_number`, `msisdn`, `whatsapp`, `pan` | `[REDACTED]` |
| `password`, `otp`, `totp_secret`, `secret`, `authorization`, `cookie`, `jwt`, `token` | `[REDACTED]` |
| `api_key`, `openrouter`, `razorpay`, `r2_`, `aws_secret`, `smtp` | `[REDACTED:key]` |
| `prompt`, `messages` | `[REDACTED:prompt]` |
| `response`, `completion` | `[REDACTED:response]` |
| `cas_bytes`, `file_bytes`, `multipart`, `raw_body`; any `bytes` value | `[REDACTED]` |

### Value-based regex (applied to every string value and the event message)

| Pattern | Redacts |
|---|---|
| `eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+` | JWT |
| `[A-Z]{5}[0-9]{4}[A-Z]` | PAN |
| `[6-9]\d{9}` | Indian mobile |
| `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` | Email |
| `sk-[A-Za-z0-9]{20,}`, `sk-or-[A-Za-z0-9]{20,}` | OpenAI / OpenRouter keys |
| `rzp_(test\|live)_[A-Za-z0-9]+` | Razorpay keys |
| `AKIA[0-9A-Z]{16}` | AWS access key |

## Correlation contract

```
HTTP request arrives
  └─ RequestIDMiddleware (PURE ASGI — NOT BaseHTTPMiddleware)
       binds  request_id=<uuid4>           [cleared in finally]
  └─ deps.current_user_or_anonymous
       binds  user_ref=hash_user_ref(uid)  [auth resolves post-routing]

Celery task enqueued
  └─ request_id propagated as task kwarg
  └─ task_prerun signal   → binds  request_id, user_ref
  └─ task_postrun signal  → clears both
  └─ task_failure signal  → clears both
  └─ task_revoked signal  → clears both   ← M2 fix (see RCA)

AI gateway
  └─ gateway.complete(..., request_id=request_id)
  └─ compliance.record_served_label persists request_id in ai_recommendation_audit

CAS worker pipeline
  └─ user_ref bound explicitly after job load
```

`RequestIDMiddleware` is PURE ASGI (not `BaseHTTPMiddleware`) to avoid breaking async
SQLAlchemy sessions — this is a load-bearing design constraint (do not change).

P1 decision: keep UUID4 `request_id`. OpenTelemetry W3C 16-byte trace IDs are deferred
to P3 (no OTel dependency introduced).

## Docker log rotation

`docker-compose.yml` defines an `x-logging: &default-logging` YAML anchor:

```yaml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "50m"
    max-file: "5"
```

Applied to all 9 services. Worst-case ~250 MB per container, ~2 GB total — within the
3 GB KVM4 box cap. No external log collector in P1.

## How to add a log line

```python
from dhanradar.core.logging import get_logger, hash_user_ref

_slog = get_logger(__name__)

# Correct — structured fields, hashed user reference:
_slog.info("cas_job_started", job_id=job_id, user_ref=hash_user_ref(str(user_id)))

# WRONG — never %-interpolate PII into the message string:
# logging.info("job started for user %s", user_id)   # not caught by value-regex
# _slog.warning("failed for %s" % user_id)           # not caught by value-regex
```

Rules:

- Always call `get_logger(__name__)` at module level; pass it as `_slog`.
- Pass `user_ref=hash_user_ref(uid)` as a structured keyword argument. Never pass a raw
  `user_id` / `uid` in the event message string (%-interpolated values bypass the
  key-based redaction rules and may not be caught by value-regex if the format is novel).
- For Celery tasks, rely on the `task_prerun` contextvars bind — `request_id` and
  `user_ref` are already in context; you do not need to pass them explicitly on every
  log call within a task.
- Never log `bytes` payloads directly — pass a length or a content-hash instead.

## Roadmap

| Phase | Scope |
|---|---|
| P1 (done) | structlog JSON, stdlib unification, two-layer redaction, UUID4 correlation, Docker rotation |
| P2 | `audit.admin_actions`, `payment_events`, `security_events` tables; traceback-scrubbing processor (residual risk 2) |
| P3 | Grafana Loki collector; W3C 16-byte OTel trace IDs replacing UUID4 `request_id` |
| P4 | Alerting rules; retention automation; log-level hot-reload |

## Known limitations / residual risks (P1-accepted)

1. **Unstructured UUID in message string.** A raw UUID %-interpolated into a log *message*
   string under no structured key is not regex-caught — UUID regex was deliberately omitted
   so `job_id` stays visible in logs. Mitigated by hashing at the known call sites and the
   key-based rules; the "never %-interpolate PII" rule above prevents new occurrences.
2. **Traceback PII leak.** Exception tracebacks are appended by `ProcessorFormatter` AFTER
   the redaction processor runs. An exception that embeds PII in its `.args` message string
   could leak. This codebase raises opaque error codes; a traceback-scrubbing processor is
   deferred to P2.
3. **Base64-encoded bytes under arbitrary keys.** A `bytes` value is caught and redacted,
   but a base64-encoded string stored under an unrecognised key is not. This relies on
   call-site discipline (do not log encoded payloads).
4. **`configure_logging()` clears root handlers.** This is intentional — it enforces a
   single JSON handler. A side effect is that any separately-configured uvicorn access-log
   file handler is dropped. Uvicorn's access logs are still emitted to stdout via the
   unified chain.

## Verification

`backend/tests/test_logging_redaction.py` — 16 tests covering: key-based hash/redact rules;
value-regex (JWT, PAN, mobile, email, API keys); recursion into nested dict/list/tuple/set;
safe-error sentinel preserves correlation keys; `bytes` value redaction; event-message
value-regex; `configure_logging` idempotency.

## Changelog

- 2026-06-08 — P1 built (B57): `core/logging.py` (configure\_logging, get\_logger,
  hash\_user\_ref); structlog processor chain + stdlib unification via ProcessorFormatter;
  two-layer \_redaction\_processor (16 key rules, 8 value-regex patterns, recursion,
  safe-error sentinel); UUID4 request\_id correlation wired end-to-end (middleware →
  Celery → gateway → audit); Docker json-file rotation anchor (9 services). Tier-B
  adversarial review (Sonnet takeover; codex n/a) ACCEPT-WITH-CONDITIONS — M1 raw
  user\_id %-interpolation fixed in tasks/mf.py + billing/service.py; M2 task\_revoked
  contextvar clear added; phone regex + tuple/set recursion + safe-error sentinel applied.
  ADR-0028. Ledger: `reviews/b57-p1-logging.md`.
