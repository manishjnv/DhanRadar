# DhanRadar — Session State

**Last updated:** 2026-06-06

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
- **Post-Stage-2 hardening (B13/B10/B9/B3/B4/B11): DONE & merged** via PR #9 (squash `76f7525`),
  CI green. ADR-0020 (concentration). Residuals B15/B16/B17.
- **Phase 3 (Market Data Adapter §B4 + AI/LLM Gateway §B3): BUILT on branch
  `phase3/market-data-ai-gateway`** (not pushed). 3A Market Data (Sonnet, Opus-reviewed; `917e5ef`)
  with 3B AI Gateway (Opus, Tier-B; `3cd2fef`) and governance fan-out fixes. Providers are stubs (no
  vendor keys / AA partner); models/prompts injected (Admin source + live verify deferred). 112
  unit tests; ci_guards green.

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

- **Phase 3 BUILT on branch `phase3/market-data-ai-gateway`** (2 commits + governance fixes; not pushed).
  - **3A Market Data Adapter** (`917e5ef`, Tier-A) — Sonnet-built against a fixed contract, Opus
    diff-reviewed. Provider-agnostic, YAML ladders, per-provider circuit breaker, normalized events,
    8 stub providers (no vendor keys; AA explicit stub), pluggable event sink. 24 unit tests.
  - **3B AI/LLM Gateway** (`3cd2fef`, Tier-B) — Opus-built. OpenRouterGateway (round-robin, 429-rotate
    no-sleep, 402-credit no-retry, Sonnet spillover, 3-strike skip), AIOutputBase + QualityValidator
    (schema + advisory screen), budget governor increment (BudgetMeter). Models/prompts injected.
  - **Governance fan-out DONE** (Architect/Security Sonnet + Compliance Opus, independent). Security
    REVISE + 1 Compliance BLOCKER → **all fixed this turn**: advisory list expanded (core set),
    high-stakes premium loop bounded by 3-strike, free counter debits every served call, atomic budget
    init, soft-cap warning, model_copy disclaimer guard, empty-choices guard, adapter `skipped`
    diagnostics. Residuals **B18–B23**. Ledger: `reviews/phase3-market-data-ai-gateway.md`.
  - Gates: 112 unit tests pass; ci_guards 0; py_compile clean. **Not pushed (PC5).**

## Next action

- **Push `phase3/market-data-ai-gateway` + open the PR** (needs operator PC5 approval). CI runs the
  integration tests this box can't; squash-merge after green.
- Wire-up work for the consuming modules (MF/Stock/Mood) must, before any user-specific payload reaches
  the gateway, land the **B20** cross-border + `RequireConsent` call-site gate and **B21** audit/model_used.
- Remaining follow-ups: residuals **B15–B23**; **B6** (non-blocking until prod activation).
- Then **Implementation-Plan Phase 4** (Rating/Scoring Engine + MF module: CAS→60s report).

## Open blockers

See `BLOCKERS.md`. Open (low/residual/non-blocking): B6, B14, B15, B16, B17, B18, B19, B20, B21, B22,
B23. Resolved: B5 (CI), **B10**, **B11** (ADR-0020), **B13**. Addressed (code/tests; data-only or
later-module work remains): B1, B2, B3, B4, B7, B8, B9, B12.

## Agent-utilization & routing-telemetry footer

- Opus: 100% — Builder + Architect on all of B13/B10; self-executed (small hot-cache edits + the
  judgment-heavy compliance-net regex and module-isolation rule). Per global carve-out: ≤ a few
  files, in hot cache, two needing Opus judgment → cheaper than cold subagent starts.
- (Earlier this session) hardening branch B13/B10/B9/B3/B4/B11: Opus builder + 5 Sonnet/Opus reviewers;
  merged via #9. Phase-3 footer below supersedes for the current work.
- **Phase 3 footer:** Opus — orchestration + Builder (3B AI Gateway, Tier-B) + Compliance reviewer +
  all adjudication/condition-fixes. Sonnet — 3A Market Data Adapter (builder, fixed contract) + 2
  independent reviewers (Architect, Security-adversarial). Haiku — n/a. codex:rescue — n/a (Tier-B
  Security gate run as independent Sonnet adversarial, fallback ladder).
- Per-delegation (telemetry): 3A market-data · Sonnet · reworked N (Opus review clean, MAJORs tracked)
  | 3B ai-gateway · Opus · reworked Y (Security REVISE + Compliance BLOCKER → fixed in-branch:
  advisory list, premium-loop bound, free-counter debit, atomic init, model_copy guard) | governance
  reviewers · Sonnet×2 + Opus×1 · independent.
- Verification note: 112 backend unit tests run locally + ci_guards green; the integration tests
  (billing/auth) run in CI only — no local Postgres/Docker (B1).
