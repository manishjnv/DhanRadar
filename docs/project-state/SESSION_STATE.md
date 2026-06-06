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
- **Phase 3 (Market Data Adapter §B4 + AI/LLM Gateway §B3): DONE & merged** via PR #10 (squash
  `5908a73`), CI green. Providers are stubs; models/prompts injected. Residuals B18–B23.
- **Phase 4 (Rating/Scoring Engine v1 §S): DONE & merged** via PR #11 (squash `033af0e`), CI green.
  Rule-table labels (not score), floor→refuse, 2-eval hysteresis, governance; `activated:false` →
  `provisional_model`. Residuals B24–B28.
- **Phase 5 (Mutual Fund module, CAS→≤60s report): BUILT on branch `phase5/mf-module`** (Opus
  compliance core + router; Sonnet snapshot math; `acb6def` + governance fixes). Consent-gated upload
  (B20, `mf_analytics`) + per-user SHA-256 dedup + <200ms enqueue; casparser-injectable parse;
  XIRR/allocation/overlap; Rating-Engine bridge → `user_fund_scores`; disclosure-injected, no-numeric
  report; 24h raw-file purge; Alembic 0004 mf schema. 163 unit tests; ci_guards green. Tier-B fan-out
  done (2 BLOCKERs fixed; no open blocker); residuals B26/B29/B30. AMFI NAV pipeline deferred.

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

- **Phase 4 Rating/Scoring Engine v1 BUILT on branch `phase4/rating-scoring-engine`** (Opus, Tier-C;
  engine `69756e1` + governance fixes; not pushed). Deterministic collapse pipeline (normalize →
  composite → confidence → floor → rule-table label → 2-eval hysteresis → publish), governance
  (churn>5% hold, distribution bound, two-person gate, changelog), internal token-guarded read API.
  Compliance invariants test-enforced: label≠score, no-numeric-public, risk-profile excluded,
  floor→refuse, disclosure/NOT_ADVICE.
- **Tier-C governance fan-out DONE** (Architect/Product Sonnet + Compliance Opus, independent) —
  all ACCEPT-WITH-CONDITIONS, **no BLOCKER**. Fixed in-branch: config completeness validation,
  `provisional_model` tag (activated:false), `disclaimer_version` + `prior_label`, fail-closed
  `X-Internal-Token` guard, neutral factor-agreement on sparse inputs. Residuals **B24–B28**.
  Ledger: `reviews/phase4-rating-scoring-engine.md`. Gates: 133 unit tests; ci_guards 0; compile 0.

## Next action

- **Push `phase5/mf-module` + open the PR + merge after CI green** (operator granted full permission).
- Then **Implementation-Plan Phase 6+** (Notification/Telegram, Mood Compass, then Stock/Search) per
  the build order; OR close the MF data pipeline (**B29**: AMFI NAV + scheme metadata) to make the
  CAS report return real labels instead of `insufficient_data`.
- Before MF DEPLOY: **B26** `ai_recommendation_audit` write at the report serve seam; **B29** NAV
  pipeline; **B6/B28** scoring activation gates.

## Open blockers

See `BLOCKERS.md`. Open (low/residual/non-blocking/deploy-gated): B6, B14, B16–B24, B26–B30.
Resolved: B5 (CI), **B10**, **B11** (ADR-0020), **B13**. Addressed (code/tests; data-only or
later-module work remains): B1, B2, B3, B4, B7, B8, B9, B12, B25.

## Agent-utilization & routing-telemetry footer

Phases this session (merged): hardening B13/B10/B9/B3/B4/B11 (#9); Phase 3 Market Data + AI Gateway
(#10); Phase 4 Rating/Scoring Engine (#11). Footer below is the current Phase-5 work.

- **Phase 5 footer:** Opus — orchestration + Builder (models, CAS parse, service, router, scoring
  bridge, celery task, migration — the compliance-critical core) + all condition-fixes. Sonnet —
  snapshot math (XIRR/allocation/overlap, fixed contract, Opus-reviewed) + 2 independent reviewers
  (Architect, Security-adversarial). Opus — independent Compliance reviewer. Haiku — n/a.
  codex:rescue — n/a (Tier-B Security gate run as independent Sonnet adversarial, fallback ladder).
- Per-delegation (telemetry): mf-snapshot · Sonnet · reworked N (19 tests, clean) | mf-core+router ·
  Opus · reworked Y (2 BLOCKERs fixed: per-user dedup, no engine-internals; + bounded read, password
  off-broker, opaque errors, magic-byte, migration orphan) | governance reviewers · Sonnet×2 + Opus×1
  · independent.
- Verification note: 163 backend unit tests run locally + ci_guards 0 + py_compile 0 + markdownlint 0;
  the upload→worker round trip + integration run in CI (no local PG/Redis/casparser — B1).
