# DhanRadar — Log Management Plan (design, not yet implemented)

**Status:** PLAN — not implemented. Picked up by a future session; see `BLOCKERS.md`.
**Date:** 2026-06-08
**Scope:** Defines two separated log streams (compliance ledger + operational debug), correlation
propagation, event taxonomy, storage/retention, and a phased build sequence.
This document is self-contained — a fresh session can implement from it directly.

---

## 1. Goals and principles

Two **strictly separate** streams — they are never mixed.

### Compliance ledger (Tier 1)

- The bare minimum required for SEBI record-keeping and DPDP audit trails.
- 7-year retention, India-resident (Mumbai Postgres), append-only, tamper-evident.
- Lean fields only — no verbose payloads — so 7-year storage stays tiny.
- PII is stored here only, access-controlled, never in the debug stream.

### Operational / debug logs (Tier 2)

- Verbose detail for debugging, rotated by volume AND time, then deleted.
- Redacted: no raw PII or secrets at any point.
- Short retention (14–30 days or volume-capped — decided in §9).

### Cross-cutting principles

- DPDP-safe: never log raw PII or secrets in the debug stream.
  Hash `user_id`; never log CAS file bytes, PAN, passwords, JWTs, full AI
  prompts/responses, or API keys.
- Correlation: one `request_id` / `trace_id` ties a debug line to a ledger row,
  propagated HTTP → Celery task → AI gateway → DB write.
  Today's CAS pipeline incidents required manual log-grepping precisely because
  this propagation is missing.
- Standards alignment: OWASP Logging Cheat Sheet, SEBI record-keeping / audit-trail
  obligations, DPDP processing records + India residency requirement,
  OpenTelemetry-compatible trace IDs (optional upgrade path).

---

## 2. What exists today

### Already present

- `request_id` middleware — generates and attaches an ID to every HTTP request;
  returned in `X-Request-ID` response header.
- `compliance.ai_recommendation_audit` — 7-year partitioned table covering
  served AI labels/outputs; introduced in the initial schema.
- `consent.consent_audit_log` — per-event consent ledger rows.
- RFC7807 error handler — structured problem+json errors with `request_id`.
- Container stdout — unstructured print/log statements, no consistent format.
- `etip_prometheus` / `etip_grafana` — reusable shared-infra containers on KVM4;
  available for scraping and dashboards without new infra cost.
- B38 (planned) — Sentry error tracking and Prometheus metrics wiring, not yet done.

### Gaps

- No correlation propagation: `request_id` stops at the HTTP boundary and is not
  threaded into Celery tasks, the AI gateway, or audit-ledger writes.
- Unstructured operational logs: stdout is ad-hoc print/logging, not JSON,
  not enriched with context, not redacted.
- No rotation config: Docker default logging driver accumulates unbounded on the
  3 GB cap box.
- Audit schema partial: `ai_recommendation_audit` and `consent_audit_log` exist;
  security-critical, admin-action, payment, and automation events have no ledger rows.

---

## 3. Compliance ledger (Tier 1) — bare minimum, 7-year, India-resident

### Storage contract

- Schema: `audit` (extends existing `compliance` schema where tables already live).
- Backend: Postgres on the Mumbai KVM4 box — satisfies DPDP India-residency.
- Rows are append-only; no UPDATE or DELETE is permitted by application code.
- Tamper-evidence: per-row SHA-256 hash of the immutable fields
  (see §9 for hash-chain vs per-row-hash decision).
- Partitioned by month (TimescaleDB or Postgres range partition); partitions retained
  for 7 years then archived (not dropped) per SEBI record-keeping rules.
- Heavy data — full prompts/responses, request bodies, intermediate scoring values,
  parse detail, raw CAS bytes, stack traces — is **never** stored in this tier.

### Per-event minimal fields

| Event type | Minimal fields |
|---|---|
| `ai_output_served` | `ts`, `event_type`, `user_ref` (hashed), `surface`, `label`, `model_version`, `disclaimer_version`, `content_hash`, `request_id` |
| `consent_action` | `ts`, `event_type`, `user_id`, `purpose`, `action`, `version`, `request_id` |
| `ai_gateway_decision` | `ts`, `request_id`, `model`, `decision` (served/refused), `disclaimer_version`, `prompt_hash` — NOT prompt or response text |
| `admin_action` | `ts`, `admin_id`, `action`, `target_type`, `target_id`, `result`, `request_id` |
| `payment_event` | `ts`, `user_id`, `order_id`, `razorpay_payment_id`, `status`, `request_id` |
| `security_critical` | `ts`, `event_type`, `user_ref` (hashed), `request_id` — covers refresh-reuse detection, suspicious auth, account deletion |

**Existing tables that already cover two rows:**
`compliance.ai_recommendation_audit` → `ai_output_served`;
`consent.consent_audit_log` → `consent_action`.
The remaining four event types need new tables or extension of existing ones (P2 work).

---

## 4. Operational / debug logs (Tier 2) — verbose, rotated

### Emission

- Library: `structlog` (add to `requirements.txt`).
- Format: JSON to stdout, one object per line.
- Bound context per request: `request_id`, `trace_id` (if OTel adopted), `job_id`
  (Celery), `user_ref` (hashed SHA-256 of `user_id` — never the raw ID).
- Structlog processors chain: `TimeStamper(iso)` → `add_log_level` →
  `CallsiteParameter` → `RedactionFilter` (see below) → `JSONRenderer`.

### Rotation — lightest option for the 3 GB box

Docker `json-file` log driver with `max-size` and `max-file` per service in
`docker-compose.yml`. Example per service:

```yaml
logging:
  driver: json-file
  options:
    max-size: "50m"
    max-file: "5"
```

This gives automatic volume-capped rotation with zero extra infra. A 50 MB × 5
ceiling per container means ~250 MB per service worst-case. Total across 8 containers
≈ 2 GB maximum — within the 3 GB cap with headroom for DB + Redis.

### Optional upgrade path (P3)

Ship logs to Grafana Loki reusing the shared `etip_grafana` instance for queryable
14–30 day retention. Keep it lightweight — no ELK.

### Redaction filter — fields that must never appear in Tier 2

The `RedactionFilter` structlog processor must scrub or hash these fields before any
line is written:

- `user_id` → replace with `sha256(user_id)[:16]`
- `email`, `phone`, `pan` → `[REDACTED]`
- `password`, `otp`, `totp_secret` → `[REDACTED]`
- JWT tokens, cookie values → `[REDACTED]`
- CAS file bytes or any `multipart` body → `[REDACTED]`
- Full AI prompt or response text → `[REDACTED:prompt]` / `[REDACTED:response]`
- R2, Razorpay, OpenRouter, and SMTP API keys → `[REDACTED:key]`

---

## 5. Correlation — the key to debugging

### Today's gap

`request_id` is generated in the HTTP middleware but stops there. Celery tasks,
AI-gateway calls, and audit-ledger writes carry no reference to the originating
request. A single CAS upload spawns a Celery chain and one or more AI calls — today
these are untraceable without manual log-grepping.

### Propagation contract

#### HTTP layer

- The existing middleware already generates `request_id` (UUID4).
- Extend it to also bind a hashed `user_ref` into the structlog context via
  `structlog.contextvars.bind_contextvars(request_id=..., user_ref=...)`.
- Every log line emitted in the request lifecycle inherits both fields automatically.

#### Celery propagation

- Pass `request_id` as a Celery task header or explicit kwarg when enqueuing.
- In the worker's `task_prerun` signal, re-bind into structlog contextvars so
  every worker log line carries the originating `request_id`.

#### AI gateway

- The gateway `complete()` call already receives context; extend its signature to
  accept and forward `request_id`.
- Write `request_id` into every `ai_recommendation_audit` / `ai_gateway_decision`
  ledger row.

#### Result

One `request_id` is fully traceable across HTTP → Celery worker → AI gateway → DB
audit row by a single grep or Loki query.

---

## 6. Event taxonomy

What gets logged and in which tier:

| Category | Examples | Tier |
|---|---|---|
| Auth / security | Login, logout, token refresh, refresh-reuse detection, failed auth, rate-limit hit | Tier 1 (security_critical) + Tier 2 debug |
| Consent / DPDP | Grant, revoke, version bump, consent-gate block | Tier 1 (consent_action) + Tier 2 debug |
| Data processing | CAS upload received, parse start/end, score job enqueued, report generated | Tier 2 debug (job_id bound); Tier 1 only for the final label served |
| AI gateway | Model chosen, token count, cost estimate, decision (served/refused), disclaimer version | Tier 1 (ai_gateway_decision) + Tier 2 debug (prompt_hash only) |
| Scoring / labels | Label computed, confidence band, factor scores | Tier 2 debug; Tier 1 for the served label (ai_output_served) |
| Admin actions | Config change, user flag, manual override, migration run | Tier 1 (admin_action) + Tier 2 debug |
| Payments | Order created, webhook received, status update, refund | Tier 1 (payment_event) + Tier 2 debug |
| Automation | Celery task start, end, failure, retry, duration, beat schedule | Tier 2 debug (job_id, request_id, duration) |
| System | Deploy event, Alembic migration applied, health-check result, unhandled exception | Tier 2 debug + Sentry (B38) for exceptions |
| Metrics | Request latency, error rates, AI cost, task queue depth | Prometheus → Grafana (not log lines) |

---

## 7. Storage and retention summary

| Tier | Store | Retention | Residency |
|---|---|---|---|
| Compliance ledger | Postgres `audit` schema (KVM4 Mumbai) | 7 years (SEBI) | India — KVM4 Mumbai |
| Operational / debug | Docker `json-file` (on-box) or Grafana Loki | 14–30 days or volume-capped (§9) | India — on-box |
| Metrics | Prometheus (etip_prometheus) | 15–30 days | India — on-box |
| Exception tracking | Sentry (B38) | Per Sentry plan | Cloud — DSN TBD |

---

## 8. Phased implementation plan

### P1 — Foundational (low-risk; makes incidents traceable immediately)

**Scope:** structlog JSON setup + `request_id` contextvar binding + propagation into
Celery and AI gateway + redaction filter + Docker `json-file` rotation in
`docker-compose.yml`.

**Why first:** this alone closes the "manual log-grepping" gap without touching any
compliance table or load-bearing path. Risk is low; the change is additive.

**Files touched:**

- `backend/requirements.txt` — add `structlog`.
- `backend/dhanradar/middleware/request_id.py` — bind structlog contextvars.
- `backend/dhanradar/core/logging.py` (new) — configure structlog processors +
  redaction filter.
- `backend/dhanradar/celery_app.py` — `task_prerun` signal re-bind.
- `backend/dhanradar/ai_gateway/gateway.py` — accept + forward `request_id`.
- `docker-compose.yml` — add `logging:` block per service.

**Acceptance:** one HTTP request generates correlated log lines at HTTP, worker,
and gateway layers sharing the same `request_id`; redacted fields absent from output.

**Routing:** Sonnet implement (load-bearing: AI gateway + middleware) + Opus diff
review + `codex:rescue` / Sonnet adversarial pass (auth middleware is Tier-B path).

---

### P2 — Extend audit schema (new ledger tables)

**Scope:** Alembic migration adding `audit.admin_actions`, `audit.payment_events`,
`audit.security_events` tables with the minimal fields from §3; add per-row hash
column; update call sites to emit rows.

**Files touched:**

- New Alembic migration under `backend/alembic/versions/`.
- `backend/dhanradar/audit/` — emit helpers for the three new event types.
- Call sites in `auth/`, `billing/`, and `admin/` modules.

**Routing:** Sonnet implement + Opus diff review. Migration is a load-bearing path —
full inline Tier-B review in the same session.

---

### P3 — Grafana Loki integration

**Scope:** Add Loki to `docker-compose.yml` reusing `etip_grafana`; configure
Promtail or Docker Loki log driver; add dashboards: per-request trace view, error
rates, AI cost by model.

**Depends on:** P1 (structured JSON logs must exist before shipping to Loki).

**Routing:** Sonnet implement + Opus review. Loki config is non-load-bearing.

---

### P4 — Alerting and retention automation

**Scope:** Prometheus alert rules for auth-failure spikes, AI budget threshold,
task-failure rate, audit-write failures. Postgres `pg_partman` scheduled maintenance
for audit partition rollover. Add a `LOGGING_RUNBOOK.md` for on-call.

**Depends on:** P3 (Loki dashboards for context), P2 (full audit schema).

**Routing:** Sonnet draft + Ops review.

---

## 9. Open decisions for the implementing session

The following are unresolved and must be decided before or during implementation:

- **Tamper-evidence method:** per-row SHA-256 hash of immutable fields (simpler,
  each row self-verifying) vs hash-chain (each row hashes prior row's hash, stronger
  ordering proof but harder to backfill). Recommendation: start with per-row hash
  in P2; hash-chain is a future upgrade.
- **Loki timing:** deploy Loki in P1 (alongside rotation) or wait for P3.
  P1 Docker `json-file` is sufficient for immediate traceability; Loki adds
  queryability but costs ~100 MB RAM on the 3 GB box.
- **Debug retention days:** 14 days (minimal) vs 30 days (more useful for slow
  incidents). Decide based on observed box disk usage post-P1.
- **OpenTelemetry trace IDs:** adopt OTel-compatible 16-byte trace IDs from the
  start (future-proof, enables Tempo) or keep the existing UUID4 `request_id`.
  Low-cost to adopt in P1 if decided up-front.
- **structlog version pin:** confirm compatibility with the existing FastAPI version
  before adding to `requirements.txt`; check for any conflict with `python-json-logger`
  if it is already present.
- **Sentry DSN (B38):** Sentry setup is a separate blocker; the exception-tracking
  row in §7 is contingent on B38 being resolved.

---

*Status: PLAN — not implemented. Picked up by a future session; see `BLOCKERS.md`.*
