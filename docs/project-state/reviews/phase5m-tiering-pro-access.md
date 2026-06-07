# Review Ledger — PHASE 5M Freemium Tiering (pro_access_until + Founding Access)

- **Change-id:** `phase5m-tiering-pro-access`
- **Branch:** `hardening/launch-gate-blockers`
- **Date:** 2026-06-08
- **Tier:** B (load-bearing: RequireTier + billing-adjacent) — full inline review this session.
- **Build sequence:** item 6 (PHASE 5M tiering). Next → B35 (Mood Compass).

## What existed vs. what was added

- **Existed:** `RequireTier` (tier-rank → 402), `resolve_tier_with_db` (900s `auth:tier:` cache),
  `_derive_tier` (Razorpay webhook writes `users.tier`), `create_checkout` B7/B8 503 inert
  fail-safe, `Subscription` model (status string), `signup_user`.
- **Added:**
  - Migration `0011_pro_access` — `pro_access_until`, `pro_access_reason`, `ai_taster_used_at` on
    `auth.users`; backfills existing users with the founding window.
  - `User` model: the three columns.
  - `config.FOUNDING_ACCESS_UNTIL` (placeholder `2026-12-31T23:59:59Z`; reset to go-live+30d at launch).
  - `deps.is_plus(user_id, db)` — LIVE (no cache) Plus check: `now < pro_access_until` OR active
    subscription; fail-closed on malformed/anonymous.
  - `RequireTier.__call__` — OR-clause bumps a sub-pro user to pro rank when `is_plus`; 402 shape
    unchanged; anonymous + `pro_plus`/`founder_lifetime` gates provably unaffected.
  - `signup_user` — founding-access stamp (`reason="founding"`) while inside the window; leaves
    `tier="free"` (so expiry is purely timestamp-driven).
  - `mf.commentary.is_commentary_entitled` + `tasks/mf.py` gate — Plus = unlimited; Free = one-time
    first-report taster (atomically claimed); otherwise `{"state":"upgrade_required"}`.

## Design rationale (auto-downgrade without a revoke job)

Time-window grants (founding/trial) leave `users.tier = "free"`, so `RequireTier` sees
`user_rank=1 < _PRO_RANK` and always calls `is_plus` LIVE — an expired `pro_access_until`
downgrades by timestamp with no cron. The 900s tier cache stays for the subscription-derived tier
only (managed by the webhook + `flush_tier_cache`). `create_checkout` is untouched (inert).

## Deterministic gates

- `ruff`: clean on all NEW code (deps/config/commentary/tasks/migration/tests). `models/auth.py` +
  `auth/service.py` carry **pre-existing** file-wide `UP045` (`Optional[X]`) debt (≈9 + ≈5 on
  origin); the new columns follow the file's uniform `Optional` idiom; not expanded into a
  load-bearing mass-rewrite. No ruff commit-hook; the gate tolerates this (branch is green).
- `anti_pattern_sweep` + `ci_guards` (non-neg + secrets): passed. Secrets grep on diff: clean.
- Tests: full unit suite **431 passed** (the 2 `test_market_data` failures are the known
  pre-existing network/DNS ones). Freemium unit tests: 18. Integration (DB-write) tests: 4 (collect;
  need Postgres) cover #4 founding stamp + #6 taster consumption.

## Acceptance proof

| # | Item | Proof |
|---|------|-------|
| 1 | `pro_access_until` column + RequireTier grants Plus when `now < it` OR active sub | migration 0011 + `test_is_plus_true_when_pro_access_until_future` |
| 2 | Expired window + no sub → Free → Plus route 402 (RFC7807+request_id via global handler) | `test_is_plus_false_when_pro_access_until_past_no_sub` + `test_require_tier_pro_raises_402_when_is_plus_false` (asserts 402 + `upgrade_required`) |
| 3 | Active subscription grants Plus regardless of `pro_access_until` | `test_is_plus_true_with_active_subscription` + `_authenticated_subscription` |
| 4 | Founding signup sets `pro_access_until` + `reason="founding"` | `test_signup_stamps_founding_access` (integration, real DB) |
| 5 | `create_checkout` UNCHANGED, still 503 inert | `test_create_checkout_503_for_unconfigured_plan` (+ file shows no diff) |
| 6 | Free one-time taster; further commentary → Plus | `test_commentary_entitled_*` (plus/unused→consume/used→refuse) + integration taster tests |
| + | Bypass guards: `pro_plus` not satisfiable by is_plus; anonymous never calls is_plus; fail-closed | `test_require_tier_pro_plus_still_gates_above_pro`, `test_require_tier_anonymous_never_calls_is_plus`, `test_is_plus_false_for_malformed/None` |

## Security review (adversarial — Sonnet takeover)

`codex:rescue` **n/a** — codex companion unhealthy (ChatGPT-account entitlement). Independent Sonnet
adversarial pass per the approved fallback ladder. **Verdict: ACCEPT-WITH-CONDITIONS** (no blockers).
Adjudication:

- **Tier-gate bypass / self-grant / checkout regression / fail-closed — CLEAR.** Ranks proven;
  `pro_access_until` written only by signup + static migration; `Subscription` rows only by the
  signature-verified webhook; `create_checkout` unchanged; `is_plus` fail-closed.
- **F4 (should-fix — stale cached `tier="pro"` could outlive a lapsed subscription up to 900s):**
  **DECLINED, documented.** The scenario is the pre-existing tier-cache TTL (governed by the
  webhook's `flush_tier_cache`), not introduced by this feature. Founding/trial grants leave
  `tier="free"` so they are always live-checked — acceptance #2 holds. The reviewer's fix (drop the
  `user_rank < _PRO_RANK` short-circuit) would add a per-request DB hit for every already-pro user
  to close a non-regression window.
- **F5 (should-fix — taster read-then-update race):** **APPLIED.** Replaced the SELECT + conditional
  UPDATE with an atomic `UPDATE … WHERE ai_taster_used_at IS NULL` claiming on `rowcount == 1`, so
  concurrent first-reports cannot both consume the taster (matches the project's atomic-primitive
  RCA lesson). Unit tests updated.
- **F6a (nit — backfill `WHERE … IS NULL` always true on a new column):** left (harmless, idempotent-friendly).

## Compliance review (Opus)

**Verdict: ACCEPT.** tier-gate=402 (shape unchanged), no numeric in the `upgrade_required` payload
(non-neg #2), `risk_profile` separation untouched (#3), module isolation holds (`is_plus` in
auth/deps reads only `auth.users` + `auth.subscriptions`; scoring imports no billing/tiering, #7),
billing stays inert (B7/B8). When a user is entitled, the full B20/B21/B22 commentary governance is
unchanged; when not, no AI is served so no disclosure/audit obligation arises. The founding backfill
is a monetization decision, not a compliance concern.

## Status

Merge-eligible (Tier-B inline ACCEPT, conditions applied). NOT deploy-eligible until the Phase-7 §5
pre-deploy gate + B2/B7/B8 plan-data seeding + B48 consent re-enable + separate human approval.
