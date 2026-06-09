# Error Catalog (RFC7807 problem+json)

> ⛔ **DO NOT ADOPT — HARVEST-NOT-ADOPT REFERENCE ONLY (B41).**
> Part of the `docs/ui-system` kit, which **conflicts with the binding
> architecture** and is **not** a source of truth. Do not implement from it.
> Authority: `docs/DhanRadar_Architecture_Final.md`; apply only per
> `docs/project-state/MIGRATION_STRATEGY_FINAL.md` (KEEP/MERGE/REPLACE/IGNORE).

`{ type, title, status, detail, request_id }`

| HTTP | type | When | UI treatment |
|---|---|---|---|
| 400 | validation_error | bad input | inline field errors |
| 401 | unauthorized | missing/expired token | redirect to login (refresh first) |
| 402 | upgrade_required | gated feature on Free | contextual paywall (not error) |
| 403 | forbidden | role/ownership | access-denied page |
| 404 | not_found | unknown instrument/resource | empty/not-found state |
| 409 | conflict | duplicate (email, idempotency) | inline message |
| 422 | unprocessable | semantic validation | inline |
| 429 | rate_limited | quota/limit | "try again" + Retry-After; AI quota → upgrade |
| 500 | internal | server fault | error card + retry + support |
| 502/503 | upstream_unavailable | feed/model down | degraded mode: last-good data + banner; AI shows cached |

**Client mapping:** React Query onError → map type → toast/inline/redirect. SSE errors → error bubble + retry. Payments are idempotent; 4xx never double-charges.
