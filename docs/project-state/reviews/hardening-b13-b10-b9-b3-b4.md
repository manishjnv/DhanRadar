# Review — hardening sweep B13 + B10 + B9 + B3 + B4 (branch `hardening/b13-b10-ci-fe`)

## Gate ledger

**Tier:** B (highest touched: payments B9 + auth/DPDP B3/B4) + A (frontend B10) + compliance-net
tooling (B13) · **Class:** major · **Base:** `908ca52` · **Commits:** `e3420ab` (B13/B10),
`c3b601c` (B9), `13c4bc4` (B3/B4), plus condition fixes (this turn) · **Date:** 2026-06-05.

| Gate | Required by tier | Verdict | Reviewer |
|---|---|---|---|
| Deterministic (ci_guards + tsc + next lint + unit pytest) | always | PASS | machine |
| Architect | always | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |
| Security (adversarial) | tier B | ACCEPT-WITH-CONDITIONS | Sonnet (independent; codex:rescue substitute per fallback ladder) |
| Compliance | tier B / C-surface | ACCEPT-WITH-CONDITIONS | Opus (independent of builder) |
| UI | tier A (B10) | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |
| Product | billing (B9) | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |

**Final status:** ACCEPT-WITH-CONDITIONS — all five reviewers ACCEPT; **no BLOCKER** found. Three
conditions fixed this turn; the rest are tracked residuals. **Merge-eligible after** the conditions
(done) — NOT deploy-eligible (PC4/PC5: separate explicit approval for any push/KVM4 deploy).

## Conditions fixed this turn

- **[Security MINOR/CONDITION] `RequireConsent` `_UUID(user.user_id)` latent 500.** A non-anonymous
  but malformed `user_id` would raise `ValueError` → unhandled 500 (not a fail-closed 403). Fixed:
  wrapped in `try/except (ValueError, TypeError)` → 403 `consent_required` (`deps.py`). New test
  `test_require_consent_malformed_subject_fails_closed`.
- **[UI MINOR] apiClient build-crash legibility.** Prefixed the module-load throw with `[apiClient]`
  so a misset `NEXT_PUBLIC_API_URL` is greppable in Next build logs (`apiClient.ts`).
- **[UI MINOR] ScoreRing naming durability.** Strengthened the comment to document the deliberate
  figure→figcaption ARIA-1.2 naming (verified NVDA+Chrome / VoiceOver) and a "do not re-add
  aria-label" warning, so the single-name model isn't reverted into a double-announce (`ScoreRing.tsx`).

## Adjudications (reviewer findings resolved without code change)

- **[Architect MINOR #13] `_FakeDB` may mock the wrong DB method.** VERIFIED non-issue:
  `authenticate_user` uses `await db.scalar(select(User)…)` (`auth/service.py:146`), so the fake's
  `scalar()` is the correct seam. No change.
- **[Security #2/#3/#4, B3 #5/#6/#7, B13 #11/#12/#13] no-double-charge, fail-closed consent, ci_guards
  coverage** — all explicitly checked and found SOUND by the adversarial reviewer (lock TTL 60s >
  call timeout 25s with lock held on failure → no second gateway call; `_consent_granted` never
  fails open incl. `{"granted":"true"}`/int/null/garbage; `_ADV_SKIP` tightening introduced no new
  false-negative; asset walk is a superset of prior coverage). No change.

## Tracked residuals (new BLOCKERS) — NOT in this PR

- **B15** [Product MAJOR] `Retry-After: 60` advertises the full lock TTL, not the *remaining* TTL —
  a retry at second 59 still waits the advertised 60s. Launch-tolerable (frontend shows "retry in
  ~a minute", not a live countdown); medium-term compute remaining TTL via `redis.ttl(lock_key)`.
- **B16** [Product MINOR] Billing test coverage gaps: no annual/non-monthly plan fixture; no
  `subscription.cancelled`/`completed` test through the re-mounted `/billing/webhook`; no
  `idempotency_key_conflict` response-shape test.
- **B17** [Architect MINOR] `eslint-plugin-boundaries` rule covers feature→feature but not
  `shared → feature` (a component/lib importing a feature internal) — pre-existing layering gap,
  next ESLint hardening pass.

## Confirmed clean (all reviewers)

- Module isolation intact (scoring ⊄ billing; no cross-module coupling added). No migrations, no
  OpenAPI drift. No numeric in DOM; label vocabulary clean; Geist/warm tokens only; cookie auth /
  no Authorization header preserved. ci_guards is the compliance net and was broadened, not weakened.
