# DhanRadar — Session State

**Last updated:** 2026-06-08

Living status doc. Update at every session exit (global playbook Phase 6). Keep it short; detail
lives in the linked docs.

## Monetization model decided (2026-06-08) — implement at Phase 5

MF launch = **freemium + Founding Access**, written into `DhanRadar_Implementation_Plan.md`
**PHASE 5M** (ready to slot into Phase 5 execution; small `pro_access_until` add at Phase 2).
Paid tier = **DhanRadar Plus** (₹149/mo · ₹1,199/yr; Founding ₹599/yr locked); paywall axis =
tracking over time; AI commentary = Pro + one-time taster, metered. Free is **gateway-
independent** — billing go-live is a data-only flip via the existing B7/B8 checkout fail-safe.
Full contract + open-item-free decision log in PHASE 5M.

## Deploy-gate hardening + governance audit (2026-06-08, branch `hardening/launch-gate-blockers`)

Concurrent-session note: this branch had 28 uncommitted frontend files from a parallel session.
That session was confirmed not running; its work (auth/mood/settings/notifications screens +
responsive-ish AppShell rework) was verified coherent (tsc + lint clean, but **no component tests**)
and parked as one WIP commit (`868688c`) with explicit owner approval, then this session continued.

**Blockers ADDRESSED this session (all on the branch / PR #28, none merged):**

- **B36** (`7035400`, `71a3ed2`) — deploy/rollback automation (`scripts/deploy.sh`, `rollback.sh`) +
  runbook. Fixed a **duplicate-`0008` Alembic branch** that broke `alembic upgrade head` (renumbered
  mf_nav → `0008a`, single head `0009`; RCA logged). Pre-push adversarial review applied.
- **B37** (`c93e387`, `71a3ed2`, `8e422af`) — `scripts/backup.sh` + `restore.sh`: nightly `pg_dump`
  and Redis AOF → India-resident R2, checksum-verified, + runbook. Audit path-traversal fix applied.
- **B40** (`ddc3f98`) — CI: backend→`timescaledb-ha:pg16`, NEW migrations job (alembic up→down→up on
  the real image), ruff+mypy invoked (ADVISORY — see B40-followup), mocks-off build.
- **B39** (`a152b2b`) — vitest + 17 tests, `--passWithNoTests` dropped, vitest global types fix.
- **B45** (`a152b2b`, `ddc3f98`) — mocks-off CI build + Playwright smoke test.
- **B46** (`c86c413`) — CAS error surfaces (no infinite spinner).
- **Security (audit conditions)** (`8e422af`) — Sentry `_scrub_event` strips exception msgs +
  `logentry` (DPDP leak); `restore.sh` MANIFEST filename allowlist. +2 tests; 26/26 observability green.

**Governance audit (pre-deploy, 4 independent Sonnet reviewers) — verdict: NOT MERGEABLE.**
Security ACCEPT-WITH-CONDITIONS (2 MAJOR fixed this session) · Compliance **REJECT** · UI **REJECT** ·
Product **NO-GO**. Full verdict on **PR #28** (draft). Hard merge-blockers remaining:

- **B44 (legal)** — DPDP consent-capture is genuinely unbuilt: **no grant/revoke writer endpoint, no
  consent UI**. Consent is *enforced* (B48 default-true) but ungrantable → every consent-gated route
  bricked + no lawful consent record. **Load-bearing Tier-B feature — not started.**
- **B42** — AppShell still desktop-only (the WIP rework did not add responsive/hamburger/bottom-nav).
- **B29** — MF NAV pipeline unseeded → every fund scores `insufficient_data` (core wedge void).
- New follow-ups to file: **B40-followup** (promote ruff/mypy from advisory→blocking after a
  lint-cleanup: ~361 ruff findings, never mypy-checked); admin routes lack `Idempotency-Key`;
  `ADMIN_USER_IDS` must be real UUIDs pre-launch (currently non-UUID → admin module non-operational).

**Merge / deploy:** NOT done, correctly. Merge blocked by Gate 0 (open Compliance BLOCKER B44);
deploy additionally needs human PC5 + infra residuals. PR #28 stays a **draft**.

**Next action:** fresh session for **B44** (consent table/writer endpoint + capture UI + inline
Tier-B Security/Compliance review), then **B42**. Start prompt is in the handoff (below / chat).

**Agent utilization (this session):**

- **Opus** — orchestration, concurrency/parking judgment, alembic-branch fix, CI authoring + the
  config-contract analysis, the 3 bounded fixes, audit adjudication, all commits.
- **Sonnet** — B36/B37 script drafts (`reworked: Y`, health-gate container-id bug + 3 adversarial
  conditions); B39/B45 frontend tests (`reworked: Y`, added vitest-env.d.ts — tests broke tsc);
  governance audit ×4 Security/Compliance/UI/Product (`reworked: N`, findings adopted as-is).
- **Haiku** — n/a.
- **codex:rescue** — n/a (companion unhealthy: `gpt-5` 400); adversarial + audit ran via Sonnet
  takeover per the approved fallback.

## DPDP consent kill-switch B48 (2026-06-07, branch `hardening/launch-gate-blockers`)

User decision: disable the fail-closed DPDP consent gate during pre-launch dev (no real
user data; consent-capture UI B44 not built) and auto-re-enforce at the 2026-07-15 launch.
Built as a fail-safe env kill-switch, NOT a hardcoded bypass:

- `DPDP_CONSENT_ENFORCED` (default `true`) + `consent_bypassed` computed property; the bypass
  takes effect at the single `_consent_granted` chokepoint (covers `RequireConsent` /
  `consent_granted` / `assert_consent`) ONLY in an allowlisted `development/test/ci` ENV.
- Setting it `false` in any other ENV is a **hard boot failure** (`config.model_post_init`) —
  a leaked override cannot disable consent in prod/staging. One startup warning when active.
- Dev `.env` set to `false`; `.env.example` documents the knob (default `true`).
- Independent Security review (Sonnet takeover; codex n/a) ACCEPT-WITH-CONDITIONS — env-allowlist
  invert + boot guard both applied in-session. 28 consent unit tests; runtime proofs captured
  (dev bypass active, prod boot-crash). Ledger `reviews/b48-consent-killswitch.md`; **B48 filed (OPEN —
  must re-enable before launch)**. Auth (anonymous→401) is untouched; only consent is relaxed.

## Launch-gate blocker hardening (2026-06-07, branch `hardening/launch-gate-blockers`)

Multi-slice load-bearing blocker work, one slice per commit, each with full inline Tier-B/C review
plus an independent adversarial sign-off (Sonnet takeover — codex unavailable on this account):

- **Slice 1 — B26 Admin endpoints** (`c365fca`): admin router (`dhanradar/admin/`, `RequireAdmin()`
  → 404 to non-admins) — disclaimer create + activate (single-active transition → R2 HTML snapshot →
  cache flush; concurrent loser → 409) + label-churn gate (reuses `governance.review_batch`). Alembic
  0008: `rating_engine_changelog` + `ai_low_confidence_log` (no writer yet) + `uq_disclaimer_active_per_type`
  partial-unique index. Adversarial ACCEPT-WITH-CONDITIONS — content bound, churn-type allowlist
  (fail-open fix), atomic single-active index — all applied in-session. Ledger `reviews/b26-admin-endpoints.md`.
- **Slice 2 — B6/B28 scoring-activation gate** (`35cace1`, ADR-0026): admin-triggered, DB-registry-
  authoritative two-person (`approved_by≠created_by`) + backtest gate; `compliance.rating_engine_changelog`
  is the authoritative runtime state; the engine sync `score()` keeps the JSON file-flag fallback so v1
  stays provisional. Alembic 0009: `uq_engine_changelog_activated_per_version` index. Adversarial
  ACCEPT-WITH-CONDITIONS — UUID `created_by` guard, the index + 409, `provisional`=registry — all
  applied. Ledger `reviews/b6-b28-scoring-activation.md`.
- **Slice 3 — B2/B7/B8 Razorpay** (`9d0016c`): DEFERRED data-only (no code) — re-verified the billing
  fail-safes (checkout 503 + `_derive_tier` free-on-unmapped) and documented exactly what to seed when
  the Razorpay dashboard exists. `BLOCKERS.md`.

Gates each slice: pytest (unit green, integration collects — run in CI per B1), `ci_guards.py` 0,
`py_compile` 0, markdownlint 0. **B26 admin / B6 / B28 mechanisms now BUILT;** remaining for B6/B28 is
the production activation of v1 (real §8 backtest + human approver), a data/human gate.

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
  B18/B2 + **B48** (re-enforce DPDP consent: `ENV=production` and/or `DPDP_CONSENT_ENFORCED=true`,
  then verify a gated route 403s without a grant) + live-stack runtime proofs + PC4/PC5 human approval).

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
  activation), **B18** (atomic AI budget), **B2/B7/B8** (Razorpay data-seeding), **B48** (re-enforce
  the DPDP consent gate — set `ENV=production` and/or `DPDP_CONSENT_ENFORCED=true`, then verify a
  consent-gated route 403s without a grant) + the live-stack runtime proofs + separate human approval (PC4/PC5).
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

### B38 observability + deploy-gate checklist (2026-06-07, branch `hardening/launch-gate-blockers`)

User drove toward a full deploy; I built the one CRITICAL ops gate in my lane and held the line on
the hard gates.

- **B38 monitoring — DONE & pushed** (`efc6556`): `dhanradar/observability.py` — `init_sentry()`
  (DPDP-safe `before_send` scrubber: cookies / auth+cookie+internal-token headers (dict AND list) /
  body / query_string / env-`REMOTE_ADDR` / breadcrumbs / user; `send_default_pii=False`, traces off);
  plus a Prometheus `/metrics` endpoint (method/route-TEMPLATE/status labels only — no raw paths/ids;
  outside `/api/v1`, network-isolated, no bearer per non-neg #5). 24 DB-free tests.
- **Deploy-gate checklist created**: `docs/project-state/DEPLOY_GATE_CHECKLIST.md` — 7 gate groups +
  owner tags; the single path from this branch → a legitimate KVM4 deploy. B38 ticked (`67d5915`).
- **B36 / B37 NOT done** — both need KVM4 box access (tested migration round-trip; backups verified
  India-resident) that this session does not have; only draftable untested. Needs a box session.
- **DEPLOY refused** — open Compliance BLOCKERs + unsigned audit + no backups/consent-UI/residency +
  PC5 human approval. **MERGE refused** — `main` is PR-protected, needs the audit, and the branch
  carries the concurrent session's load-bearing work. Owner consent does not waive legal (DPDP) /
  integrity (two-person) / data / infra gates.
- **Opus** — orchestration, infra-notes grounding, line-by-line review, the ci_guards/bearer
  resolution, gating/commit/push. **Sonnet ×2** — B38 builder (reworked **Y**: adversarial round) +
  adversarial reviewer (found **4 real DPDP PII leaks** the build missed — high value). **Haiku** —
  n/a. **codex:rescue** — n/a (unavailable; Sonnet adversarial takeover per the approved ladder).
- Gates: pytest 24 · ruff 0 · ci_guards 0 · anti-pattern 9/9 · markdownlint 0. Commits `efc6556`,
  `67d5915` (latter has a cosmetic stray `@` in its message — bash/PowerShell heredoc mixup; not
  force-fixing on a shared branch).

### DPDP consent kill-switch B48 (2026-06-07, branch `hardening/launch-gate-blockers`)

- **Opus** — Phase-0 status read; the kill-switch design (single `_consent_granted` chokepoint,
  env-allowlist, boot guard); both edits (config.py / deps.py) hand-written (load-bearing
  compliance path + small/hot-cache); the two adversarial-condition fixes (env allowlist invert,
  `model_post_init` boot guard); the test additions; runtime proofs; B48 + the review ledger +
  this footer.
- **Sonnet** — 1 independent adversarial Security/Compliance sign-off (7 vectors; codex n/a →
  takeover) → ACCEPT-WITH-CONDITIONS, both required conditions applied before commit.
- **Haiku** — n/a (targeted greps run inline).
- **codex:rescue** — n/a — account not entitled for Codex models; Sonnet takeover per the approved
  fallback ladder.
- Per-delegation (telemetry): b48-adversarial · Sonnet · reworked N (verdict + 3 conditions adopted
  as-found; Opus implemented the fixes). Doc prose (B48 row / ledger / this footer) Opus-direct under
  the load-bearing one-shot exemption (needed the precise adversarial-review context). Gates: 28
  consent unit tests green; 350 unit pass (2 pre-existing network failures unrelated); ci_guards +
  anti-pattern sweep PASS; markdownlint 0.

### Launch-gate blocker hardening (2026-06-07, branch `hardening/launch-gate-blockers`)

- **Opus** — Phase-0 warm reads (canonical docs + scoring/compliance code); orchestration; both build
  contracts; line-by-line Phase-3 diff review of every slice; ALL adversarial-condition fixes (slice 1:
  content bound + churn-type allowlist + single-active index; slice 2: UUID `created_by` guard +
  activation index + `provisional`=registry); both review ledgers; slice-3 fail-safe verification; the
  session-exit docs.
- **Sonnet** — 2 builders (slice-1 B26-admin endpoints; slice-2 B6/B28 activation) against exact
  contracts; 2 independent adversarial sign-offs (codex unavailable → Sonnet takeover); 1 doc-drafter
  (ADR-0026 + feature doc + BLOCKERS B6/B28).
- **Haiku** — n/a (no bulk grep/triage; targeted greps run inline).
- **codex:rescue** — n/a — companion lacks model entitlement; both Tier-B/C adversarial sign-offs run
  as independent Sonnet takeovers (slice 1 + slice 2 each ACCEPT-WITH-CONDITIONS), all conditions
  applied in-session before commit.
- Per-delegation (telemetry): slice1-builder · Sonnet · reworked: Y (Opus fixed a fail-open churn-type
  gap + added a content bound + the atomic single-active index from the adversarial pass) |
  slice1-adversarial · Sonnet · reworked: N | slice2-builder · Sonnet · reworked: Y (Opus added the
  UUID `created_by` guard, the activation partial-unique index + IntegrityError→409, and
  `provisional`=registry) | slice2-adversarial · Sonnet · reworked: N | slice2-docs-drafter · Sonnet ·
  reworked: N (ADR/feature/BLOCKERS applied as-drafted). Two review ledgers + this footer were
  Opus-direct (needed the adversarial-review context / precise telemetry; one-shot exemption).

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
