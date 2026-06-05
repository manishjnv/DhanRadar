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

## Next action

- Clear **pre-billing** blockers before enabling charges: B7 (Razorpay plan-id mapping),
  B8 (`Plan.total_count`), B2 (`EXACT_PLAN_TIERS`), B9 (billing test gaps).
- **Broaden `ci_guards.py`** advisory detection (B12) — the gate that should have caught the tokens
  BLOCKER.
- Then proceed to **Implementation-Plan Phase 3+** (Market Data Adapter + AI/LLM Gateway).

## Open blockers

See `BLOCKERS.md`. Open: B2, B3, B4, B6 (non-blocking), B7–B12. Resolved: B5 (CI).
Addressed: B1 (CI runs pytest). Pre-billing: B2, B7, B8, B9.

## Agent-utilization & routing-telemetry footer

- Opus: orchestration + Builder (openapi fixes, tokens BLOCKER fix) + Compliance reviews + adjudication — Tier-0.
- Sonnet: independent Architect / Security / Product / UI reviewers (post-merge Tier-A/B/C fan-out).
- Haiku: n/a — no bulk sweep.
- codex:rescue: n/a — substituted by independent Sonnet adversarial review (fallback ladder); formal codex pass on payments still available (B9).
- Per-delegation: stage2-steps5-7-backend · Tier B · ACCEPT-WITH-CONDITIONS · reworked N (tracked) | stage2-step8 · Tier C · ACCEPT-WITH-CONDITIONS · N | stage2-steps2-4-frontend · Tier A · ACCEPT-WITH-CONDITIONS · reworked Y (UI BLOCKER fixed).
