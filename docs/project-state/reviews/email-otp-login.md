# Gate Ledger — Email OTP as an alternative login factor

**Change-id:** `email-otp-login`
**Branch:** `feat/b37-backup-cron-drill` (email-OTP slice)
**Date:** 2026-06-12
**Tier:** **B** (auth/session — load-bearing path; full inline Security + Compliance review,
not deferred to the phase audit).
**Authority extension:** ADR-0031 (email OTP login is net-new — not in the pre-existing
canon; the OTP-first IGNORE scope is explicitly narrow, and this feature falls outside it).

## What shipped

A 4th way to obtain the **same** RS256 `__Host-` cookie session as password, Google SSO, and
TOTP login: **email OTP as an alternative first factor** (founder request 2026-06-12).

- `POST /api/v1/auth/email-otp/request` — sends a 6-digit code to the supplied email address.
  Always returns **202** (enumeration-safe even for unknown email, cooldown, or daily cap
  exceeded). Returns **503 `email_otp_not_configured`** when `RESEND_API_KEY` is unset —
  fail-closed, matching the SSO pattern. Per-IP rate limit: 3 req/min.
- `POST /api/v1/auth/email-otp/login` — verifies the 6-digit code and issues cookies.
  Returns a **generic 401** on every failure (unknown email, wrong code, expired, attempts
  exceeded, code already used). Per-IP rate limit: 5 req/min. Successful verification issues
  RS256 `__Host-` cookies via the same `set_auth_cookies` path as all other login methods.

**UI:** the login page's code-mode is now email-OTP (replaced the authenticator-app TOTP
code entry UI; `POST /auth/totp/login` stays live API-side and the settings → Security
enrolment page is untouched). Prominent secondary button "Sign in with email code"; two-phase
flow — email address → 6-digit input with auto-submit on the 6th digit, manual "Log in"
fallback, 60-second countdown resend.

**Redis keys:**

| Key | Purpose | TTL |
|---|---|---|
| `auth:email_otp:{uid}` | SHA-256 hash of the active code | 600 s |
| `auth:email_otp_cooldown:{uid}` | Send-request cooldown gate (`SET NX`) | 60 s |
| `auth:email_otp_daily:{uid}` | Daily-send cap counter (`SET NX` + `INCR`) | Until midnight |
| `auth:email_otp_attempts:{uid}` | Failed-verify attempt counter | 15 min |
| `auth:email_otp_used:{uid}:{hash}` | Per-code atomic consume marker | Never deleted |

**No DB migration.** Email delivery via `notifications.channels.deliver_email` (Resend;
interface-only coupling; code never logged). The send is fire-and-forget
(`asyncio.create_task`) to remove response-timing as an enumeration oracle.

**Schema hardening:** digit regex uses `[0-9]` not `\d` (Unicode-digit hardening; same fix
applied to existing TOTP schemas).

**Deletion-pending accounts:** a `deletion_requested_at` account receives a silent **202**
on the request endpoint; a **403** is returned on the login endpoint — but only AFTER the
code is proven correct, so the 403 is not an enumeration oracle (matching the accepted TOTP
residual posture per ADR-0029; Compliance ACCEPT-WITH-CONDITIONS condition 2 below).

## Deterministic gates

- Backend unit tests: **46 passed** (`test_email_otp.py`); full unit suite green except
  one PRE-EXISTING `main` failure (`test_mf_tracking::test_monthly_rescore_skips_free_users`
  — reproduced on clean `main`, confirmed out of lane). ✅
- Ruff (changed files): **clean**. ✅
- Frontend: `tsc --noEmit` clean; **165 tests pass** (vitest). ✅
- Secrets scan / CI guards: clean. ✅
- Integration tests (email-OTP flows): **CI-only** (no local Postgres) — gated by
  `gh pr checks`, NOT claimed green here.

## Security review (Tier-B, independent) — Sonnet adversarial takeover

`codex:rescue` unavailable on this account → Sonnet adversarial takeover (per standing
fallback).

**Verdict: REVISE → re-verified → ACCEPT (2026-06-12, focused final pass on the per-code marker).**

**Initial pass — REVISE:**

- **MAJOR — TOCTOU double-spend (one code, two concurrent sessions):** the first verify
  implementation used a per-uid consume marker (`auth:email_otp_used:{uid}`). Two concurrent
  requests could both read "not used" before either write, admitting both. **Fixed** — the
  marker is keyed per code: `auth:email_otp_used:{uid}:{hash}` (`SET NX` returns `False` for
  any second consumer of the same code; deliberately NOT cleared on success — a "clear on
  success" approach would reopen the race if the clear races with a concurrent request). The
  reviewer's suggestion of "clear on success" was considered and explicitly rejected: the
  per-code key ensures the race is closed regardless of session timing, at the cost of a
  600-second key (TTL self-heals).
- **MAJOR — deletion-pending 403 placed before code verification:** the original
  `deletion_requested_at` check occurred before OTP verification, making the endpoint an
  account-existence oracle for any caller who knows (or guesses) a pending-deletion email
  address. **Fixed** — the 403 is now issued only after the code is proven correct (same
  posture as the TOTP-login accepted residual in ADR-0029).
- **MINOR — `INCR`/`EXPIRE` non-atomicity:** the daily cap counter used two separate Redis
  commands (`INCR` then `EXPIRE`), so a crash between them could leave the cap key without a
  TTL (permanent cap). **Fixed** — replaced with a `SET NX` seed + atomic `INCR` + `EXPIREAT`
  on key creation only, ensuring the TTL is always set on first write.
- **MINOR — `\d` admits Unicode digits:** digit validation in OTP schemas used `\d`, which
  matches non-ASCII digit codepoints in Python. **Fixed** — all OTP digit patterns use
  `[0-9]` (applied to both the new email-OTP schemas and the existing TOTP schemas).

**Re-verification pass:** the initial per-uid consume-marker fix (`auth:email_otp_used:{uid}`)
was found to introduce a **post-login lockout**: the marker was keyed on uid only, so after a
successful login the mark would persist and block any subsequent code request from that user
for the key's TTL (approximately 10 minutes). The per-code keying
(`auth:email_otp_used:{uid}:{hash}`) was the fix: each marker is specific to a single issued
code, so a fresh request generates a new code with a new marker, avoiding the lockout entirely.

**Final verdict: ACCEPT** (2026-06-12 — all 5 checks of the focused pass clean; tests 46/46).

Probed clean (evidence in review): per-IP rate-limit independence, send-side
enumeration-safety (202 always), response-timing oracle via fire-and-forget send,
attempts-lock 401 not 429 (not an account oracle), code-hash storage (never plaintext),
session-issuance parity with other login paths, deletion-pending oracle width.

## Compliance review (Tier-B) — Opus

- **SEBI advisory boundary:** not engaged — no score/label/AI/advisory surface in the diff. ✅
- **DPDP consent:** no bypass. Email OTP creates a session via the same `set_auth_cookies`
  path as all other login methods; consent is gated downstream on data-processing routes via
  `RequireConsent`, which is unchanged. B48 prod-enforcement guard untouched. ✅
- **PII handling:** the email address is already stored in `auth.users`; the OTP code is
  stored as a SHA-256 hash only (never plaintext, never logged). The send is fire-and-forget
  via `notifications.channels.deliver_email` (interface-only coupling; Resend). ✅
- **Erasure parity (B4):** `deletion_requested_at` accounts are refused on the login endpoint
  (403 after code verification), matching the accepted TOTP-login posture. ✅
- **DPDP cross-border — transactional auth email (condition 1):** Resend is a non-Indian
  processor. The payload is the user's email address (already stored, no new PII category) +
  an ephemeral 6-digit code. The trigger is user-initiated (the user explicitly requests a
  code). This differs from B31's system-initiated notification fan-out. A pre-auth consent
  gate would create a lockout circularity (the user needs to log in to grant consent, but
  needs consent to receive the login code). Compliance accepts this posture pending counsel
  confirmation — see B64 (OPEN, low). ✅ (conditional)

**Verdict: ACCEPT-WITH-CONDITIONS.**

Conditions:

1. ADR-0031 is recorded in-PR before merge (done — see ARCHITECTURE_DECISIONS.md).
2. The `deletion_requested_at` 403-after-verify posture is recorded as a deliberate
   scope-match to the TOTP-login accepted residual (ADR-0029), not a new deviation.
3. B64 (OPEN, low) is filed for counsel confirmation that cross-border transactional auth
   email via Resend (non-Indian processor; payload = email address + ephemeral code;
   user-initiated; pre-auth circularity prevents a consent gate) is permissible under DPDP
   without a per-processor consent gate. Email template stays strictly transactional.

## Architect / Builder

- Builder: implemented per contract (Tier-B inline; backend + frontend), Opus-revised for
  the two MAJOR security findings, the re-verification lockout finding, and the two MINOR
  hardening items.
- Architect: aligns to non-neg #5/#6 (RS256, `__Host-`, no bearer, `/api/v1`, RFC7807);
  fire-and-forget send preserves response-time neutrality; per-code consume marker is the
  correct TOCTOU-close without a post-login lockout regression; new scope recorded in
  ADR-0031; no DB migration (Redis only).

## Status

**COMPLETE (merge-eligible).** All deterministic gates green locally; Tier-B Security (ACCEPT
after revise + re-verify) + Compliance (ACCEPT-WITH-CONDITIONS, all 3 conditions satisfied)
logged; Builder + Architect signed.

**NOT deploy-eligible** until: CI integration tests pass on the PR; `RESEND_API_KEY`
provisioned in the KVM4 `.env` (currently on the missing-secrets list — founder action
required); separate explicit human deploy approval. Email OTP returns 503 until
`RESEND_API_KEY` exists; TOTP login and Google SSO are unaffected by this dependency.
