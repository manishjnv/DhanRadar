# Auth Spec

RS256 JWT (15-min access) + rotating refresh (30d, reuse-detection), OTP (6-digit, argon2-hashed, throttled), argon2id passwords, Google/Apple OIDC. Access token in memory (web) / secure storage (mobile); refresh in HttpOnly+Secure+SameSite=Strict cookie. AuthZ: RBAC (user/admin/ml_ops/support) + plan entitlements + row-level tenancy + scoped API keys. MFA: passkeys/TOTP; mandatory WebAuthn for staff; step-up for sensitive actions. Full: /docs/03 (F,G) + /docs/06 (MFA).
