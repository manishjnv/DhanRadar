# Review — B48 DPDP consent gate pre-launch kill-switch

**Change-id:** b48-consent-killswitch
**Date:** 2026-06-07
**Branch:** `hardening/launch-gate-blockers`
**Tier:** B (DPDP / compliance load-bearing path — `deps.py` consent gate)
**Decision driver:** user decision — disable the consent gate during pre-launch dev
(no real user data; consent-capture UI B44 not yet built) and auto-re-enforce at the
2026-07-15 launch.

## What changed

- `config.py` — new `DPDP_CONSENT_ENFORCED: bool = True` (default ENFORCED). New
  `consent_bypassed` computed property = `not DPDP_CONSENT_ENFORCED and ENV ∈
  {development,test,ci}`. New `model_post_init` boot guard: disabling enforcement in
  any non-allowlisted ENV raises `ValueError` at startup (hard crash, fail-safe);
  one startup warning when the bypass is legitimately active.
- `deps.py` — single chokepoint `_consent_granted()` returns `True` when
  `settings.consent_bypassed`. This disables all three surfaces that route through it:
  `RequireConsent` (route dep), `consent_granted()` (notify deliver seam), and
  `assert_consent()` (worker/AI call sites). The anonymous→401 auth guard in
  `RequireConsent` is untouched — auth is still required; only the consent check is relaxed.
- `tests/unit/test_consent.py` — bypass-on grants all (dev); bypass ignored in prod;
  boot-guard rejects 6 non-dev envs; default-is-enforced.
- `.env` (gitignored, local) — `DPDP_CONSENT_ENFORCED=false` set for dev.
- `.env.example` — documents the knob, default `true`, with the fail-safe note.

## Why this design (not a hardcoded bypass / not gate removal)

- **Default-safe:** the gate is ON unless explicitly turned off; production is unaffected
  by default.
- **Cannot reach prod:** the bypass is an ALLOWLIST (`development/test/ci`), not a
  denylist — any other env (production, staging, preview, mis-cased, unset) keeps the
  gate enforced, and a leaked `false` on such a box is a hard boot failure. Re-enabling
  at launch is "do nothing in prod / set `ENV=production`", not a memory-dependent flip.
- **Single chokepoint:** grep confirmed no code reads `dpdp_consents` outside
  `_consent_granted`; the AI gateway keeps its independent param-level default-deny.

## Adversarial review (independent)

Security/Compliance reviewer = independent **Sonnet takeover** (codex:rescue unavailable —
account not entitled for Codex models; approved fallback ladder). 7 enumerated attack
vectors (prod-leak path, default-safety, type-order, anon guard, log flood/PII, re-enable
residual, chokepoint completeness).

**Verdict: ACCEPT-WITH-CONDITIONS.** Conditions applied in-session before commit:

1. **(required)** `ENV != "production"` was a fail-open foot-gun (staging/`PROD`/whitespace/
   unset slipped through). → Inverted to an explicit dev allowlist, case+whitespace
   normalized (`_CONSENT_BYPASS_ALLOWED_ENVS`).
2. **(required)** No startup assertion. → Added `model_post_init` that refuses to boot when
   the bypass is set outside the allowlist (verified: `ENV=production` + `false` raises).
3. **(optional, applied)** Per-call warning would flood logs. → Moved to a single startup
   warning; `_consent_granted` just returns True.

Residual (finding 4, out-of-band): the deploy pipeline must set `ENV=production` explicitly
on the prod box. Tracked in B48 / the deploy checklist.

## Gates

- `pytest tests/unit/test_consent.py` — 28 passed.
- Full unit suite — 350 passed, 2 failed (pre-existing network DNS failures in
  `test_market_data.py` AMFI fetch; unrelated to this change).
- `ci_guards.py` PASS · `anti_pattern_sweep.py` PASS · `py_compile` clean.
- Runtime proof: dev `.env` → `consent_bypassed=True` (one warning); `ENV=production` +
  `false` → boot `ValueError`.

## MUST DO before launch (B48 close-out)

- Set `DPDP_CONSENT_ENFORCED=true` (or remove the line) in the deploy env, AND set
  `ENV=production` (which alone forces enforcement).
- Verify a consent-gated route (e.g. `POST /mf/upload`) returns 403 without a grant.
- Ship B44 (consent-capture UI) so users can actually grant; wire B20/B31 cross-border grants.
