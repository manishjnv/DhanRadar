# Review ledger — B57 P1 centralised structured logging

- **Change-id:** b57-p1-logging
- **Date:** 2026-06-08
- **Branch:** `fix/cas-dedup-and-logging-plan`
- **Governance tier:** **Tier-B** (load-bearing paths: ASGI middleware, Celery signal
  wiring, AI gateway, docker-compose; compliance/DPDP: two-layer PII redaction filter).
  Required reviews: Builder + Architect + **Security** + **Compliance**. Inline in-session
  (load-bearing exception — not deferred to the phase audit).

## What landed

New module `backend/dhanradar/core/logging.py` (stdlib + structlog only — module
isolation). Provides `configure_logging(*, level="INFO")` (idempotent),
`get_logger(name=None)`, and `hash_user_ref(user_id) -> sha256(user_id)[:16]`.

Structlog processor chain shared by structlog-native loggers AND all ~19 existing stdlib
`logging.getLogger()` callers via `ProcessorFormatter` + `foreign_pre_chain`:
`merge_contextvars` → `add_log_level` → `TimeStamper(iso,utc)` → `CallsiteParameterAdder`
→ `_redaction_processor` → `JSONRenderer`. One JSON object per line to stdout.

Two-layer `_redaction_processor` (COMPLIANCE-CRITICAL, DPDP): key-based rules (user-id
fields hashed; contact/PAN/credential/API-key/prompt/response/binary fields redacted) plus
value-based regex on every string and the event message (JWT, PAN, Indian mobile, email,
API-key patterns). Recurses dict/list/tuple/set; never raises; safe-error sentinel preserves
correlation keys. 16 unit tests in `backend/tests/test_logging_redaction.py`.

`request_id` (UUID4, existing) bound in `RequestIDMiddleware` (PURE ASGI — NOT
`BaseHTTPMiddleware`); cleared in `finally`. `user_ref = hash_user_ref(user_id)` bound in
`deps.current_user_or_anonymous` and the CAS worker pipeline. Propagated to Celery as a
task kwarg; re-bound in `task_prerun`; cleared in `task_postrun`, `task_failure`, and
`task_revoked`. Threaded into `gateway.complete(..., request_id=)` and persisted in
`ai_recommendation_audit` via `compliance.record_served_label`.

Docker log rotation: `x-logging: &default-logging` YAML anchor (`json-file` driver,
`max-size: 50m`, `max-file: 5`) applied to all 9 services in `docker-compose.yml`.
Worst-case ~2 GB total — within the 3 GB KVM4 box cap.

P1 scope only. P2 (structured audit tables), P3 (Grafana Loki + OTel trace IDs), and P4
(alerting + retention) are deferred.

## Builder + Architect

Builder = Opus (doc/plan phase); implementation in load-bearing paths (middleware, Celery
signals, gateway threading, compose anchor). Architect = Opus line-by-line diff review.

Architect review confirmed: `RequestIDMiddleware` correctly uses PURE ASGI (not
`BaseHTTPMiddleware`) preserving async SQLAlchemy session behaviour; processor chain order
is correct (`_redaction_processor` before `JSONRenderer`); `configure_logging()` idempotency
guard is sound; contextvar clear is present on all three Celery exit signals after M2 fix;
Docker anchor syntax is valid and applied to all services.

## Deterministic gates

- **Tests:** 16 redaction unit tests (`test_logging_redaction.py`) — all pass. Existing
  relevant suites (middleware, deps, gateway, compliance) — no regressions.
- **ruff:** no new violations on changed files.
- **Secrets scan:** no credential patterns in new code.
- **Anti-pattern sweep (`ci_guards.py` + `anti_pattern_sweep.py`):** clean — no advisory
  verbs, no bearer auth, no ES references, no bare `/v1` paths in new files.
- **docker-compose validation:** `docker compose config` resolves the `x-logging` anchor
  correctly across all 9 services.
- **markdownlint:** four new/updated doc files pass under `.markdownlint.json`.

## Security — **ACCEPT-WITH-CONDITIONS** (all conditions applied in-session)

Codex was unavailable (ChatGPT-plan entitlement error on every model). Per the sanctioned
fallback ladder, an **independent Sonnet adversarial takeover** ran with a self-contained
threat-model prompt (attacker goal: extract PII/credentials from log output; attacker has
write access to a log call site or can trigger an exception with a PII-laden message).
Verdict **ACCEPT-WITH-CONDITIONS**.

**MUST-FIX conditions (both applied before any commit):**

- **(M1) Raw user UUID %-interpolated into log message strings.** `tasks/mf.py` and
  `billing/service.py` each called a logger with a raw user UUID in the message string,
  bypassing key-based redaction. Fix: replaced with `user_ref=hash_user_ref(uid)` structured
  keyword arguments. See RCA `docs/rca/README.md` (2026-06-08 P1 logging entry).
- **(M2) `task_revoked` had no contextvar clear.** A revoked Celery task left `request_id`
  and `user_ref` bound in contextvars, so the next task on the same worker thread could log
  under the wrong identity. Fix: added `@task_revoked.connect` handler calling
  `structlog.contextvars.clear_contextvars()` in `celery_app.py`. See same RCA entry.

**SHOULD-FIX conditions (all applied in-session):**

- Phone number value-regex backstop added to `_redaction_processor`.
- Recursion extended to cover `tuple` and `set` values (not just dict/list).
- Safe-error sentinel on `_redaction_processor` internal exception preserves only the
  non-PII correlation keys (`request_id`, `job_id`, `task`, `task_id`, `user_ref`) rather
  than leaking the full event dict.

**Vector-by-vector confirmed CLEAN (post-fix):** JWT/PAN/mobile/email/API-key value
extraction; nested dict/list/tuple/set recursion; `bytes` value redaction; safe-error
sentinel; contextvar isolation across Celery tasks; `configure_logging()` idempotency;
Docker json-file driver (no remote log target introduces exfiltration surface in P1).

## Compliance (Opus) — **ACCEPT**

- **Non-neg #10 (DPDP):** the two-layer redaction filter is the enforcement mechanism for
  PII in logs. Key-based rules hash user identifiers and redact contact/credential data.
  Value-based regex provides a backstop for known PII patterns appearing in unstructured
  strings. The filter is test-enforced. Four accepted residual risks are documented in
  `docs/features/logging.md` (Known limitations) and in ADR-0028 Consequences.
- **Non-neg #1 (no advisory verbs):** no new advisory vocabulary in log messages or event
  strings in the changed files.
- **Non-neg #2 (no numeric in DOM):** logging is a server-side concern; no client surface
  affected.
- **Non-neg #5 (auth):** `RequestIDMiddleware` binds `request_id` only — no auth data.
  `user_ref` is a SHA-256[:16] hash, not a reversible identifier.
- **Non-neg #7 (module isolation):** `core/logging.py` imports only stdlib and structlog;
  no cross-module ORM or service imports.
- **DPDP residual (accepted):** exception tracebacks are appended by `ProcessorFormatter`
  AFTER the redaction processor. An exception embedding PII in its message string could
  leak. This codebase raises opaque error codes; a traceback-scrubbing processor is
  deferred to P2 and tracked in BLOCKERS.

## Residual risks accepted for P1

1. Unstructured UUID in message string — not regex-caught (UUID regex omitted deliberately);
   mitigated by call-site hashing discipline and key rules.
2. Exception traceback PII — deferred to P2 traceback-scrubbing processor.
3. Base64-encoded bytes under arbitrary keys — relies on call-site discipline.
4. `configure_logging()` drops uvicorn access-log file handler — intentional; access logs
   still emit to stdout via the unified chain.

## Status

**Merge-eligible** (deterministic gates green + Tier-B reviews pass + all MUST-FIX and
SHOULD-FIX conditions applied in-session). **NOT deploy-eligible** until the Phase-7 §5
pre-deploy adversarial gate clears and separate explicit human approval is given. No
merge/deploy performed this session (human-gated). ADR-0028 recorded.
