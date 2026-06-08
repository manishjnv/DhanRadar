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
| ADR-0020 | Concentration: catalogued-but-unweighted risk sub-factor in scoring v1 (B11) | Accepted |
| ADR-0024 | DPDP cross-border consent: per-processor purposes + fail-closed non-route gate (B20/B31) | Accepted |
| ADR-0025 | AMFI historical NAV report as the canonical backfill source for MF return signals (B29) | Accepted |
| ADR-0026 | Scoring-engine activation: admin-triggered, DB-registry-authoritative two-person + backtest gate (B6/B28) | Accepted |
| ADR-0027 | First AI-gateway consumer = MF report portfolio commentary; complete() returns CompletionResult(output, model_used) | Accepted |
| ADR-0028 | Centralised structured logging (P1): structlog JSON + request_id correlation + Docker json-file rotation + compliance redaction | Accepted |

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
is the single source of truth; `design-system/` + `tokens/` (Manrope/cool) are retired (deleted 2026-06-06; `frontend/` is canonical);
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

## ADR-0020 — Concentration is a catalogued-but-unweighted risk sub-factor in scoring v1 (B11)

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** `FINAL_SCORING_SPEC` §2.5 lists 7 RISK sub-factors including Concentration
(segment/customer), but the §6.1 v1 formula weights only 6 (the six already sum to 1.0), leaving
concentration orphaned — an internal inconsistency flagged as BLOCKERS B11. Concentration data
(segment-revenue / customer-concentration disclosures) is hard to source reliably across the MF-first
launch wedge and the broad Indian retail universe.
**Decision:** Reconcile by treating §2.5 `axes.risk` as the **factor catalog** and the §6.1 weight
map as the **activated subset**. Concentration stays catalogued but **unweighted in v1** — an
intentional deferral, not a contradiction. It is a **v2 candidate**: a weight is assigned only once a
reliable data source + its sector normalization exist, and is then set at the backtest pass-gate under
the two-person methodology gate (B6). No v1 weight changes; the engine's behaviour is unchanged (it
already treats concentration as unweighted). The config validator already permits a catalogued-but-
unweighted sub-factor.
**Consequences:** B11 is resolved as documentation (no weight re-derivation, no backtest re-run now);
§2.5/§6.1 carry cross-pointers; `ranking_configs_v1.json._concentration_note` records the resolution.
Adding concentration in v2 is a FINAL-element change → new ADR + Tier-C review + B6 gate at that time.
**Source:** `FINAL_SCORING_SPEC.md` §2.5/§6.1, `BLOCKERS.md` B11, ADR-0019.

## ADR-0021 — Notification delivery uses a 1-minute Celery-beat LPOP drain, not a long-running BLPOP consumer (Phase 6)

**Date:** 2026-06-06 · **Status:** Accepted
**Context:** Architecture Global §5 specifies "`celery-misc` BLPOPs" the
`notifications:queue:{channel}` Redis lists. A blocking `BLPOP` needs a bespoke
long-running consumer process; the DhanRadar stack already runs Celery workers +
beat and routes tasks through the broker — there is no dedicated consumer process
in the compose stack, and adding one is extra surface for a low-volume educational
alert channel.
**Decision:** `publish_notification` still LPUSHes the documented job onto
`notifications:queue:{telegram,email}` (the interface is unchanged). A
beat-scheduled `dhanradar.tasks.misc.drain_notifications` task runs **every minute**
and drains each channel with a bounded `RPOP` loop (FIFO with the LPUSH publisher),
applying quiet-hours + per-channel daily rate caps, rendering the label-only
disclosure-injected template, delivering via the channel transport, logging, and
re-queuing transient failures up to the per-channel cap. Each tick is bounded to the
pre-loop queue length so re-queued jobs are not re-processed the same tick (loop-safe).
**Consequences:** delivery latency is ≤ ~1 minute (acceptable for educational
alerts; not a real-time/transactional channel). No bespoke consumer process to
operate or supervise. The drain must run on a **single** beat worker (or with a
Redis lock / `acks_late`) to keep the non-atomic rate-cap counter exact — tracked as
**B32**; a Redis Lua counter is the path before multi-worker scale. If a
sub-minute SLA is ever required, swap the beat drain for a dedicated BLPOP consumer
without changing the publisher interface.
**Source:** `docs/DhanRadar_Architecture_Final.md` §5; `docs/DhanRadar_Implementation_Plan.md`
Phase 6; `BLOCKERS.md` B32; `reviews/phase6-notification.md`.

## ADR-0022 — `ai_recommendation_audit`: never-lose-a-row design + 7-yr `user_id` retention survives DPDP erasure (B26)

**Date:** 2026-06-06 · **Status:** Accepted
**Context:** §4 requires an immutable 7-yr SEBI audit tying every served label to the
in-force disclaimer version. Two tensions: (a) a fire-and-forget audit write must NEVER
be lost (a missing partition or a referential hiccup dropping a compliance row is worse
than the elegance of strict FKs); (b) SEBI 7-yr recordkeeping conflicts with the DPDP
right to erasure — the audit must identify who was served what, yet the user may request
deletion.
**Decision:** (1) **Never-lose-a-row:** the table is RANGE-partitioned monthly on
`served_at` with a **DEFAULT partition** so an insert always lands even before monthly
partitions exist; `disclaimer_version` is a denormalized NOT-NULL text (NOT a hard FK) and
`user_id` has NO FK — so a write never fails on a referential miss. (2) **Retention vs
erasure:** `user_id` (no FK/CASCADE) means the audit OUTLIVES a user erasure; the legal
basis is the **SEBI recordkeeping obligation**, which overrides DPDP erasure for this table
only. The erasure module MUST skip `compliance.ai_recommendation_audit` and log the
override with this basis. (3) **recommendation_type** is a POSITIVE allowlist (DB CHECK +
service) — only educational types may be audited as served (non-neg #1). (4) The R2 archive
keeps `user_id` (it is the 7-yr record-of-serving and must stay user-identifiable); the
control on cross-border PII is **R2 bucket India-residency** (B34), not de-identification.
**Consequences:** a `user_id` (DPDP personal data) is retained 7 years post-erasure — an
intentional, documented exception, not a leak. Adding a new auditable `recommendation_type`
is a deliberate migration (controlled vocabulary). A reconcile job asserting every
`disclaimer_version` exists in `disclaimers` is owed (denormalized value could drift).
**Source:** `docs/DhanRadar_Architecture_Final.md` §4; `BLOCKERS.md` B26/B34;
`reviews/b26-compliance-audit.md`; `docs/features/compliance-audit.md`.

## ADR-0023 — Mood Compass public surface is regime + band (no numeric), and a sub-0.30-confidence regime refuses to `insufficient_data`

**Date:** 2026-06-06 · **Status:** Accepted
**Context:** Mood Compass computes a 0–100 market-regime score. The genre (CNN Fear &
Greed) makes the NUMBER the viral hook. But non-neg #2 forbids any numeric score on a
client surface, and a public "60 = greed" number invites the "60 → buy" reading the
SEBI educational boundary forbids. Separately, a regime computed from a few low-weight
signals (e.g. only `news_sentiment`, weight 0.06) would otherwise broadcast a confident
directional bucket at near-zero confidence.
**Decision:** (1) The public surface exposes the **regime bucket + confidence band +
commentary + evidence only**; the 0–100 `mood_score` and the confidence float stay
**server-side** (`market_mood` columns) and never serialize to a client (non-neg #2).
A future "is it getting worse?" hook must be a NON-numeric directional field (e.g.
`trend: rising|falling|stable` from comparing the last two rows), not the number. (2) The
refuse floor (non-neg #4) degrades the **label, not just the band**: when confidence
< 0.30 the served `regime` is coerced to `insufficient_data` (mirroring the rating
engine), so a degraded snapshot cannot over-claim a directional regime. (3) Free-text AI
commentary is advisory-screened before publish (non-neg #1).
**Consequences:** Mood deliberately diverges from the Fear&Greed convention — it loses the
shareable number but stays inside the educational boundary. Compliance confirmed a public
number would be a BLOCKER. The directional-trend enhancement is tracked (B35). The 0–100
remains available server-side for internal/event consumers (AI-Enrichment analogues).
**Source:** `docs/DhanRadar_Architecture_Final.md` Mood Compass §; CLAUDE.md non-neg #2/#4;
`BLOCKERS.md` B35; `reviews/mood-compass.md`; `docs/features/mood-compass.md`.

## ADR-0024 — DPDP cross-border consent: per-processor purposes + fail-closed non-route gate (B20/B31)

**Date:** 2026-06-05 · **Status:** Accepted
**Context:** transferring user personal data OUTSIDE India — the AI gateway → OpenRouter (B20) and
the notification deliver seam → Telegram + Resend-Tokyo (B31) — is a DPDP cross-border concern
distinct from the per-feature *processing* purposes. The seams had no cross-border consent gate
(two MAJOR deploy-gates), and `RequireConsent` is a FastAPI route dependency unusable from Celery
workers / internal seams.
**Decision:** (a) add **per-processor** cross-border purposes — `cross_border_ai` (B20) +
`cross_border_notify` (B31) — NOT one bundled grant, honouring DPDP's specific-consent /
no-bundling principle (Compliance review). (b) add reusable, non-route
`consent_granted(user_id, purpose, db) -> bool` (skip semantics) and `assert_consent(...)` (raises
`ConsentRequiredError`) in `deps.py`, reusing the existing fail-closed `_consent_granted` reader,
read FRESH (no cache) so a revoke is honoured immediately. The gate is enforced at the CALL SITE
(the gateway cannot know the user).
**Consequences:** B20/B31 wiring (consuming-module PRs) must call the gate and prove "no grant →
egress client never invoked." Until the Consent-module grant/revoke WRITER exists (non-neg #10,
still a stub), every user fails closed → the cross-border seams are inert for real users, which is
safe. Revoke contract: the writer MUST set `granted:false` / remove the key, never add a separate
`revoked` key (documented in `_consent_granted`). The ADR index is currently behind (0021–0024
un-indexed beyond this addition; reconcile separately).
**Source:** `backend/dhanradar/deps.py`; `reviews/consent-cross-border-primitive.md`;
`docs/DhanRadar_Architecture_Final.md` §Compliance; CLAUDE.md non-neg #10; ADR-0022 (R2 residency).

## ADR-0025 — AMFI historical NAV report is the canonical backfill source for MF return signals (B29)

**Date:** 2026-06-07 · **Status:** Accepted
**Context:** Producing real (still provisional) MF labels needs 1Y/3Y category-relative return
signals, which need NAV **history**. The verified Allowed-APIs block covered only `NAVAll.txt`
(today's NAV). A backfill source was required; the options were the official AMFI historical NAV
report, a third-party aggregator (e.g. `mfapi.in`), or accrue-forward-only (no backfill, labels
stay `insufficient_data` for 1–3 years). Introducing an external API requires an architecture-owner
decision + an Allowed-APIs entry (the "never invent an external API" rule).
**Decision:** Use the **official AMFI historical NAV report**
(`GET portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?frmdt=&todt=`) as the canonical
backfill source — the **same official, free, India-resident** source as the daily feed; **no
third-party NAV vendor is introduced.** Live-verified 2026-06-07. It is semicolon-delimited but
**8-field with a different column order** than `NAVAll.txt`, so it gets a separate parser
(`parse_nav_history`); AMFI caps each request to ~3 months, so a multi-year backfill loops over
non-overlapping windows. Added to the Implementation Plan §0 Allowed-APIs block.
**Consequences:** the MF data pipeline (B29) can compute return-based signals — Momentum (category
rank), Trend (rolling-return trajectory), Risk (volatility/drawdown), partial Quality, and the
`outperform_1y/3y` / `drawdown_controlled` label signals — per `FINAL_SCORING_SPEC` §2.6/§4.1/§8.
**Valuation stays uncomputed** (needs an expense-ratio feed) and `structural_concern`/`manager_change`
stay False (no qualitative feed) → coverage ~3/5 → confidence caps at `medium`, and every result keeps
the **`provisional_model`** flag because the weights are `activated:false` (B28) pending the backtest
pass-gates + two-person methodology gate (B6). The signal-derivation **thresholds are provisional and
config-gated, not frozen methodology** — finalizing them is a FINAL-element calibration → B6 gate
before any numeric is treated as authoritative. DPDP-clean: public NAV data, no PII, India-resident.
**Source:** Implementation Plan §0 Allowed-APIs ("AMFI NAV — historical"); `FINAL_SCORING_SPEC`
§2.6/§4.1/§8; `BLOCKERS.md` B29/B28/B6; `GROWTH_BACKLOG.md` Tier-0; `reviews/independent-audit-2026-06-06.md`.

## ADR-0026 — Scoring-engine activation: admin-triggered, DB-registry-authoritative two-person + backtest gate (B6/B28)

**Date:** 2026-06-07 · **Status:** Accepted

**Context:** `ranking_configs_v1.json` carries `activated:false` and every result is tagged
`provisional_model`. ADR-0018/ADR-0019 document the two-person methodology gate (`approved_by ≠
created_by`) and the §8 backtest pass-gates as pre-conditions for treating any numeric as
authoritative. No enforcement mechanism existed: the gate was a written rule without a runtime
trigger or a durable activation state. Three implementation approaches were evaluated.

- **Option A — Admin endpoint + DB registry (chosen):** a `POST /api/v1/admin/scoring/{version}/activate`
  endpoint (`RequireAdmin()` → surface-hiding 404 for non-admins) writes a row to
  `compliance.rating_engine_changelog` with `activated=true`. The registry row is the authoritative
  runtime activation state; the endpoint is the only activation trigger.
- **Option B — Ops-script service function (rejected):** a pure Python function callable only from a
  CLI script; no HTTP trigger, smaller attack surface, but no operator UI action and no audit trail
  in the compliance table.
- **Option C — Gated CLI flips `activated:true` in the JSON (rejected):** simplest engine path, but
  activation requires a redeploy, and the "state" is a file edit with no immutable audit row.

**Decision:** Option A. The `compliance.rating_engine_changelog` table is the **authoritative
runtime activation state** for a scoring `model_version`. A version is "activated" iff it has a
changelog row with `activated=true`. Activation is gated by
`scoring/engine/activation.py:assert_activatable`, which enforces fail-early:

1. `backtest_passed` must be `true` (the §8 backtest pass-gates, asserted by the operator) — else
   422 `backtest_not_passed`.
2. `approved_by ≠ created_by` two-person gate (reuses `governance.two_person_gate_ok`) — else 409
   `two_person_gate_failed`. `created_by` is the authoring ROLE from `ranking_configs_v1.json`
   (`"architecture-review"`); `approved_by` is the activating admin's UUID. `EngineConfig.validate()`
   rejects a UUID-shaped `created_by` to prevent trivial/deceptive satisfaction of the gate.

On success, one `rating_engine_changelog` row is written via `compliance.service.record_engine_changelog`
(interface-only coupling; scoring never imports the compliance ORM model). A
`uq_engine_changelog_activated_per_version` partial-unique index (migration 0009) is the
multi-worker race-safe backstop against double-activation (409 `model_already_activated`).

The engine's synchronous `score()` path is **unchanged** — it reads `cfg.activated` from the JSON
file flag as a "no DB session" fallback (`provisional_model` tag). Surfaces with a DB session call
`activation.is_activated(db, model_version)` (positive-memoized via a process-global set; activation
is monotonic). `GET /api/v1/admin/scoring/{version}/status` reports `file_activated`,
`registry_activated`, `effective_activated` (file OR registry), and `provisional` (NOT
`registry_activated` — the registry gate governs provisional determination, not the file flag).

**v1 stays provisional**: no backtest has been run, so v1 is not activated. The mechanism is built
and ready; actual v1 activation still requires real §8 backtest pass-gates (human/data) and a human
approver admin whose UUID differs from the authoring role.

**Consequences:** runtime activation requires no redeploy. The compliance table carries an immutable
audit row for every activation event. The two-person gate is structurally enforced, not discipline-
dependent. The engine sync path retains the JSON-flag fallback so scoring is never blocked by a DB
session absence. Adding v1 activation is a data + human gate (backtest + admin action), not a code
change.

**Tier-C review:** independent adversarial review (Sonnet takeover; codex unavailable) —
ACCEPT-WITH-CONDITIONS; all 3 conditions applied in-session (UUID `created_by` validation;
partial-unique index + IntegrityError→409; `provisional` governed by registry). 7 unit + 7
integration tests; ci_guards green.

**Files:** `scoring/engine/activation.py` (new); `scoring/engine/config.py`; `compliance/service.py`;
`admin/router.py` + `admin/schemas.py`; `models/compliance.py`; `alembic/versions/0009_engine_activation_unique.py`.

**Source:** `BLOCKERS.md` B6/B28; `AI_GOVERNANCE_MODEL.md` §7.2; `FINAL_SCORING_SPEC.md` §8;
`docs/project-state/reviews/b6-b28-scoring-activation.md`.

## ADR-0027 — First AI-gateway consumer = MF report portfolio commentary; complete() returns CompletionResult(output, model_used)

**Date:** 2026-06-07 · **Status:** Accepted

**Context:** The governed OpenRouter gateway was built but had zero consumers; `complete()` returned
the bare `AIOutputBase` schema with no way to surface the winning model (B21). The first consumer
had to wire all four AI gates — B20 (DPDP cross-border consent), B21 (`model_used` audit), B22
(confidence floor), B23 (advisory screen) — plus the B26 third audit seam.

**Decision:** (a) The first consumer is MF report portfolio-level commentary
(`dhanradar/mf/commentary.py`, called from `tasks/mf.py::_run_pipeline` after scoring, before
report assembly). Mood Compass was the alternative but is anonymous — it cannot exercise B20's
`assert_consent("cross_border_ai")` (no user/PII) — and is inert in prod (signals stubbed). MF is
the launch wedge, live, carries real per-user PII, and is the only surface that genuinely wires all
four gates. Granularity is one portfolio-level LLM call per report (bounded budget); commentary is
non-blocking and omitted on any refusal/failure (architecture §MF line 257). (b) `complete()` now
returns a frozen `CompletionResult(output, model_used)` dataclass instead of the bare `AIOutputBase`,
so callers can record `model_used` into `ai_recommendation_audit` (B21). No production consumers
existed, so the blast radius was gateway tests only.

**Consequences:** B20/B21/B22 call sites wired and B26 third audit seam opened
(`surface=mf_commentary`, per HEAD's shipped `mf/commentary.py`). B23 gains a second
defense-in-depth net but its taxonomy stays open. Commentary is SEBI-disclaimer-postfixed.
Mood Compass is the trivial fast-follow (`contains_personal_data=False`). In prod, commentary
refuses until `cross_border_ai` consent capture lands — the correct fail-closed behaviour.

**Source:** `docs/project-state/reviews/ai-consumer-mf-commentary.md`; `BLOCKERS.md`
B20/B21/B22/B23/B26; `docs/DhanRadar_Architecture_Final.md` §MF line 257.

## ADR-0028 — Centralised structured logging (P1): structlog JSON + request_id correlation + Docker json-file rotation + compliance redaction

**Date:** 2026-06-08 · **Status:** Accepted

**Context:** The pre-P1 stack had ~19 stdlib `logging.getLogger()` call sites emitting
unstructured text, no cross-request correlation, no redaction, and no log rotation — a
compliance gap (DPDP/non-neg #10) and an operability gap on a shared box (KVM4, ~3 GB cap).
BLOCKERS B57 tracked the requirement. Four decisions required architecture-owner sign-off:
(a) whether to unify structlog and the existing stdlib callers under one chain or run two
parallel chains; (b) whether to introduce OpenTelemetry 16-byte W3C trace IDs or keep UUID4
`request_id`; (c) how to implement the two-layer PII/credential redaction filter required by
DPDP; (d) how to rotate Docker logs within the shared-box cap without adding external infra.

**Decision:**

(a) **structlog + stdlib unification via `ProcessorFormatter` + `foreign_pre_chain`.**
`configure_logging()` (`backend/dhanradar/core/logging.py`, stdlib-only imports plus structlog)
installs a single structlog processor chain and wires the same chain to the stdlib root handler
via structlog's `ProcessorFormatter`. Every existing `logging.getLogger()` call site emits the
same redacted JSON without modification. The chain is: `merge_contextvars` → `add_log_level`
→ `TimeStamper(iso,utc)` → `CallsiteParameterAdder` → `_redaction_processor` → `JSONRenderer`.
One JSON object per line to stdout. `configure_logging()` is idempotent; public API also exposes
`get_logger(name=None)` and `hash_user_ref(user_id) -> sha256(user_id)[:16]`.

(b) **Keep UUID4 `request_id` in P1; defer OpenTelemetry to P3.** UUID4 already exists in
`RequestIDMiddleware` (PURE ASGI — deliberately NOT `BaseHTTPMiddleware`, which breaks async
SQLAlchemy sessions). The middleware binds `request_id` as a contextvars key and clears it in a
`finally` block. `user_ref = hash_user_ref(user_id)` is bound in `deps.current_user_or_anonymous`
(auth resolves AFTER the pre-routing middleware), in the CAS worker pipeline, and is propagated
to Celery as a task kwarg and re-bound in `task_prerun`; cleared in `task_postrun`,
`task_failure`, and `task_revoked`. `request_id` is also threaded into `gateway.complete()`
and into the `ai_recommendation_audit` ledger write. W3C 16-byte trace IDs and a Grafana Loki
collector are deferred to P3 (no OpenTelemetry dependency introduced in P1).

(c) **Two-layer `_redaction_processor` (COMPLIANCE-CRITICAL, DPDP).** The processor runs
BEFORE `JSONRenderer` and applies: (1) KEY-based rules — user-id fields → SHA-256[:16] hash;
contact/PAN fields → `[REDACTED]`; credential/auth fields → `[REDACTED]`; API-key fields →
`[REDACTED:key]`; prompt/message fields → `[REDACTED:prompt]`; AI response fields →
`[REDACTED:response]`; binary/file fields and any `bytes` value → `[REDACTED]`. (2) VALUE-based
regex on every string and the event message: JWT (`eyJ…`), PAN, Indian mobile (`[6-9]\d{9}`),
email, and API-key patterns (`sk-`, `sk-or-`, `rzp_(test|live)_`, `AKIA…`). The processor
recurses dict/list/tuple/set and never raises — on internal error it returns a safe
`[REDACTED_ERROR]` sentinel that preserves only the non-PII correlation keys (`request_id`,
`job_id`, `task`, `task_id`, `user_ref`). Enforced by 16 unit tests in
`backend/tests/test_logging_redaction.py`.

(d) **Docker `json-file` rotation via an `x-logging` YAML anchor (no new infra).**
`docker-compose.yml` defines an `x-logging: &default-logging` anchor (`json-file` driver,
`max-size: 50m`, `max-file: 5`) applied to all 9 services. Worst-case ~250 MB per container,
~2 GB total — within the 3 GB box cap. Grafana Loki collection is deferred to P3.

**Consequences:** all ~19 existing stdlib callers emit redacted JSON without code changes. A
`request_id` + `user_ref` thread is available end-to-end from HTTP → Celery → AI gateway →
audit. DPDP/SEBI compliance is enforced at the log layer (not call-site discipline) for the
known key/value patterns. Log rotation is bounded within the shared-box cap. Four residual
risks are accepted for P1: (1) a raw UUID interpolated into a log message string under no
structured key is not regex-caught (UUID regex deliberately omitted so `job_id` stays visible —
mitigated by hashing at known call sites); (2) exception tracebacks are appended AFTER the
redaction processor, so an exception embedding PII in its message could leak — this codebase
raises opaque error codes; traceback scrubbing deferred to P2; (3) base64-encoded bytes under
an arbitrary key rely on call-site discipline; (4) `configure_logging()` clears root handlers
(intentional — single JSON handler), which drops any separately-configured uvicorn
access-log file handler.

**Tier-B adversarial sign-off:** independent Sonnet adversarial takeover (codex unavailable —
ChatGPT-plan entitlement error). Verdict **ACCEPT-WITH-CONDITIONS**; all MUST-FIX and
SHOULD-FIX conditions applied in-session. MUST-FIX: (M1) raw user UUID was %-interpolated
in `tasks/mf.py` and `billing/service.py` — replaced with `hash_user_ref(uid)` structured
fields; (M2) `task_revoked` had no contextvar clear — added, so a revoked task cannot
misattribute the next task's logs. SHOULD-FIX applied: phone value-regex backstop,
tuple/set recursion, safe-error sentinel preserving correlation keys. RCA:
`docs/rca/README.md` (2026-06-08 entry). Review ledger: `docs/project-state/reviews/b57-p1-logging.md`.

**Source:** `docs/project-state/LOGGING_PLAN.md` §1–§8; `BLOCKERS.md` B57;
`docs/project-state/reviews/b57-p1-logging.md`.
