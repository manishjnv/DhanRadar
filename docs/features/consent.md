# Feature — Consent (DPDP)

**Status:** built (writer endpoints + capture UI; enforcement kill-switch B48 deferred to launch)
**Phase:** Phase 2 (slice 2 of 4)
**Last updated:** 2026-06-08

## Purpose & scope

Implements the DPDP Act consent-capture layer for DhanRadar. Provides:

- A server-side writer that records per-purpose consent grants and revokes atomically in
  `auth.users.dpdp_consents` (JSONB) and appends an append-only audit row to
  `consent.consent_audit_log`.
- Three REST endpoints (`GET /consent`, `POST /consent/grant`, `POST /consent/revoke`) that
  let authenticated users read and change their consent state.
- A frontend consent modal (`ConsentModal`) for point-of-use capture, and a settings panel
  (`/settings/privacy`) for full-lifecycle management of all seven purposes.

The module is the write-side complement to the fail-closed read gate (`deps.RequireConsent` /
`deps._consent_granted`) built in Phase 2 slice 1 (B3/B4). Together they form the complete
DPDP enforcement chain: read → gate → write.

## Non-goals

- Advisory/recommendation logic — no buy/sell/hold framing anywhere (SEBI educational boundary).
- Numerics in the DOM — no score or factor weight is shown on any consent surface.
- Consent enforcement bypass — this module captures consent; enforcement gating lives in
  `deps.RequireConsent` and is tested independently (see auth.md / B48).
- Erasure flow — `deletion_requested_at` flag is set by a separate erasure endpoint (not yet
  built); this module does not own that surface.
- CMP banner — the regulatory-grade cookie/consent management platform is a post-launch item.
- 30-minute consent cache — deferred (see Known limitations section).

## Public interface (the only coupling surface)

All endpoints are under `/api/v1`, require authentication (anonymous → 401 `not_authenticated`
returned in-body before any DB read), and return RFC7807 errors with `request_id`.

### Endpoints

- `GET /consent` — return the authenticated user's current consent state for all seven purposes.
  Response: `ConsentStateResponse` (see Data section).

- `POST /consent/grant` — grant one or more canonical DPDP purposes.
  Body: `{"purposes": ["mf_analytics", ...]}`. Accepts optional `Idempotency-Key` header
  (action-scoped; see Pipeline section). Returns the full updated `ConsentStateResponse`.

- `POST /consent/revoke` — revoke one or more canonical DPDP purposes.
  Body: `{"purposes": ["mf_analytics", ...]}`. Accepts optional `Idempotency-Key` header
  (action-scoped). Returns the full updated `ConsentStateResponse`. Writes
  `{"granted": false, ...}` — never a `"revoked"` key (see Revoke contract below).

### Revoke contract

The revoke path writes `{"granted": false, "ts": ..., "version": ...}` into the JSONB column.
It deliberately never sets a `"revoked"` key. The fail-closed reader `deps._consent_granted`
returns `True` only when the value is exactly Python `True` or a mapping with
`value.get("granted") is True`. A `"revoked"` key (or any other key) therefore reads as denied.
Writing `granted: false` ensures a revoke is honoured even if the reader is ever loaded from
a stale JSONB snapshot.

### Events emitted / consumed

None. The consent writer is a synchronous CRUD surface; it does not emit domain events.

## Data

### Postgres

`auth` schema — `auth.users` columns (written by this module):

- `dpdp_consents` (jsonb) — one key per purpose, value shape:
  `{"granted": bool, "ts": "<ISO-8601 UTC>", "version": "<semver>"}`.
  Keys are created on first grant (`create_missing=True` in `jsonb_set`).
- `dpdp_consent_version` (text) — the active consent document version at the time of the last
  write (kept in sync with `settings.DPDP_CONSENT_VERSION` on every grant/revoke).

`consent` schema (Alembic migration `0010_consent_audit_log.py`):

- `consent.consent_audit_log` — append-only audit trail.

  | Column | Type | Notes |
  |---|---|---|
  | `id` | uuid PK | `gen_random_uuid()` |
  | `user_id` | uuid NOT NULL | **No FK/CASCADE** — audit survives user erasure |
  | `purpose` | text NOT NULL | One of the seven canonical purposes |
  | `action` | text NOT NULL | `CHECK (action IN ('grant', 'revoke'))` |
  | `consent_version` | text | Version string at time of action |
  | `request_id` | text | Traces back to the originating HTTP request |
  | `created_at` | timestamptz | `DEFAULT now()` |

  Index: `ix_consent_audit_user` on `(user_id, created_at)`.

  The absence of a FK to `auth.users` is intentional: DPDP right-to-erasure erases PII content,
  not the audit fact of consent itself. The audit row must survive a user deletion.

### Redis

`consent:idem:{action}:{uid}:{key}` — NX SET, TTL 24 h, per-action idempotency dedup.

The `action` segment (`grant` or `revoke`) scopes the key by operation. Without this scoping,
reusing a key across a grant then a revoke would make the revoke look like a replay and be
silently skipped, leaving consent granted while the caller receives 200 (a fail-open defect
found and fixed at inline Tier-B review; see RCA 2026-06-08).

### Purpose taxonomy

The canonical set (seven purposes, defined in `deps.CONSENT_PURPOSES`):

| Purpose | What it gates |
|---|---|
| `mf_analytics` | CAS upload → portfolio report pipeline |
| `ai_insights` | AI gateway call for portfolio commentary |
| `marketing` | Newsletter / product-update emails |
| `portfolio_sync` | Stored-holdings refresh without re-upload |
| `behavioral_nudges` | Periodic portfolio health reminder notifications |
| `cross_border_ai` | Transfer to an overseas AI provider (OpenRouter, B20) |
| `cross_border_notify` | Delivery via overseas messaging/email providers (B31) |

Unknown purposes are rejected at the schema layer (`ConsentChangeRequest.validate_purposes`)
with a 422 listing valid values.

## Pipeline / behaviour

### Read flow (`GET /consent`)

1. Request arrives; `current_user_or_anonymous` resolves the session from the
   `__Host-access` cookie.
2. Anonymous check in-body (before any DB access) → 401 `not_authenticated`.
3. `read_state(db, user_id)` selects `auth.users.dpdp_consents` fresh (no cache) and
   evaluates every canonical purpose through `deps._consent_granted` → `{purpose: bool}` dict.
4. Returns `ConsentStateResponse(consents, consent_version)`.

### Write flow (`POST /consent/grant` and `POST /consent/revoke`)

1. Anonymous check in-body → 401.
2. If `Idempotency-Key` header is present: attempt Redis NX set at
   `consent:idem:{action}:{uid}:{key}` (TTL 24 h). If the key already exists (replay) →
   return current state without writing. If Redis is unavailable, log a warning and proceed
   (consent capture must not be blocked by a cache outage; write-side idempotency via JSONB
   merge makes a duplicate write safe).
3. Call `apply_consent_change(db, user_id, purposes, granted, version, request_id)`:
   a. For each purpose in the list, issue a Postgres `UPDATE auth.users SET
      dpdp_consents = jsonb_set(dpdp_consents, '{purpose}', payload, true),
      dpdp_consent_version = version WHERE id = uid`.
   b. The `jsonb_set` call is atomic at the key level — sibling purposes are not clobbered
      even if concurrent requests touch different purposes.
   c. Check `result.rowcount == 0`: if the user row is gone (DPDP erasure race),
      roll back and raise 401 `user_not_found` (no false audit row committed).
   d. Append one `ConsentAuditLog` row per purpose (`action = 'grant' | 'revoke'`).
   e. Single `await db.commit()` — all-or-nothing across all purposes in the request.
4. Re-read the full state via `read_state` and return `ConsentStateResponse`.

### Fail-closed gate (`deps.RequireConsent`)

Route dependencies and internal call sites (`consent_granted`, `assert_consent`) all read
`auth.users.dpdp_consents` fresh via `deps._consent_granted`:

- Anonymous principal → 401 `not_authenticated` (safe-by-default; ordering never delegated
  to the caller — Phase-7 §5 hardening).
- Grant missing or `granted != True` → 403 `consent_required` with the `purpose` field.
- No cache on the read path, so a revoke is honoured immediately.

## Config & flags

| Variable | Default | Effect |
|---|---|---|
| `DPDP_CONSENT_VERSION` | `"1.0"` | Written into every consent row and audit log |
| `DPDP_CONSENT_ENFORCED` | `true` | Kill-switch (B48). `false` only in `development/test/ci` ENV; boot-fails in all others |

`DPDP_CONSENT_ENFORCED=false` in dev `.env` disables enforcement via the single
`_consent_granted` chokepoint so consent-gated routes work during development without a
real grant. Auth (anonymous → 401) is untouched. One startup warning is logged when active.
**B48 must be re-enforced at launch** (set `ENV=production` or `DPDP_CONSENT_ENFORCED=true`
and verify a gated route 403s without a grant).

Rate limit: 20 requests / 60 s per IP across all three endpoints.

## Failure modes & fallbacks

| Failure | Behaviour |
|---|---|
| Anonymous caller | 401 `not_authenticated` (in-body, before any DB read) |
| Unknown purpose in body | 422 validation error listing valid purposes |
| Idempotency key replay | 200 with current state; no write, no audit row |
| Redis unavailable on idempotency check | Warning logged; write proceeds (JSONB merge is idempotent) |
| `rowcount == 0` (user deleted mid-session) | Rollback + 401 `user_not_found`; no false audit row |
| `_consent_granted` missing or false | 403 `consent_required` (gate never fails open) |
| DB error during write | Transaction rolls back; 500 propagated by FastAPI error handler |

## Dependencies

- **Auth module** (`auth.users`, `current_user_or_anonymous`, `UserContext`) — read-only
  dependency; no cross-schema writes.
- **`deps.RequireConsent` / `deps._consent_granted`** (`backend/dhanradar/deps.py`) — the
  canonical fail-closed reader; this module uses it for `read_state` to keep grant/revoke
  semantics at a single source of truth.
- **Redis** — idempotency key store only; degraded gracefully if unavailable.
- **MF module** (`mf_analytics`) — the CAS upload route depends on `RequireConsent("mf_analytics")`.
- **AI gateway** (`ai_insights`) — the `complete()` callsite depends on `consent_granted("ai_insights")`.
- **Notification module** (`cross_border_notify`) — deliver seam depends on `consent_granted("cross_border_notify")`.

## Frontend

### ConsentModal (`frontend/src/features/consent/ConsentModal.tsx`)

Point-of-use capture dialog shown inline when a feature requires a consent that has not yet
been granted. Props: `open`, `purposes: ConsentPurpose[]`, `onGranted`, `onCancel`.

Accessibility contract: `role="dialog"`, `aria-modal="true"`, `aria-labelledby` heading,
focus moved to the heading on open, Escape key fires `onCancel`. "Grant & continue" is
disabled until the "I consent" checkbox is checked.

Flow: user checks the checkbox → clicks "Grant & continue" → `useGrantConsent()` mutation
fires → on success `onGranted()` is called → the blocked feature proceeds.

### Settings panel (`frontend/src/app/(app)/settings/privacy/page.tsx`)

Full-lifecycle management of all seven purposes at `/settings/privacy`. Shows a `role="switch"`
toggle per purpose in display order (data-processing purposes first, cross-border transfers
last). Each toggle fires `useGrantConsent` or `useRevokeConsent` for a single purpose on change
and seeds the TanStack Query cache with the authoritative server response. Skeleton loading state
and retry error card are included. Renders a `Disclaimer` component at the foot.

### TanStack Query hooks (`frontend/src/features/consent/api.ts`)

- `useConsent()` — `GET /consent`; `staleTime` 60 s; 401 is not retried (anonymous is
  the expected unauthenticated state).
- `useGrantConsent()` — `POST /consent/grant`; seeds the consent query cache on success.
- `useRevokeConsent()` — `POST /consent/revoke`; seeds the consent query cache on success.

### Purpose copy (`frontend/src/features/consent/purposeCopy.ts`)

Human-readable title and description for each of the seven purposes. All copy is educational
and advisory-verb-free. No numerics.

## Verification

Run the integration test suite:

```bash
docker compose run --rm dhanradar-fastapi pytest -q backend/tests/integration/test_consent_writer.py
```

Key regression tests:

- `test_same_idempotency_key_across_grant_then_revoke_still_revokes` — asserts that reusing a
  key across a grant then a revoke correctly executes the revoke (action-scoped key prevents
  the replay-skipping fail-open).
- `test_grant_for_deleted_user_fails_closed_no_audit` — asserts that a 0-row UPDATE raises
  401 and commits no audit row.

Frontend: `npx vitest run src/features/consent/` (unit tests for `api.ts` and `ConsentModal`).

Deterministic gates: `ci_guards.py` exit 0 (no advisory verbs, no numerics, no bearer auth) ·
`ruff` / `mypy` (advisory) · `tsc` clean · `markdownlint` 0.

## Known limitations / future

- **30-minute consent cache with flush-on-revoke** — the read gate (`deps.RequireConsent`)
  currently reads fresh from DB on every request (no cache). A per-user cache keyed by
  `consent:{uid}:{purpose}` with TTL=30 min, flushed atomically on revoke, is the planned
  optimisation. Deferred to avoid the cache-invalidation complexity before a real traffic load
  justifies it.
- **CMP banner** — a regulatory-grade consent management platform banner for first-visit capture
  is a post-launch deliverable. The `ConsentModal` serves as point-of-use capture in the
  interim.
- **Erasure flow** — the `deletion_requested_at` flag triggers a login denial (auth module)
  and must also revoke the user's active refresh JTIs and flush `auth:tier:{uid}` when set.
  The erasure endpoint itself is not yet built.
- **`marketing` and `behavioral_nudges` promotional grant** — these purposes currently require
  the user to opt in via the settings panel. A "grant all promotional" convenience at signup is
  a planned onboarding UX improvement; it would call `POST /consent/grant` for both purposes
  after the signup consent flow.
- **B48 kill-switch** — `DPDP_CONSENT_ENFORCED=false` is active in dev. It must be set to
  `true` (or `ENV=production`) before any live traffic touches the stack. This is a
  hard pre-launch gate; see `BLOCKERS.md` B48.

## Changelog

- 2026-06-08 — Module built (Phase 2 slice 2, B44). Backend consent writer (927f64f):
  `consent/router.py`, `consent/service.py`, `consent/schemas.py`,
  `models/consent.py`, Alembic `0010_consent_audit_log.py`. Frontend consent UI (4b40f83):
  `ConsentModal.tsx`, `purposeCopy.ts`, `types.ts`, `api.ts`,
  `app/(app)/settings/privacy/page.tsx`. Inline Tier-B Security/Compliance review completed
  (Sonnet adversarial takeover; codex n/a — account entitlement error). Two defects found
  and fixed before commit: idempotency key action-scoping (fail-open replay), and 0-row
  UPDATE check (false audit row). See RCA 2026-06-08.
