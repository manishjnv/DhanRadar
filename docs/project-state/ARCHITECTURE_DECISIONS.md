# DhanRadar — Architecture Decision Record (ADR) Log

Append-only log of **major** architectural/governance decisions. Standing rule: a decision that
changes a contract, a stack choice, a security/compliance posture, or the operating model gets an
ADR entry here. New entries at the bottom; never rewrite history — supersede with a new ADR and
flip the old one's status to `Superseded by ADR-NNNN`.

**Entry format:** ID · title · date · status · context · decision · consequences · source.
**Status values:** Accepted · Superseded · Proposed · Deprecated.

## Index

| ID | Title | Status |
|---|---|---|
| ADR-0001 | Authority order for source-of-truth conflicts | Accepted |
| ADR-0002 | `docs/ui-system/` is harvest-not-adopt | Accepted |
| ADR-0003 | Design tokens: Geist/warm canonical; retire Manrope/cool (D1) | Accepted |
| ADR-0004 | Auth: RS256 JWT in `__Host-` HttpOnly cookies; no bearer (P2) | Accepted |
| ADR-0005 | API base path `/api/v1`; RFC7807 errors (P1, D3) | Accepted |
| ADR-0006 | Search: Postgres FTS + `pg_trgm`; no Elasticsearch (S1) | Accepted |
| ADR-0007 | Database: TimescaleDB required; schema-per-concern; module-isolated tables | Accepted |
| ADR-0008 | Email: Resend (not SendGrid/SES) | Accepted |
| ADR-0009 | LLM access: governed OpenRouter gateway + budget governor | Accepted |
| ADR-0010 | SEBI educational boundary: non-advisory labels; no numeric in DOM | Accepted |
| ADR-0011 | Scoring: 5-axis with Trend (Growth nested), not Growth (REC-D1) | Accepted |
| ADR-0012 | Confidence: internal 0–1, launch band-only (REC-D2) | Accepted |
| ADR-0013 | Risk profile: architecture thresholds/states; excluded from score (REC-D3) | Accepted |
| ADR-0014 | Signup: password-immediate; OTP-first preserved-not-activated (D2) | Accepted |
| ADR-0015 | Billing: `plans` catalog as additive backward-compatible migration (D4) | Accepted |
| ADR-0016 | Launch sequencing: MF-first | Accepted |
| ADR-0017 | Infra: KVM4 shared-infra + dedicated cloudflared tunnel; 8 containers; no host ports | Accepted |
| ADR-0018 | Operating model: multi-agent tiered governance (A/B/C) | Accepted |
| ADR-0019 | Scoring Engine Authority: FINAL_SCORING_SPEC.md is the sole source of truth | Accepted |

---

## ADR-0001 — Authority order for source-of-truth conflicts

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** three sources in tension — architecture-of-record, existing code, and the
independently produced `docs/ui-system/` kit.
**Decision:** binding order is `DhanRadar_Architecture_Final.md` → `DhanRadar_Implementation_Plan.md`
→ existing code → `docs/features` → `docs/ui-system` → mockups.
**Consequences:** every alignment doc resolves conflicts by this order; ui-system loses on
framing/stack/auth/tokens.
**Source:** `REPOSITORY_ALIGNMENT_REPORT.md`, all `project-state/*` headers.

## ADR-0002 — `docs/ui-system/` is harvest-not-adopt

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** ui-system has its own OpenAPI, schema, stack, and tokens, and is internally
self-contradictory (brand vs design-system).
**Decision:** harvest specific value (RFC7807, richer auth tables, `src/` feature-slice structure,
CI) per `MIGRATION_STRATEGY_FINAL.md` KEEP/MERGE/REPLACE/IGNORE; never adopt wholesale.
**Consequences:** ui-system assets are repathed/retokenized/relabelled before use.
**Source:** `REPOSITORY_ALIGNMENT_REPORT.md`, `MIGRATION_STRATEGY_FINAL.md`.

## ADR-0003 — Design tokens: Geist/warm canonical; retire Manrope/cool (D1)

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** ui-system ships three token sets under one `--dr-*` prefix resolving to different
fonts/hexes; the repo already adopted brand/Geist/warm and memory enforces it.
**Decision:** brand (Geist Sans/Mono + Instrument Serif, warm palette, keys `royal`/`ink-secondary`)
is the single source of truth; `design-system/` + `tokens/` (Manrope/cool) are retired;
components/screens/figma are retokenized to brand.
**Consequences:** `agent.md` re-pointed; ui-package components won't compile until retokenized.
**Source:** `CANONICAL_DESIGN_SYSTEM_ALIGNMENT.md`.

## ADR-0004 — Auth: RS256 JWT in `__Host-` HttpOnly cookies; no bearer (P2)

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** ui-system specifies bearer-header auth; existing code implements cookie auth, already
security-reviewed.
**Decision:** RS256 JWT in `__Host-access`/`__Host-refresh` HttpOnly+Secure cookies; refresh =
rotation + reuse detection (atomic `GETDEL`); rate-limit keyed by `CF-Connecting-IP`. Bearer auth
rejected.
**Consequences:** OpenAPI security scheme = cookie; frontend uses `credentials: 'include'`.
Security-adjacent → Tier B reviews.
**Source:** `CANONICAL_OPENAPI_ALIGNMENT.md` §2, `docs/features/auth.md`.

## ADR-0005 — API base path `/api/v1`; RFC7807 errors (P1, D3)

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** ui-system uses `/v1`; the cloudflared ingress only routes `^/api/.*` to FastAPI.
**Decision:** every endpoint under `/api/v1`; error bodies are RFC7807 problem+json with a stable
`type` taxonomy + `request_id`; `Idempotency-Key` on mutating/payment routes; tier-gate = 402.
**Consequences:** regenerate `openapi.yaml` to `/api/v1`; add a global RFC7807 handler +
request-id middleware (Stage 2 Step 5, Tier B).
**Source:** `CANONICAL_OPENAPI_ALIGNMENT.md` §1/§4.

## ADR-0006 — Search: Postgres FTS + `pg_trgm`; no Elasticsearch (S1)

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** ui-system requires Elasticsearch 8; KVM4 RAM budget (~3 GB) assumes none.
**Decision:** full-text/typeahead via Postgres `GIN tsvector` + `pg_trgm`; no ES container/dep/env.
**Consequences:** screener/search re-spec'd on Postgres; ES is an IGNORE-list grep guard.
**Source:** `REPOSITORY_ALIGNMENT_REPORT.md` S1, `MIGRATION_STRATEGY_FINAL.md`.

## ADR-0007 — Database: TimescaleDB required; schema-per-concern; module-isolated tables

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** time-series (NAV/price history) needs hypertables; architecture mandates module
decoupling.
**Decision:** `timescale/timescaledb-ha:pg16`; schema-per-concern (no flat `public`); per-module
tables (`mf_funds`, `etf_metadata`, `stocks`) — the ui-system unified physical `instruments`/flat
`scores` table is rejected (usable only as a serializer read-shape).
**Consequences:** UI-package tables are imported schema-qualified; no shared mutable cross-module
tables.
**Source:** `REPOSITORY_ALIGNMENT_REPORT.md` N5/S2/D-DM3, architecture §B5.

## ADR-0008 — Email: Resend (not SendGrid/SES)

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** SendGrid free tier retired 2025-05-27; ui-system assumes AWS SES.
**Decision:** Resend (`re_…` sending key); domain verified; Phase-6 gate cleared.
**Consequences:** map SES→Resend in any ui-system config; the email client must send a real
User-Agent (Cloudflare blocks `Python-urllib`).
**Source:** Implementation Plan §0.1#1, `infra-notes.md`.

## ADR-0009 — LLM access: governed OpenRouter gateway + budget governor

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** ui-system assumes a generic `LLM_API_KEY`/`LLM_BASE_URL` with no cost governance.
**Decision:** `OpenRouterGateway` with free-pool round-robin → Sonnet spillover + `budget_guard()`
hard/soft caps; generic LLM env vars rejected.
**Consequences:** AI surfaces consume the governed gateway; 402 = balance (not a retry) vs 429 =
rate-limit.
**Source:** architecture §B3, `REPOSITORY_ALIGNMENT_REPORT.md` S4.

## ADR-0010 — SEBI educational boundary: non-advisory labels; no numeric in DOM

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** ui-system uses advisory `strong_buy/buy/hold/caution/avoid` and ships raw numeric
score/factors/fair-value to the client — a legal violation, not a style choice.
**Decision:** labels are `in_form/on_track/off_track/out_of_form/insufficient_data`, derived from a
deterministic rule table (not a pure function of the score); numeric score / factor weights /
fair-value never reach the DOM (public = label + confidence band); every score/label/AI surface
renders the disclosure bundle + `NOT_ADVICE`.
**Consequences:** hard blocker on any UI build until relabelled/regated; CI grep guard on advisory
verbs; Compliance Review mandatory (Tiers B and C).
**Source:** `REPOSITORY_ALIGNMENT_REPORT.md` A1/A2, `FINAL_SCORING_SPEC.md` §4, architecture §C/§S.

## ADR-0011 — Scoring: 5-axis with Trend (Growth nested), not Growth (REC-D1)

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** architecture axis = Trend; ui-system = Growth.
**Decision:** keep 5-axis Quality/Valuation/Momentum/Risk/**Trend**; Growth is sub-factors inside
Trend; Trend inherits the 0.22 weight; Momentum stays pure price/technical; earnings-revision +
relative-strength move to Trend (single-axis, test-enforced no double-count).
**Consequences:** `factors` API key set frozen = `quality/valuation/momentum/risk/trend`.
**Source:** `FINAL_SCORING_SPEC.md` §2.4/§3, `RECOMMENDATION_ENGINE_ALIGNMENT.md` F3.

## ADR-0012 — Confidence: internal 0–1, launch band-only (REC-D2)

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** architecture thresholds are 0–1 (0.30 floor, 0.70 high); ui-system uses 0–100.
**Decision:** compute on 0–1; display % only when the calibration reliability-curve is within ±10%;
launch shows band only (`high/medium/low`); `<0.30 → insufficient_data` (refuse).
**Consequences:** no numeric % in responses until the backtest calibration gate opens.
**Source:** `FINAL_SCORING_SPEC.md` §5.

## ADR-0013 — Risk profile: architecture thresholds/states; excluded from score (REC-D3)

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** suitability profiling must never personalize the score (research/advisory separation).
**Decision:** states `conservative/moderate/aggressive/not_set`; reuse the ui-system 8-question
instrument re-scaled onto the 0–100 architecture range; sole writer = Onboarding; **excluded from
all scoring-engine inputs** (test-enforced).
**Consequences:** risk profile drives content-suitability/education only.
**Source:** `FINAL_SCORING_SPEC.md` §6.2.

## ADR-0014 — Signup: password-immediate; OTP-first preserved-not-activated (D2)

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** existing flow is password-immediate; ui-system is 202+OTP (needs an SMS provider).
**Decision:** keep password-immediate for MVP; preserve the ui-system `otp_codes` schema + docs as
a future additive phase; do not wire OTP.
**Consequences:** OTP screens dropped from the launch surface; cookie issuance unchanged.
**Source:** `CANONICAL_OPENAPI_ALIGNMENT.md` §2, `REPOSITORY_ALIGNMENT_REPORT.md` P3.

## ADR-0015 — Billing: `plans` catalog as additive backward-compatible migration (D4)

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** ui-system has a `plans` catalog + `plan_id` FK; existing uses `subscriptions.plan`
TEXT.
**Decision:** add `billing.plans` + a nullable `subscriptions.plan_id` FK alongside the existing
`plan` TEXT (no drop during transition); webhook still writes `plan` (and `plan_id` when
resolvable).
**Consequences:** reversible migration on a payment-linked table; Tier B (Security + Compliance).
**Source:** `STAGE2_EXECUTION_PLAN.md` Step 6, `MIGRATION_STRATEGY_FINAL.md` §4.

## ADR-0016 — Launch sequencing: MF-first

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** ui-system screens are stock-centric; architecture launch wedge is the MF CAS→60s
report.
**Decision:** build in architecture phase order — MF detail + CAS upload + 60s report first;
stocks/ETFs follow. Create the missing CAS-upload/job-status/MF-report screens in-system.
**Consequences:** screen build order follows phases, not the ui-system stock-first set.
**Source:** `REPOSITORY_ALIGNMENT_REPORT.md` A4, Implementation Plan Phase 5.

## ADR-0017 — Infra: KVM4 shared-infra + dedicated cloudflared tunnel; 8 containers; no host ports

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** deploy target is a shared KVM4 box (~32 other containers); ui-system compose publishes
host ports + bundles ES on a greenfield host.
**Decision:** 8 own internal containers, no host port bindings, dedicated `dhanradar` cloudflared
tunnel as sole ingress; reuse `shared_prometheus`/`shared_grafana`; honor the ❌ NEVER-TOUCH list + 3
cloudflared gotchas; ui-system's port-publishing/ES compose ignored.
**Consequences:** local testing via `docker-compose.override.yml`; deploy is security-relevant +
gated.
**Source:** `infra-notes.md`, `REPOSITORY_ALIGNMENT_REPORT.md` I1.

## ADR-0018 — Operating model: multi-agent tiered governance (A/B/C)

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** Claude Code acted as builder + planner only; the operating review found no compliance
gate, no independent reviewer, and no enforced gates for a SEBI-boundary product.
**Decision:** Claude Code acts as Builder + Architect + Security + Compliance + UI + Product
reviewer; which reviews run is set by a 3-tier model (A: +UI · B: +Security+Compliance · C:
+Compliance+Product; Builder + Architect always); reviewers are independent agents; all output for
one change lives in `docs/project-state/reviews/<change-id>.md`. The two-person scoring methodology
gate is documented but non-blocking until production activation (BLOCKERS B6).
**Consequences:** no major change is "done" until its tier's reviews pass + the ledger is signed
off; security/compliance gates fail-closed.
**Source:** `AI_GOVERNANCE_MODEL.md`, `CLAUDE.md` overlay.

## ADR-0019 — Scoring Engine Authority: FINAL_SCORING_SPEC.md is the sole source of truth

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** scoring rules were spread across architecture §S, `RECOMMENDATION_ENGINE_ALIGNMENT.md`,
`docs/ui-system/recommendation-engine/*`, and `contracts/score-model.md`, creating ambiguity about
which governs the factor/weight/confidence/risk/label/threshold/governance models.
**Decision:** `docs/project-state/FINAL_SCORING_SPEC.md` is the **sole source of truth** for the
**rating/scoring engine**. It consolidates all eight model areas, is consistent with and
reproduces architecture §S's hard governance rules (which remain the originating authority), and
**supersedes** the alignment doc + the ui-system engine docs + `docs/ui-system/contracts/score-model.md`
for all purposes. On a scoring conflict between sibling docs, FINAL_SCORING_SPEC wins; on conflict with §S
hard rules, §S wins and the spec is corrected.
**Consequences:** any scoring change updates FINAL_SCORING_SPEC and adds an ADR if it changes a
FINAL element; sibling docs carry a "superseded" pointer; Tier-C reviews cite this doc. Numeric
weights stay PROPOSED v1 pending backtest pass-gates + the two-person methodology gate (B6,
non-blocking until production activation). This clears `STAGE2_EXECUTION_PLAN` pre-condition **PC6**.
**Source:** `FINAL_SCORING_SPEC.md` §0, `AI_GOVERNANCE_MODEL.md` (Tier C), `STAGE2_EXECUTION_PLAN.md`.
