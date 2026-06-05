# Feature — Auth & Tiering

**Status:** partial (auth lifecycle + tiering built; consent/erasure deferred)     **Phase:** Phase 2 (slice 1 of 4)
**Last updated:** 2026-05-19

## Purpose & scope
Full authentication lifecycle (signup, login, logout, silent refresh, TOTP 2FA enrolment) and subscription-tier gating for DhanRadar. Issues RS256 JWTs in `__Host-` HttpOnly cookies, resolves a user's tier from their active Razorpay subscription, and exposes the shared `RequireTier` dependency every domain module gates on. Also lands the async Alembic migration infrastructure.

## Non-goals
- KYC / identity verification (partner, Year 2).
- Broker-credential storage (Portfolio module scope).
- Consent/DPDP enforcement — `RequireConsent` is an intentional pass-through **stub** here; the Consent module is a later Phase-2 slice.
- TOTP is **not** enforced at login — it gates "Pro+ sensitive actions" via a documented step-up hook implemented later. 2FA is therefore enrolment-only today.
- No advisory/recommendation logic (SEBI educational boundary — out of scope for this module).

## Public interface (the only coupling surface)
REST (all under `/api/v1`):
- `POST /auth/signup` — create free-tier account, set session cookies (201; 409 on duplicate email).
- `POST /auth/login` — password auth, set cookies (401 generic `invalid_credentials`).
- `POST /auth/logout` — clear cookies, revoke refresh jti **and** denylist the live access jti.
- `POST /auth/refresh` — silent refresh; rotates the refresh token with reuse detection.
- `GET  /auth/me` — current user profile (401 if anonymous).
- `POST /auth/totp/setup` — provisioning URI + secret (pre-verify only).
- `POST /auth/totp/verify` — verify code, activate 2FA.
- `POST /subscriptions/webhook` — Razorpay webhook; signature-verified, idempotent.

Shared dependencies consumed by other modules: `Depends(RequireTier("free"|"pro"|"pro_plus"))` → **HTTP 402** `{error, upgrade_url}`; `Depends(current_user_or_anonymous)` → `UserContext`. No events emitted.

## Data
Postgres schema `auth`:
- `auth.users` — `id` (uuid PK), `email` (unique, lowercased), `hashed_password` (argon2id), `tier` (enum `auth.user_tier`: anonymous|free|pro|pro_plus|founder_lifetime), `totp_secret`/`totp_verified`, `risk_profile` (Onboarding writes later), `dpdp_consent_version`/`dpdp_consents` jsonb (Consent writes later), `deletion_requested_at`, timestamps.
- `auth.subscriptions` — `id`, `user_id` FK→users (CASCADE), `razorpay_subscription_id` (unique), `plan`, `status`, period start/end, timestamps.
Redis: `auth:refresh:{jti}`→uid (7d), `auth:tier:{uid}`→tier (15m), `auth:totp_attempts:{uid}` (900s, lock ≥5), `auth:access_revoked:{jti}` (TTL=token remainder), `auth:rzp_evt:{event_id}` (7d dedup), `ratelimit:{cf_ip}:{path}`.
Migration: `alembic/versions/0001_auth_init.py` (async env, `include_schemas=True`).

## Pipeline / behaviour
1. Signup/login → argon2id hash/verify → issue access (15m) + refresh (7d) RS256 JWTs → `__Host-*` cookies.
2. Refresh: decode `__Host-refresh` → atomic Redis `GETDEL` of the jti (race-free reuse detection) → owner-match assert → issue + store new pair.
3. Logout: revoke refresh jti + denylist live access jti for its remaining TTL → `current_user_or_anonymous` rejects denylisted access tokens.
4. Tier: `current_user_or_anonymous` resolves tier via `auth:tier:{uid}` cache (15m) → DB fallback. Razorpay webhook (verify-before-parse, event-id dedup) upserts the subscription, recomputes `users.tier`, flushes the cache.

## Config & flags
Env (see `.env.example`): RS256 PEM supplied either inline as `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` (literal `\n` accepted for single-line `.env`) **or** as a mounted file path `JWT_PRIVATE_KEY_FILE`/`JWT_PUBLIC_KEY_FILE` (production-preferred — keys never transit env; resolved by `config.jwt_private_key`/`jwt_public_key`, file wins, empty → fails closed). Generate dev keys: `backend/scripts/gen_jwt_keys.py`. Also `JWT_ALGORITHM=RS256`, `ACCESS_TTL_MIN=15`, `REFRESH_TTL_DAYS=7`, `COOKIE_SECURE=True`, `RAZORPAY_KEY_ID/SECRET/WEBHOOK_SECRET`. No feature flags.

## Failure modes & fallbacks
Tier cache miss → DB; deleted user → tier `anonymous` (≤15m stale on cache hit); webhook bad signature → 400 (fails closed); duplicate webhook → 200 not reprocessed; invalid/expired JWT → anonymous (client calls `/refresh`); refresh reuse/owner-mismatch → 401; ≥5 bad TOTP → 429 for 900s; rate-limit exceeded → 429 `Retry-After`.

## Dependencies
Postgres (`auth` schema, from Phase-1 init SQL), Redis, `current_user_or_anonymous`/`RequireTier` (this module owns them). Build-vs-partner: auth=build; payments=Razorpay (partner); KYC=partner (Y2).

## Verification
`python -m py_compile` clean across the backend package and the test suite. Adversarial gate (Opus takeover, 2026-05-19): verdict **REVISE → fixes applied**; config key-loading change Opus mini-gate: **ACCEPT**. A pytest suite exists under `backend/tests/` — unit (JWT alg/typ-confusion, expiry, password hashing, tier derivation, budget) + integration (signup→login→refresh-rotation→reuse→logout-revocation→rate-limit; Razorpay webhook signature/tier/idempotency). Run: `docker compose run --rm dhanradar-fastapi pytest -q` (see README → Testing). **Status: written + statically compiled, NOT yet executed** — execution is gated by the Phase-1 §2c image check (`01_init.sql` must succeed for the Postgres test DB) and is owed before any deploy (Phase 7 §5).

## Known limitations / deferred (carry to handoff)
- `RequireConsent` is a stub; `deletion_requested_at` not enforced at auth — the Consent module must enforce it **and** flush `auth:tier:{uid}` on erasure.
- `EXACT_PLAN_TIERS` is empty — substring plan→tier fallback is a **pre-billing blocker**; populate with real Razorpay plan_ids before billing goes live.
- Future checkout creation MUST server-set `notes.user_id` from the authenticated session (never client-supplied).
- Rate limiter is fixed-window (small burst at boundary); consider sliding window later. No permissive CORS may be added (cookie-auth + SameSite=lax posture depends on it).
- Signup returns 409 on duplicate email (intentional, accepted enumeration tradeoff).

## Changelog
- 2026-05-19 — Module built (Phase 2 slice 1). Security review + Opus-takeover adversarial gate; fixes: rate-limit wiring, atomic refresh `GETDEL`, `CF-Connecting-IP` keying, signup-race 409, access-token revocation on logout, webhook event-id idempotency, exact-plan map w/ fallback warning, password `max_length`. See RCA 2026-05-19.
- 2026-05-19 — Test enablement: Dockerfile now `COPY`s `alembic/`+`alembic.ini` (in-container `alembic upgrade head` was broken); config resolves PEM via `JWT_*_KEY_FILE` path or `\n`-unescaped inline; gitignored `docker-compose.override.yml` (ports + `COOKIE_SECURE=False` + key mount); pytest suite added (`backend/tests/`); pytest-asyncio fixture loop-scope landmine fixed (db_engine/db_tables → function scope). Mini-gate on key-loading: ACCEPT.
