# Feature — Auth & Tiering

**Status:** partial (auth lifecycle + tiering built; consent/erasure deferred)     **Phase:** Phase 2 (slice 1 of 4)
**Last updated:** 2026-06-12 (ADR-0031: Email OTP alternative login)

## Purpose & scope

Full authentication lifecycle (signup, login, logout, silent refresh, TOTP 2FA enrolment) and subscription-tier gating for DhanRadar. Issues RS256 JWTs in `__Host-` HttpOnly cookies, resolves a user's tier from their active Razorpay subscription, and exposes the shared `RequireTier` dependency every domain module gates on. Also lands the async Alembic migration infrastructure.

## Non-goals

- KYC / identity verification (partner, Year 2).
- Broker-credential storage (Portfolio module scope).
- Consent/DPDP — the full Consent module (append-only `consent_audit_log`, grant/revoke endpoints, CMP banner, erasure, the consent cache) is a later Phase-2 slice. The **gate primitives** are hardened here (B3/B4): `RequireConsent` is **fail-closed** (purpose validated against the canonical taxonomy; grant read fresh from `users.dpdp_consents`; missing/false/anonymous → 403 `consent_required`), and `authenticate_user` denies login for a `deletion_requested_at` account (403 `account_deletion_pending`).
- TOTP is **not** a second factor and is **never forced**. Beyond enrolment it is an
  **opt-in alternative login method** (`/auth/totp/login`, ADR-0029). Email OTP is a second
  opt-in alternative login method (`/auth/email-otp/request` + `/auth/email-otp/login`,
  ADR-0031) — also a first factor, not 2FA. Both methods are distinct from the banned
  OTP-first D2 pattern. The Pro+ sensitive-action step-up hook remains a separate later
  concern.
- No advisory/recommendation logic (SEBI educational boundary — out of scope for this module).

## Public interface (the only coupling surface)

REST (all under `/api/v1`):

- `POST /auth/signup` — create free-tier account, set session cookies (201; 409 on duplicate email).
- `POST /auth/login` — password auth, set cookies (401 generic `invalid_credentials`).
- `POST /auth/logout` — clear cookies, revoke refresh jti **and** denylist the live access jti.
- `POST /auth/refresh` — silent refresh; rotates the refresh token with reuse detection.
- `GET  /auth/me` — current user profile (401 if anonymous).
- `POST /auth/totp/setup` — provisioning URI + secret (pre-verify only).
- `POST /auth/totp/verify` — verify code, activate authenticator login.
- `POST /auth/totp/login` — **standalone TOTP login** (email + 6-digit code → cookies); generic 401 on any failure (enumeration-safe), per-account lock + per-code replay guard. ADR-0029.
- `GET  /auth/google/start` — begin Google SSO (OAuth+PKCE+nonce); 503 if SSO unconfigured. ADR-0029.
- `GET  /auth/google/callback` — verify id_token locally, resolve/create user, set cookies (303); failures redirect `/login?error=…`. ADR-0029.
- `POST /auth/email-otp/request` — send a 6-digit code to the supplied email (202 always
  — enumeration-safe; 503 if `RESEND_API_KEY` unset). ADR-0031.
- `POST /auth/email-otp/login` — verify code, issue cookies; generic 401 on any failure.
  ADR-0031.
- `POST /subscriptions/webhook` — Razorpay webhook; signature-verified, idempotent.

Shared dependencies consumed by other modules: `Depends(RequireTier("free"|"pro"|"pro_plus"))` → **HTTP 402** `{error, upgrade_url}`; `Depends(current_user_or_anonymous)` → `UserContext`. No events emitted.

## Data

Postgres schema `auth`:

- `auth.users` — `id` (uuid PK), `email` (unique, lowercased), `hashed_password` (argon2id, **nullable** — SSO-only accounts have none; ADR-0029), `google_sub` (unique, nullable — Google subject id), `tier` (enum `auth.user_tier`: anonymous|free|pro|pro_plus|founder_lifetime), `totp_secret`/`totp_verified`, `risk_profile` (Onboarding writes later), `dpdp_consent_version`/`dpdp_consents` jsonb (Consent writes later), `deletion_requested_at`, timestamps.
- `auth.subscriptions` — `id`, `user_id` FK→users (CASCADE), `razorpay_subscription_id` (unique), `plan`, `status`, period start/end, timestamps.

Redis: `auth:refresh:{jti}`→uid (7d), `auth:tier:{uid}`→tier (15m), `auth:totp_attempts:{uid}`
(enrolment-verify lock, 900s, ≥5), `auth:totp_login_attempts:{uid}` (standalone-login lock,
separate so a login sprayer can't lock out enrolment; ADR-0029), `auth:totp_used:{uid}:{code}`
(90s replay guard), `auth:oauth_state:{state}`→`{nonce,code_verifier,next}` (600s, single-use
`GETDEL`), `auth:access_revoked:{jti}` (TTL=token remainder), `auth:rzp_evt:{event_id}` (7d
dedup), `ratelimit:{cf_ip}:{path}`, `auth:email_otp:{uid}` (SHA-256 code hash, TTL 600 s),
`auth:email_otp_cooldown:{uid}` (send cooldown, SET NX 60 s), `auth:email_otp_daily:{uid}`
(daily send cap counter, SET NX + INCR + EXPIREAT), `auth:email_otp_attempts:{uid}`
(5-attempt failed-verify lock, 15 min), `auth:email_otp_used:{uid}:{hash}` (per-code atomic
consume marker, SET NX — never deleted, TTL=code TTL; per-code keying closes TOCTOU without
post-login lockout).

Migrations: `alembic/versions/0001_auth_init.py` (async env, `include_schemas=True`); `0018_google_sso.py` (adds `google_sub` unique + makes `hashed_password` nullable).

## Pipeline / behaviour

1. Signup/login → argon2id hash/verify → issue access (15m) + refresh (7d) RS256 JWTs → `__Host-*` cookies.
2. Refresh: decode `__Host-refresh` → atomic Redis `GETDEL` of the jti (race-free reuse detection) → owner-match assert → issue + store new pair.
3. Logout: revoke refresh jti + denylist live access jti for its remaining TTL → `current_user_or_anonymous` rejects denylisted access tokens.
4. Tier: `current_user_or_anonymous` resolves tier via `auth:tier:{uid}` cache (15m) → DB fallback. Razorpay webhook (verify-before-parse, event-id dedup) upserts the subscription, recomputes `users.tier`, flushes the cache.

## Email OTP login (ADR-0031)

Two-phase flow: the user clicks "Sign in with email code", enters their email address, and
receives a 6-digit code via email (Resend). They enter the code on a second screen
(auto-submit on 6th digit; manual "Log in" fallback; 60-second countdown before resend
is enabled).

**Endpoints:**

- `POST /auth/email-otp/request` — accepts `{email}`; always returns 202 (enumeration-safe);
  503 if `RESEND_API_KEY` unset (fail-closed, matching SSO pattern). Per-IP: 3 req/min.
- `POST /auth/email-otp/login` — accepts `{email, code}`; issues `__Host-` cookies on
  success via `set_auth_cookies`; generic 401 on every failure. Per-IP: 5 req/min.

**Redis state (no DB migration):**

- `auth:email_otp:{uid}` — SHA-256 hash of the active code (TTL 600 s).
- `auth:email_otp_cooldown:{uid}` — send-cooldown gate (`SET NX`, 60 s).
- `auth:email_otp_daily:{uid}` — daily send cap, atomic `SET NX` seed + `INCR` + `EXPIREAT`.
  Cap: 10 sends/day; counter starts at 1 on first request; EXPIREAT fires at midnight.
- `auth:email_otp_attempts:{uid}` — failed-verify counter; ≥5 triggers the lock for 15 min;
  on lock transition a `email_otp_locked` security event fires once; returns 401 not 429
  (lock is not an account-exists oracle on the unauthenticated surface).
- `auth:email_otp_used:{uid}:{hash}` — per-code atomic consume marker (`SET NX`). Returns
  False for any second consumer of the same code. Never deleted (TTL self-heals with the
  code key); per-code keying is deliberate — a per-uid marker would block the next code
  request for the key's TTL (approximately 10 min post-login lockout), whereas per-code
  keying closes the TOCTOU race without that side-effect.

**Security properties:**

- Enumeration-safe: 202 on request regardless of whether the email exists, is on cooldown,
  or has hit the daily cap.
- Response-timing oracle closed: send is `asyncio.create_task` (fire-and-forget); the request
  endpoint returns before Resend is called.
- TOCTOU double-spend closed: `auth:email_otp_used:{uid}:{hash}` (`SET NX`) is the atomic
  consume guard.
- Code stored as SHA-256 hash only — never plaintext, never logged (interface-only coupling
  to `notifications.channels.deliver_email`).
- Deletion-pending accounts: 202 on request; 403 only after code proven correct on login
  (not an account oracle — consistent with the TOTP-login accepted residual, ADR-0029).
- Digit validation uses `[0-9]` not `\d` (Unicode-digit hardening, applied to both email-OTP
  and existing TOTP schemas).

**UI handover:** the login page's code-mode (previously authenticator-app TOTP entry) is
now email-OTP. `POST /auth/totp/login` stays live API-side; the settings → Security
enrolment page is untouched.

## Config & flags

Env (see `.env.example`): RS256 PEM supplied either inline as `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` (literal `\n` accepted for single-line `.env`) **or** as a mounted file path `JWT_PRIVATE_KEY_FILE`/`JWT_PUBLIC_KEY_FILE` (production-preferred — keys never transit env; resolved by `config.jwt_private_key`/`jwt_public_key`, file wins, empty → fails closed). Generate dev keys: `backend/scripts/gen_jwt_keys.py`. Also `JWT_ALGORITHM=RS256`, `ACCESS_TTL_MIN=15`, `REFRESH_TTL_DAYS=7`, `COOKIE_SECURE=True`, `RAZORPAY_KEY_ID/SECRET/WEBHOOK_SECRET`. **Google SSO (ADR-0029):** `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`
(all three required; any absent → `/auth/google/start` returns 503 — SSO is opt-in/fail-closed).
**Email OTP (ADR-0031):** `RESEND_API_KEY` (required; absent → `POST /auth/email-otp/request`
returns 503 — email OTP is opt-in/fail-closed). No other new env vars. No feature flags.

## Failure modes & fallbacks

Tier cache miss → DB; deleted user → tier `anonymous` (≤15m stale on cache hit); webhook bad signature → 400 (fails closed); duplicate webhook → 200 not reprocessed; invalid/expired JWT → anonymous (client calls `/refresh`); refresh reuse/owner-mismatch → 401; ≥5 bad TOTP on enrolment-verify → 429 for 900s; ≥5 bad TOTP on `/totp/login` → still generic **401** (lock is not an account-exists oracle on
the unauth surface); ≥5 bad email OTP attempts → generic **401** for 15 min (lock is not an
account oracle; a `email_otp_locked` security event fires once at lock transition); Google SSO
any failure → `/login?error=…` redirect (never a JSON page); rate-limit exceeded → 429
`Retry-After`.

## Dependencies

Postgres (`auth` schema, from Phase-1 init SQL), Redis, `current_user_or_anonymous`/`RequireTier` (this module owns them). Build-vs-partner: auth=build; payments=Razorpay (partner); KYC=partner (Y2).

## Verification

`python -m py_compile` clean across the backend package and the test suite. Adversarial gate (Opus takeover, 2026-05-19): verdict **REVISE → fixes applied**; config key-loading change Opus mini-gate: **ACCEPT**. A pytest suite exists under `backend/tests/` — unit (JWT alg/typ-confusion, expiry, password hashing, tier derivation, budget, **consent/deletion gate B3/B4**) + integration (signup→login→refresh-rotation→reuse→logout-revocation→rate-limit; Razorpay webhook signature/tier/idempotency). Run: `docker compose run --rm dhanradar-fastapi pytest -q` (see README → Testing). **Status: unit tests run locally; integration tests execute in CI** (no local Postgres, per BLOCKERS B1) — full execution owed before any deploy (Phase 7 §5).

## Known limitations / deferred (carry to handoff)

- DPDP gate primitives are now fail-closed (B3/B4): `RequireConsent` enforces against `users.dpdp_consents` (403 `consent_required`); login is denied for a `deletion_requested_at` account (403 `account_deletion_pending`). **Still owed in the Consent/erasure module:** the append-only `consent_audit_log` + grant/revoke endpoints + CMP, and — at the point erasure SETS `deletion_requested_at` — revoking the user's refresh jtis **and** flushing `auth:tier:{uid}` so existing sessions die (login denial only stops *new* sessions).
- `EXACT_PLAN_TIERS` is empty — substring plan→tier fallback is a **pre-billing blocker**; populate with real Razorpay plan_ids before billing goes live.
- Future checkout creation MUST server-set `notes.user_id` from the authenticated session (never client-supplied).
- Rate limiter is fixed-window (small burst at boundary); consider sliding window later. No permissive CORS may be added (cookie-auth + SameSite=lax posture depends on it).
- Signup returns 409 on duplicate email (intentional, accepted enumeration tradeoff).

## Changelog

- 2026-05-19 — Module built (Phase 2 slice 1). Security review + Opus-takeover adversarial gate; fixes: rate-limit wiring, atomic refresh `GETDEL`, `CF-Connecting-IP` keying, signup-race 409, access-token revocation on logout, webhook event-id idempotency, exact-plan map w/ fallback warning, password `max_length`. See RCA 2026-05-19.
- 2026-05-19 — Test enablement: Dockerfile now `COPY`s `alembic/`+`alembic.ini` (in-container `alembic upgrade head` was broken); config resolves PEM via `JWT_*_KEY_FILE` path or `\n`-unescaped inline; gitignored `docker-compose.override.yml` (ports + `COOKIE_SECURE=False` + key mount); pytest suite added (`backend/tests/`); pytest-asyncio fixture loop-scope landmine fixed (db_engine/db_tables → function scope). Mini-gate on key-loading: ACCEPT.
- 2026-06-05 — DPDP gate primitives hardened (B3/B4): `RequireConsent` made fail-closed; login denial for `deletion_requested_at`; unit tests added (`tests/unit/test_consent.py`). See RCA 2026-06-05.
- 2026-06-12 — Email OTP as an alternative login method (ADR-0031): 4th login method;
  two new endpoints (`/auth/email-otp/request` + `/auth/email-otp/login`); Redis-only
  state; fire-and-forget Resend delivery; per-code TOCTOU consume guard; login-page
  code-mode UI handover from TOTP entry to email-OTP entry. Tier-B inline Security
  (Sonnet adversarial takeover, ACCEPT after revise + re-verify) + Compliance (Opus,
  ACCEPT-WITH-CONDITIONS); B64 DPDP residual filed. See `reviews/email-otp-login.md`.
