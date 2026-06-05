# Backend Implementation Spec

**Stack:** FastAPI · PostgreSQL · Redis · Elasticsearch · Celery. Full: /docs/03-backend-architecture.md.

## Layering
router (HTTP/validation) → service (business/transactions) → repository (data) → models/schemas. Modular monolith; modules: auth, users, instruments, scoring, portfolio, screener, watchlist_alerts, ai, news, billing, admin, notifications, audit.

## Non-negotiables
- `scores` table is DB-level read-only to all services except the scoring worker.
- `scoring` package may NOT import `billing` (import-lint).
- Idempotency-Key on all mutating/payment endpoints.
- Every sensitive mutation → append-only hash-chained audit_log.
