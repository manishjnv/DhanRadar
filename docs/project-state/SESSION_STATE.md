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

- **Run the pre-merge governance fan-out** on `hardening/b13-b10-ci-fe` (Architect + UI for B10;
  Compliance for the B13 compliance-net change), then open the PR with explicit push approval (PC5).
- **Pre-billing** remains code-ADDRESSED — only **data-only seeding** (real Razorpay plan ids +
  `total_count` + `EXACT_PLAN_TIERS`) once the dashboard exists.
- Remaining follow-ups: **B9** (billing 502/webhook tests), **B11** (scoring §2.5/§6.1 reconciliation).
- Then **Implementation-Plan Phase 3+** (Market Data Adapter + AI/LLM Gateway).

## Open blockers

See `BLOCKERS.md`. Open: B3, B4, B6 (non-blocking), B9, B11, B14. Resolved: B5 (CI), **B10**, **B13**.
Addressed (code; data-only/CI remains): B1, B2, B7, B8, B12.

## Agent-utilization & routing-telemetry footer

- Opus: 100% — Builder + Architect on all of B13/B10; self-executed (small hot-cache edits + the
  judgment-heavy compliance-net regex and module-isolation rule). Per global carve-out: ≤ a few
  files, in hot cache, two needing Opus judgment → cheaper than cold subagent starts.
- Sonnet: n/a — no parallel mechanical fan-out this session.
- Haiku: n/a — no bulk sweep.
- codex:rescue: n/a — implementation only; pre-merge Tier-B adversarial sign-off (B13 compliance net)
  still owed before PR to `main`.
- Per-delegation (telemetry): B13 ci_guards hardening · Opus · reworked N | B10 eslint-boundaries ·
  Opus · reworked Y (v6 object-selector schema rejected → reverted to working array selector + static
  message) | B10 apiClient/ScoreRing · Opus · reworked N.
