# DhanRadar — Session State

**Last updated:** 2026-06-07

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
- **Phase 5 (Mutual Fund module, CAS→≤60s report): DONE & merged** via PR #12 (squash `ad93d65`),
  CI green. Consent-gated upload (B20, `mf_analytics`) + per-user SHA-256 dedup + <200ms enqueue;
  casparser-injectable parse; XIRR/allocation/overlap; Rating-Engine bridge → `user_fund_scores`;
  disclosure-injected, no-numeric report; 24h raw-file purge; Alembic 0004 mf schema. Residuals
  B26/B29/B30. AMFI NAV pipeline deferred.
- **Phase 6 (Notification: Telegram + Resend email + Pillow share-cards): DONE & merged** via PR #13
  (squash `7f2fc5e`), CI green (incl. the 10 integration tests against Postgres). `notify` schema + Alembic 0005
  (`notification_preferences`/`notification_log`); `publish_notification` LPUSH → Redis channel queues;
  1-min Celery-beat LPOP drain (ADR-0021) with opt-in, IST quiet-hours, per-channel daily rate caps,
  and transient retry (Telegram 3×); Telegram/Resend transports (real UA, Cloudflare-1010 guard, Resend
  not SendGrid); template renderer (label-only, disclosure+NOT_ADVICE+DISCLAIMER_VERSION injected
  structurally, no numeric/advisory); Pillow 1200×630 share-card → R2 (`storage.py`); prefs API +
  `/test` (Pro). 49 unit + 10 integration tests; full deterministic gates green. Tier-A+Compliance
  +Security fan-out: all ACCEPT-WITH-CONDITIONS, no merge BLOCKER; MAJOR/MINORs fixed in-branch (RCA
  2026-06-06); **B31** (cross-border consent, deploy gate) + **B32** (low) filed, **B26** extended.
  Pending: FE preferences screen; daily public Mood card (needs Mood Compass). Ledger:
  `reviews/phase6-notification.md`.
- **Phase 7 (Verification & Hardening): DONE on branch `phase7/verification-hardening`** (Opus
  synthesis; 5 independent auditor agents — 2 Haiku sweeps, 2 Sonnet coverage, 1 Sonnet adversarial
  §5 + 1 Sonnet re-verify). Anti-pattern sweep **CLEAN (9/9)**; constraint audit (secrets/timezone/
  budget PASS; **container memory trimmed 3572M→3072M**; DPDP→B31; audit table→B26); coverage matrix
  (launch-critical path COVERED; "missing" endpoints/events/beat-tasks are unbuilt future-phase
  modules, catalogued not defects); **§5 adversarial gate ACCEPT-WITH-CONDITIONS, no BLOCKER**. Fixed
  in-branch: `RequireConsent` anonymous→**401** safe-by-default (re-verified ACCEPT, RCA 2026-06-06);
  consented_purposes trap annotated. New **B33** (auth/session hygiene, low). Report:
  `PHASE7_VERIFICATION.md`. Merge-eligible; **NOT deploy-eligible** (deploy checklist: B26/B31/B6/B28/
  B18/B2 + live-stack runtime proofs + PC4/PC5 human approval).

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

- **CI regression guards wired (DONE):** `scripts/anti_pattern_sweep.py` (Plan §0.3, 9 guards) +
  `scripts/check_compose_memory.py` (§A6 ≤3072M) now run in the CI `guards` job, with a subprocess
  self-test (`backend/tests/unit/test_anti_pattern_sweep.py`). Closes the Phase-7 improvement suggestion
  — these regressions are caught automatically now.
- **B26 Compliance Audit module: DONE (ADDRESSED)** — `compliance` schema + Alembic 0006
  (partitioned 7-yr `ai_recommendation_audit` + DEFAULT partition + guarded pg_partman; seeded
  `disclaimers`); fire-and-forget `record_served_label`; both live seams write `(label, model,
  disclaimer_version)` (MF generation + notification deliver); served surfaces stamp the version;
  allowlisted `recommendation_type`; public rate-limited `GET /disclaimers/{type}`; daily R2 archival;
  ADR-0022. Tier-B governance ACCEPT-WITH-CONDITIONS (allowlist/version-stamp/endpoint-DoS/backdating
  fixed in-branch). New **B34** (archival R2 residency, deploy gate). Ledger
  `reviews/b26-compliance-audit.md`; feature doc `features/compliance-audit.md`.
- **Mood Compass module: DONE** — `mood` schema + Alembic 0007; pure compute (11 weights, 5 buckets,
  confidence floor → `insufficient_data` <0.30, factors); twice-daily Celery beat (09:00/16:00 IST);
  anon endpoints (`/market/mood`, `/mood/history`, `/why-today`) — **regime + band, no numeric** (non-neg
  #2, ADR-0023); `mood.snapshot.published` = B26 audit (`mood_regime`) + public card via the Notification
  interface (`post_public_card`). Tier-C governance (Architect+Compliance+Product) ACCEPT-WITH-CONDITIONS;
  sub-0.30 refuse + bucket-gap + commentary-screen fixed in-branch. Go-live gaps → **B35** (real signals,
  embed widget, empty-state, factor labels, structured event, mood_history, commentary). Ledger
  `reviews/mood-compass.md`; feature `features/mood-compass.md`.
- **UI launch screens: BUILT on branch `frontend/auth-screens`** (this session, Tier-A Builder+Architect;
  reviews batched to phase audit per the cadence rule). Notification preferences screen
  (`/settings/notifications`) + public Mood page (`/mood`, anon + sidebar link) built against the frozen
  contracts; `MoodGauge` (band-only, symmetric non-advisory colour scale) added. MF report + CAS upload +
  disclosure verified compliant; **fixed a real CAS bug** — the upload password was captured but never sent
  (RCA 2026-06-06; `useUploadCas` now threads `password`). Shared wiring (queryKeys, MSW handlers, AppShell
  nav) added. Deterministic gates green: tsc 0, eslint 0 (1 pre-existing boundaries migration warning),
  anti-pattern sweep 9/9, compliance greps clean (no numeric/advisory/Authorization in rendered copy).
  Co-located with the in-flight uncommitted auth screens on the same branch. **Pending:** in-browser visual
  pass (MSW dev server) + the batched Tier-A/Compliance phase-audit sign-off before deploy-eligible.
- **Launch-gate blockers (2026-06-07, branch `hardening/launch-gate-blockers`): 4 reviewed commits.**
  **B18** atomic incr-then-rollback premium budget cap (`00a809b`); **B20** default-deny cross-border
  contract in the AI gateway `complete()` + **B31** confirmed (notify deliver-seam step-1b gate) +
  **ci_guards** `role="switch"` false-positive fix (`894d170`); **B34** codeable parts —
  audit-write-failure metric + disclaimer-version reconcile job; R2 India-residency stays a human/infra
  deploy gate (`84903df`); **B26-admin FOUNDATION** — `RequireAdmin` fail-closed surface-hiding 404 gate plus
  the `settings.ADMIN_USER_IDS` allowlist (`207eb53`). Each slice: deterministic gates green + an
  INDEPENDENT Sonnet adversarial sign-off (codex:rescue unavailable — account not entitled for Codex
  models; approved fallback) → all ACCEPT / ACCEPT-WITH-CONDITIONS (conditions applied). **Deferred:**
  B2/B7/B8 (Razorpay — needs real plan IDs; code already fail-safe). **Remaining (next session, prompt
  handed off):** B26-admin ENDPOINTS (disclaimer activate/HTML-snapshot, label-churn + >5% gate,
  `rating_engine_changelog` + `ai_low_confidence_log` tables + Alembic migration) on the new
  `RequireAdmin`; then **B6/B28** (two-person `approved_by≠created_by` scoring activation gate +
  provisional→activated state machine). Ledgers: `reviews/b20-ai-callsite-gate.md`,
  `reviews/b26-admin-auth.md`.
- Then continue the build order: **Mood Compass** (unblocks the daily public Mood card + notification
  event consumers), then **Stock/Search**; OR close the MF data pipeline (**B29**: AMFI NAV + scheme
  metadata) so reports return real labels instead of `insufficient_data`.
- Other deploy gates before KVM4: **B31** (notification cross-border consent), **B6/B28** (scoring
  activation), **B18** (atomic AI budget), **B2/B7/B8** (Razorpay data-seeding) + the live-stack
  runtime proofs + separate human approval (PC4/PC5).
- Before MF DEPLOY: **B26** `ai_recommendation_audit` write at the report serve seam; **B29** NAV
  pipeline; **B6/B28** scoring activation gates.

## Open blockers

See `BLOCKERS.md`. Open (low/residual/non-blocking/deploy-gated): B6, B14, B16–B24, B27–B35
(**B26 now ADDRESSED**). New: **B34** (compliance R2 archival residency, deploy gate), **B35**
(Mood Compass go-live: real signals + embed widget + product polish).
Resolved: B5 (CI), **B10**, **B11** (ADR-0020), **B13**. Addressed (code/tests; data-only or
later-module work remains): B1, B2, B3, B4, B7, B8, B9, B12, B25. New: **B31** (notification
cross-border consent, deploy gate), **B32** (notification residuals, low), **B33** (auth/session
hygiene from the Phase-7 §5 gate, low).

## Agent-utilization & routing-telemetry footer

### Orchestration-config session (2026-06-07, branch `hardening/launch-gate-blockers`)

Meta session — **no product code**. User flagged that most sessions run on Opus; reviewed the last
two footers (this section confirms the leak: "all RCA / feature-doc / BLOCKERS / ledger writes" by
Opus). Cut Opus-token leaks via config (not discipline):

- **Doc-drafting nudge hook** — `PreToolUse(Write|Edit)` on doc/governance paths → reminds to draft
  prose on Tier-4 free-chain / Sonnet, Opus reviews only. Lives in `.claude/settings.local.json` +
  `.claude/hooks/doc-drafting-reminder.ps1` (**gitignored — personal**, embeds the `or.mjs` path).
  Active after a `/hooks` reload.
- **`warm-start` subagent** — `.claude/agents/warm-start.md` (Sonnet, read-only). Returns a one-page
  Phase-0 brief so Opus stops ingesting the full canon every session. Committed; active after
  `/agents` reload.
- **Routing overlay** (`CLAUDE.md`, committed) — tightened `reworked:Y` = any Opus change to a
  subagent's output; Tier-2 (`dsf`/`grok-code`) activation note; warm-start + heavy-skill-payload
  isolation rules. Carried-context insight: ingestion is re-billed every turn, so it outweighs typed
  output in long sessions.
- Est. saving ≈ **25–40k Opus tokens/session (~10–20%)**, adoption-dependent (only the hook is
  enforced; warm-start + isolation are conventions).
- **Opus** — 100% this session (advisory judgment + small config authoring in hot cache; self-execute
  beats subagent cold-start under the tiny-edit rule). **Sonnet / Haiku / codex:rescue** — n/a (no
  load-bearing/security path; no bulk sweep). Per-delegation: none.
- Commit: config + warm-start agent + routing overlay (this session). Markdownlint 0; hook logic
  pipe-tested (3 match / 3 skip); `settings.local.json` schema-validated.

### Launch-gate blockers session (2026-06-07, branch `hardening/launch-gate-blockers`)

- **Opus** — Phase-0 warm read; the B18 atomic-budget design + the B20 / `RequireAdmin` / B34
  contracts; every Phase-3 diff review; the admin-auth keystone (config + `RequireAdmin`) and the
  `ci_guards` lookbehind fix hand-written; all RCA / feature-doc / BLOCKERS / ledger writes; the
  concurrent-session branch-collision untangle.
- **Sonnet** — B20 gateway contract build; B34 (metric + reconcile job + tests); 3 independent
  adversarial sign-offs (B18, B20, admin-auth) run as the codex:rescue fallback.
- **Haiku** — n/a.
- **codex:rescue** — n/a — companion unavailable (ChatGPT account not entitled for any Codex model;
  hard 400). Sonnet takeover per the approved fallback ladder. Verdicts: **B18** ACCEPT-WITH-CONDITIONS
  (4 applied), **B20** ACCEPT, **admin-auth** ACCEPT (8 vectors, no fail-open); **B34** right-sized
  (observability + read-only reconcile → Builder+Architect, no adversarial gate).
- Per-delegation (telemetry): B20-gateway-contract · Sonnet · reworked N | B34-metric+reconcile ·
  Sonnet · reworked N | adversarial-B18/B20/admin · Sonnet · reworked N. Commits: `00a809b`,
  `894d170`, `84903df`, `207eb53`. Tests green; `ci_guards` exit 0; markdownlint 0.
- **Collision note:** a concurrent session committed B29 (`2989df3` AMFI NAV parsers) + an audit doc
  (`cd9c3dd`) onto this branch lineage mid-session. `hardening/launch-gate-blockers` and the other
  session's `feat/mf-data-pipeline` share that history (identical commits → merge to `main` cleanly).
  Do NOT branch-surgery while the other session is active.

### UI launch-screens session (2026-06-06, branch `frontend/auth-screens`)

- **Opus** — Phase-0 warm read (design system, migration strategy, frozen notification/mood
  contracts, FE component kit); orchestration; shared-file wiring (queryKeys, MSW handlers, nav);
  Phase-3 line-by-line diff review; the MF CAS-password bug fix + RCA; the type-ownership flip
  (Regime → shared MoodGauge); all docs.
- **Sonnet** — 2 parallel screen builders (notification preferences slice+page; mood slice+page+gauge),
  each against a self-contained frozen contract with disjoint files (no shared-file conflicts).
- **Haiku** — n/a (no bulk grep/triage needed this session).
- **codex:rescue** — n/a (no load-bearing/security/auth/AI-classifier path touched; UI is Tier-A,
  reviews batched to the phase audit per the cadence rule).
- Per-delegation (telemetry): notif-prefs-screen · Sonnet · reworked N | mood-page+gauge · Sonnet ·
  reworked N (Opus flipped the Regime type ownership feature→shared to match the ScoreRing precedent;
  no rebuild). Verification: tsc 0 · eslint 0 (1 pre-existing migration warning) · anti-pattern 9/9 ·
  compliance greps clean.

### Phase-7 (Verification & Hardening) — branch `phase7/verification-hardening`

Footer below is the prior Phase-7 work.

- **Phase 7 footer:** Opus — orchestration + synthesis of all five audits + remediation (RequireConsent
  401, compose memory trim, doc de-stale) + the verification report + all docs. Sonnet — 2 coverage-matrix
  auditors + the §5 adversarial gate + the independent re-verify of the security fix. Haiku — 2 mechanical
  sweeps (anti-pattern §0.3, constraint/DPDP). codex:rescue — n/a (§5 adversarial gate run as independent
  Sonnet per the approved fallback ladder; verdict ACCEPT-WITH-CONDITIONS, no BLOCKER).
- Per-delegation (telemetry): anti-pattern-sweep · Haiku · reworked N (CLEAN 9/9) | constraint-audit ·
  Haiku · reworked N (caught the 3572M memory overage) | coverage-A/B · Sonnet×2 · reworked N | §5-adversarial
  · Sonnet · reworked N (3 MAJOR, no BLOCKER) | consent-401-reverify · Sonnet · ACCEPT.
- Verification note: 212 backend unit tests pass locally + ci_guards 0 + F-lint 0 + markdownlint 0;
  compose YAML valid + memory sum = 3072M; integration suite collects (63) and runs in CI (B1). Live-stack
  hops (E2E, NTP, R2 archival, measured box memory) are deploy-time — listed in the deploy checklist.
