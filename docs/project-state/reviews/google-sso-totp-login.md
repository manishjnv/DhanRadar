# Gate Ledger — Google SSO + TOTP standalone login

**Change-id:** `google-sso-totp-login`
**Branch:** `feat/google-sso-totp-login` (from `origin/main`)
**Date:** 2026-06-12
**Tier:** **B** (auth/session — load-bearing path; full inline Security + Compliance review,
not deferred to the phase audit).
**Authority extension:** ADR-0029 (Google SSO + TOTP-login are net-new — not in the pre-existing
canon, which scoped TOTP to Pro+ sensitive-action step-up only).

## What shipped

Two new ways to obtain the **same** RS256 `__Host-` cookie session as password login:

1. **Google SSO** — server-side OAuth 2.0 authorization-code flow with PKCE (S256) + nonce.
   - `GET /api/v1/auth/google/start` — fail-closed 503 if any Google credential is unset; stores
     `{nonce, code_verifier, next}` in Redis (`auth:oauth_state:{state}`, TTL 600s); 302 to Google.
   - `GET /api/v1/auth/google/callback` — single-use state (`GETDEL`); exchanges the code with the
     stored verifier; verifies the id_token **locally** against Google's JWKS (RS256-only, `aud`,
     `iss`, `nonce`, `exp`); requires `email_verified=True`; resolves/creates the user; issues
     cookies on a 303. Every user-facing failure is a `/login?error=…` redirect, never a JSON page.
2. **TOTP standalone login** — `POST /api/v1/auth/totp/login` (email + 6-digit code), an
   **alternative first factor**, not a second factor (founder decision). Enumeration-safe generic
   401 on every failure (unknown email / not enrolled / wrong code / locked); per-account
   brute-force lock + per-code single-use replay guard (Redis `SET NX`, 90s).

Model: `hashed_password` now nullable (SSO-only accounts); new unique `google_sub`. Migration
`0018_google_sso`. Frontend: dual-mode login page (Google button + TOTP mode with auto-focus,
auto-submit on the 6th digit, inline error), settings → Security enrolment page.

## Deterministic gates

- Backend unit tests: **30 passed** (incl. `test_google_oauth` + CI guards). ✅
- Ruff (changed files): **clean** except one pre-existing UP042 on `UserTierEnum` (untouched; main
  carries it too). ✅
- Frontend: `tsc --noEmit` clean; **156 tests pass** (150 → 156, +6 new auth tests). ✅
- Secrets scan / CI guards: clean (MSW mock secret renamed to clear the `secret=` heuristic). ✅
- Integration tests (SSO + TOTP-login flows): **CI-only** (no local Postgres) — gated by
  `gh pr checks`, NOT claimed green here.

## Security review (Tier-B, independent) — Sonnet adversarial takeover

`codex:rescue` unavailable on this account → Sonnet adversarial takeover (per standing fallback).

**Verdict: REVISE → re-verified ACCEPT after fixes.**

Findings and resolution:

- **MAJOR — open redirect via backslash** in `validate_next` (backend) and `safeNext` (frontend):
  `/\evil.com` passed the `//` guard but browsers fold `\`→`/`. **Fixed** — both now reject
  backslashes and (backend) control chars; unit vectors added (`/\evil.com`, `/\/evil.com`,
  embedded `\`, `\n`/`\t`).
- **MAJOR — account takeover via email auto-link**: DhanRadar never verifies local emails, so
  auto-linking a Google identity onto an existing **password** account let a Google-side email
  controller hijack it. **Fixed** — `_resolve_existing_email_user` now raises `_AccountExistsError`
  for any password-bearing row → callback redirects `/login?error=account_exists_use_password`; no
  `google_sub` write, no cookies. Integration test inverted to assert rejection.
- **MINOR — cross-surface TOTP lockout DoS**: login attempts shared the enrolment counter, letting
  a sprayer lock a victim out of `/totp/verify`. **Fixed** — separate
  `auth:totp_login_attempts:{uid}` prefix.
- **NIT — 7–8 digit codes** could waste a lockout attempt. **Fixed** — `TOTPLoginRequest` is now
  strictly `^\d{6}$`.

Probed clean (evidence in review): state replay (atomic `GETDEL`), PKCE binding, nonce comparison,
alg:none/HS confusion, JWKS kid confusion, `email_verified` bypass, `google_sub` conflict path,
session parity (refresh-jti + founding-access + audit on all paths), NULL-password auth safety,
error-param XSS, TOTP secret exposure, brute-force math, replay-guard atomicity.

## Compliance review (Tier-B) — Opus

- **SEBI advisory boundary:** not engaged — no score/label/AI/advisory surface in the diff. ✅
- **DPDP consent:** no bypass. The new auth entry points create an account + issue a session,
  exactly as `POST /auth/signup` does today; consent is gated downstream on data-processing routes
  via `RequireConsent`, which is unchanged. B48 prod-enforcement guard untouched. ✅
- **PII handling:** `email` already stored; `google_sub` is an opaque provider id (low sensitivity).
  id_token / authorization code / code_verifier are **never logged** (asserted in `google.py`).
  Security anomalies (`google_sub_conflict`, `totp_locked`) fire `record_security_event`. ✅
- **Erasure parity (B4):** `deletion_requested_at` accounts are refused on both new paths (403 /
  deletion-pending redirect), matching `authenticate_user`. ✅

**Verdict: ACCEPT.**

## Architect / Builder

- Builder: implemented per contract (parallel Sonnet, backend + frontend), Opus-revised for the two
  MAJOR security findings + naming/scope-copy.
- Architect: aligns to non-neg #5/#6 (RS256, `__Host-`, no bearer, `/api/v1`, RFC7807); new scope
  recorded in ADR-0029; single linear migration head preserved (`0017` → `0018`).

## Status

**COMPLETE (merge-eligible).** All deterministic gates green locally; Tier-B Security (ACCEPT after
revise) + Compliance (ACCEPT) logged; Builder + Architect signed.

**NOT deploy-eligible** until: CI integration tests pass on the PR; `GOOGLE_CLIENT_ID/_SECRET/
_REDIRECT_URI` provisioned in the KVM4 `.env`; migration `0018` run on the box; separate explicit
human deploy approval. SSO returns 503 until the credentials exist; TOTP login needs no secrets.

## Deploy record (2026-06-12)

All four deploy conditions cleared, with explicit founder approval in-session:

1. CI green on the PR (backend incl. both integration flows, frontend, migrations, guards;
   `lint` red = pre-existing advisory debt, zero new findings).
2. Google OAuth client created by the founder; `GOOGLE_CLIENT_ID/_SECRET/_REDIRECT_URI` synced
   to the KVM4 `.env`.
3. Squash-merged as `6468797`; `scripts/deploy.sh deploy` run (env-hash full-stack recreate,
   expected); migration `0017 → 0018` in the deploy log; prod DB asserts `alembic_version=0018`
   and `users.google_sub` exists.
4. Smoke: `/api/v1/health` 200 · `GET /auth/google/start` 302 → accounts.google.com
   (PKCE S256 + nonce, prod redirect_uri) · `POST /auth/totp/login` enumeration-safe 401.
   All 9 containers running (healthy where checked).

**Status: LIVE in production.**
