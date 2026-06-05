# DhanRadar — Session State

**Last updated:** 2026-06-05

Living status doc. Update at every session exit (global playbook Phase 6). Keep it short; detail
lives in the linked docs.

## Where we are

- **Phase 1** (infra skeleton, KVM4 shared-infra): **done** — 8-container stack, dedicated
  cloudflared tunnel verified, pushed to `manishjnv/DhanRadar` `main`.
- **Phase 2 slice 1/4** (Auth & Tiering + async Alembic): **built; tests written but NOT yet
  executed** (see `BLOCKERS.md` B1).
- **Stage 1** (contract reconciliation, docs-only): **done** — 6 alignment docs in
  `docs/project-state/`.
- **Stage 2 (Steps 1–9): DONE & merged to `main`** (PRs #2 Steps 2-4, #3 Steps 5-9; baseline
  `05440b1` squashed/scrubbed the history for public release). All steps given a **post-merge
  governance review** 2026-06-05 (`reviews/`): all ACCEPT-WITH-CONDITIONS; one UI **BLOCKER fixed**
  (advisory verbs in `tokens.json`); conditions tracked B7–B12. PC4/PC5 still bind (no KVM4 deploy
  without separate approval).
- **Governance**: project `CLAUDE.md` overlay, `AI_GOVERNANCE_MODEL.md` (3-tier review model),
  `ARCHITECTURE_DECISIONS.md`, `SESSION_STATE.md`, `BLOCKERS.md`, and the rewritten `agent.md`
  landed 2026-06-05.
- **Scoring governance: COMPLETE** — `FINAL_SCORING_SPEC.md` is the consolidated **sole source of
  truth** (ADR-0019). Factor / weight / confidence / risk / label / threshold / governance models
  are **FINAL**; numeric axis weights remain **PROPOSED v1** pending backtest pass-gates + the
  two-person methodology gate (`BLOCKERS.md` B6, non-blocking until production activation). This
  clears `STAGE2_EXECUTION_PLAN` **PC6**.

## In flight

- **Post-merge governance review of Stage 2 Steps 1–9: DONE** (this session). 6 independent
  reviewer agents across Tier-B (Steps 5-7: RFC7807/migration/billing), Tier-C (Step 8
  ranking_configs), Tier-A (Steps 2-4 frontend) + the earlier Step-1 review. Code found sound — no
  security/compliance leak in code. Trail: `reviews/stage2-step1-openapi.md`,
  `stage2-steps5-7-backend.md`, `stage2-step8-ranking-configs.md`, `stage2-steps2-4-frontend.md`.
- **Fixed this session:** UI BLOCKER — removed the advisory-verb `signal` block from
  `frontend/styles/tokens.json` + regenerated tokens (RCA 2026-06-05); added `_concentration_note`
  to `ranking_configs_v1.json`. **B5 (CI) → RESOLVED**; new blockers **B7–B12** filed.
- **Pre-billing hardening + B12 guard: DONE + reviewed.** B12 (`ci_guards.py` broadened + now scans
  the token files — closes the scope+pattern gaps), B7/B8 (`billing.plans.razorpay_plan_id` /
  `total_count` + migration 0003 + checkout fail-safe), B2 (substring tier foot-gun removed). Tier-B
  review (Architect+Security+Compliance) ACCEPT-WITH-CONDITIONS → 2 MINORs fixed, residuals
  **B13/B14**. Code reached `main` via #6; the governance trail + 2 fixes are on
  `hardening/prebilling-fail-safes`. Trail: `reviews/prebilling-hardening.md`.

## In flight (this session)

- **Blocker sweep on branch `hardening/b13-b10-ci-fe`** (this session): B13, B10, B9, B3, B4.
  - **B9** (`c3b601c`) — `Retry-After: 60` on the lock-held checkout 409; 502-gateway no-double-charge
    test + valid-event test through the re-mounted `/billing/webhook`. Plans-seed Compliance pass is
    data-only (no seed yet). Tier-B (payments) — adversarial sign-off owed before merge.
  - **B3/B4** — `RequireConsent` made fail-closed (purpose-validated; fresh `users.dpdp_consents`
    read; 403 `consent_required`); `authenticate_user` denies login for a `deletion_requested_at`
    account (403 `account_deletion_pending`). Unit-tested (`tests/unit/test_consent.py`, 17 cases).
    Tier-B (DPDP/auth) — adversarial sign-off owed before merge. Full Consent/erasure module deferred.
- **B13 + B10 hardening: DONE on branch `hardening/b13-b10-ci-fe`** (this session). B13 — ci_guards
  advisory scan now walks all non-code label assets (not 3 hardcoded files), skip-list tightened,
  scoring skip narrowed to `ranking_configs*`, self-test added (`backend/tests/unit/test_ci_guards.py`).
  B10 — ESLint isolation matrix replaced by a generic `eslint-plugin-boundaries` rule (closes the
  fail-open that left `dashboard`/`mf` uncovered; clean-pass + planted-violation both verified);
  `apiClient` fails closed on a bad `NEXT_PUBLIC_API_URL`; `ScoreRing` aria collapsed to one
  `<figcaption>`. Gates green: ci_guards 0, tsc 0, next lint 0, pytest (ci_guards self-test) 3 passed.
  RCA logged (2× 2026-06-05). **Not pushed** (PC5). Pre-merge governance review (Architect + UI +
  Compliance-on-B13) still owed before PR to `main`.

## Next action

- **Pre-merge governance fan-out: DONE** (5 independent reviewers — Architect/Security/UI/Product
  Sonnet + Compliance Opus). All **ACCEPT-WITH-CONDITIONS, no BLOCKER**. 3 conditions fixed this turn
  (RequireConsent malformed-uuid → fail-closed 403; apiClient `[apiClient]` log prefix; ScoreRing
  aria comment). Residuals filed B15/B16/B17. Ledger: `reviews/hardening-b13-b10-b9-b3-b4.md`.
- **PR is prepped, NOT pushed (PC5).** Branch `hardening/b13-b10-ci-fe` is merge-eligible pending
  the operator's explicit push approval; PR body drafted. Push the branch + `gh pr create`, then
  squash-merge after CI green (CI runs the integration tests this box can't).
- **Pre-billing** remains code-ADDRESSED — only **data-only seeding** (real Razorpay plan ids +
  `total_count` + `EXACT_PLAN_TIERS`) once the dashboard exists. B9 plans-seed copy Compliance pass
  is also data-only (no seed exists yet).
- **B11 RESOLVED** (ADR-0020, operator chose option C): concentration reconciled as a
  catalogued-but-unweighted v1 risk sub-factor (doc-only; §2.5/§6.1 cross-pointers + `_concentration_note`).
- Remaining follow-ups: **B6** (non-blocking until prod activation), residuals **B15/B16/B17**.
- Then **Implementation-Plan Phase 3+** (Market Data Adapter + AI/LLM Gateway).

## Open blockers

See `BLOCKERS.md`. Open: B6 (non-blocking), B14, B15, B16, B17 (all low/residual). Resolved: B5 (CI),
**B10**, **B11** (ADR-0020), **B13**. Addressed (code/tests; data-only or later-module work remains):
B1, **B2**, **B3**, **B4**, B7, B8, **B9**, B12.

## Agent-utilization & routing-telemetry footer

- Opus: 100% — Builder + Architect on all of B13/B10; self-executed (small hot-cache edits + the
  judgment-heavy compliance-net regex and module-isolation rule). Per global carve-out: ≤ a few
  files, in hot cache, two needing Opus judgment → cheaper than cold subagent starts.
- Sonnet: 4 independent reviewers (Architect / Security-adversarial / UI / Product) for the pre-merge
  governance fan-out on the branch — all ACCEPT-WITH-CONDITIONS.
- Haiku: n/a — no bulk sweep.
- codex:rescue: n/a — Tier-B Security gate run as an independent Sonnet adversarial review (fallback
  ladder, per prior-session precedent); a formal codex pass remains available.
- Per-delegation (telemetry): B13 ci_guards hardening · Opus · reworked N | B10 eslint-boundaries ·
  Opus · reworked Y (v6 object-selector schema rejected → reverted to working array selector + static
  message) | B10 apiClient/ScoreRing · Opus · reworked N | B9 billing Retry-After + tests · Opus ·
  reworked N | B3/B4 DPDP gate primitives · Opus · reworked N.
- Verification note: unit tests run locally (66 backend unit incl. 17 new B3/B4 + 3 ci_guards);
  billing/auth INTEGRATION tests compile+collect only — no local Postgres/Docker (B1), they run in CI.
