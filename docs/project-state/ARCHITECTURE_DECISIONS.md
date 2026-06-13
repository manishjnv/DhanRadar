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
| ADR-0029 | Two additional login methods: Google SSO (server-side OAuth+PKCE) and TOTP as a standalone first factor | Accepted |
| ADR-0030 | Cohort label band goes category-class-aware (model v1.1, B58-f4) | Accepted |
| ADR-0031 | Email OTP as an alternative login factor (amends the OTP-first IGNORE scope) | Accepted |

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

## ADR-0029 — Two additional login methods: Google SSO (server-side OAuth+PKCE) and TOTP as a standalone first factor

**Date:** 2026-06-12 · **Status:** Accepted

**Context:** The canon (`DhanRadar_Architecture_Final.md` §2, `CANONICAL_OPENAPI_ALIGNMENT.md` §2)
specified email+password as the only login method, scoped TOTP to "Pro+ sensitive-action step-up"
(enrolment-only today, never checked at login), and contained **no** Google SSO. The "OTP-first"
signup pattern (D2) is explicitly REJECTED and grep-banned. The founder asked for (a) Google SSO
and (b) TOTP usable to log in — clarifying that TOTP here is **another way to log in**, not a
second factor. Both are net-new scope and an extension of the auth contract, so they require an ADR
before implementation (Engineering-Governance Inv. 4).

**Decision:**

(a) **Google SSO = server-side OAuth 2.0 authorization-code flow with PKCE (S256) + nonce**, not
the in-browser Google Identity Services button (founder choice). Rationale: no third-party JS, no
token ever transits the browser, and the flow terminates in the **same** `set_auth_cookies` path as
password login — preserving non-neg #5 (RS256 `__Host-` cookies, no bearer auth). New endpoints
`GET /api/v1/auth/google/{start,callback}` under the existing `/auth` prefix. The id_token is
verified **locally** against Google's JWKS (RS256-only, `aud`/`iss`/`exp`/`nonce`) — Google's token
endpoint is never trusted blindly. State is single-use (`GETDEL`); `email_verified=True` is
required. SSO is **fail-closed**: absent `GOOGLE_CLIENT_ID`/`_SECRET`/`_REDIRECT_URI` → 503.

(b) **TOTP standalone login = alternative first factor**, NOT 2FA, and NOT "OTP-first" (the banned
D2 pattern is OTP *replacing the password as the primary gate for all users at signup*; this is an
**opt-in** code-for-password swap for users who have already enrolled an authenticator under the
existing `/totp/setup`+`/totp/verify`). New endpoint `POST /api/v1/auth/totp/login`. Strictly
6-digit. Enumeration-safe: unknown email / not-enrolled / wrong code / locked all return the same
generic 401 (the per-account lock deliberately returns 401, not 429, so it is not an
account-exists oracle; the per-IP limiter supplies its own 429). Per-code single-use replay guard
(Redis `SET NX`, 90s). This supersedes the auth-feature-doc statement "TOTP is not enforced at
login" — TOTP is now a **login option**, while still never a forced second factor.

(c) **Account model:** `auth.users.hashed_password` becomes nullable (SSO-only accounts have none;
the password-login path runs a dummy-hash verify then the generic 401, so an SSO-only account is
indistinguishable from an unknown email). New unique `google_sub`. Migration `0018_google_sso`.

(d) **No silent account-linking onto password accounts (security decision).** DhanRadar does not
verify local emails, so a Google identity whose email matches an existing **password** account is
**rejected** (`/login?error=account_exists_use_password`), never auto-linked — otherwise a
Google-side controller of that address (e.g. a Workspace admin) could hijack the local account.
Auto-create is allowed only when no row exists; linking a passwordless row is future-proofed but
unreachable today. Explicit "link Google from settings while logged in" is deferred.

**Consequences:** three login methods now converge on one session-issuance path (parity on
refresh-jti storage, founding-access stamp, and security-audit events is asserted in the Tier-B
ledger). SSO needs operator-provisioned Google credentials + the registered redirect URI before it
leaves 503. A real email-verification flow remains absent — decision (d) is the compensating
control until one exists. Gate ledger: `reviews/google-sso-totp-login.md` (Security ACCEPT after
revise — backslash open-redirect + auto-link takeover both fixed; Compliance ACCEPT — no advisory
surface, no DPDP consent bypass). Net-new endpoints to fold into `CANONICAL_OPENAPI_ALIGNMENT.md`
at the next contract-sync.

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

## ADR-0030 — Cohort label band goes category-class-aware (model v1.1, B58-f4)

**Date:** 2026-06-12 · **Status:** Accepted (ADR-0029 reserved by PR #99 — Google SSO/TOTP login)

**Context:** The B58 category-relative label rule compares a fund's 1Y/3Y returns to its AMFI
category-peer median with a ±margin band (`backend/dhanradar/mf/cohort.py`). v1 shipped a flat
`_MARGIN_PCT = 2.0` return-percentage-points sized for equity dispersion. Debt-category peer
dispersion is sub-2pp, so the band was effectively inactive there: every debt fund labelled
`on_track` regardless of relative performance. The v1 activation entry
(`RATING_ENGINE_CHANGELOG.md`) explicitly accepted this as caveat B58-f4 and bound any change to
"a new version through this same gate" (B6/B28 two-person methodology gate, ADR-0026).

- **Option A — class-aware fixed bands (chosen):** margin keyed on the AMFI category-class prefix
  (`"<class> - <subcategory>"`): Debt 0.5pp · Hybrid 1.0pp · default 2.0pp (Equity, Solution
  Oriented, Other, unknown). Deterministic, auditable, bit-identical to v1 for equity.
- **Option B — dispersion-adaptive band (rejected for v1.1):** margin derived per-cohort from peer
  IQR/stdev. Self-calibrating but harder to explain/audit, changes equity behaviour too, and makes
  labels non-reproducible without snapshotting the dispersion input. A future-version candidate
  once prod label-distribution telemetry accumulates.
- **Option C — leave flat, document (status quo, rejected):** label quality for debt funds stays
  zero; the wedge's CAS report mislabels a whole asset class.

**Decision:** Option A as **model_version v1.1** through the ADR-0026 activation machinery:
`ranking_configs_v1.json` bumps `model_version` to `v1.1` and carries the margin manifest
(`labels.cohort_margin_pct`); the pure module constants (`_MARGIN_PCT_DEFAULT`,
`_MARGIN_PCT_BY_CLASS`) are lockstep test-enforced against the manifest
(`test_margin_manifest_lockstep_with_config`). No weight, normalization, confidence, or rule-table
change — the band parameters are the only delta. Unknown/unparseable category classes take the
WIDEST band (harder to flag → `on_track`), keeping the error direction conservative and
non-escalating. v1.1's registry activation row (`approved_by` = founder admin ≠ `created_by` =
`architecture-review`) is written at deploy; new score rows carry `model_version=v1.1` for
reproducibility.

**Consequences:** debt/hybrid funds can now genuinely reach `in_form`/`off_track`; equity labels
are unchanged; historical rows keep `v1` and stay bit-reproducible under their own version. The
band values are a first calibration sized to class dispersion — refinement is a future version
through the same gate, informed by `label_distribution_sanity` telemetry.

**Files:** `backend/dhanradar/mf/cohort.py`; `backend/dhanradar/scoring/ranking_configs_v1.json`;
`backend/dhanradar/scoring/RATING_ENGINE_CHANGELOG.md`; `backend/tests/unit/test_mf_cohort.py`.

**Source:** `BLOCKERS.md` B58-f4; `FINAL_SCORING_SPEC.md` §4.1/§7; ADR-0026;
`docs/project-state/reviews/b58-f2-f4-b62-f2.md`.

## ADR-0031 — Email OTP as an alternative login factor (amends the OTP-first IGNORE scope)

**Date:** 2026-06-12 · **Status:** Accepted

**Context:** The auth canon specifies email+password, Google SSO (ADR-0029), and TOTP standalone
login (ADR-0029) as login methods. The `docs/ui-system/` "OTP-first" signup pattern (D2) is
explicitly IGNORE-listed in MIGRATION_STRATEGY_FINAL.md: it proposes OTP as the primary gate for
all users at signup, requires an SMS provider, and was rejected (ADR-0014). On 2026-06-12 the
founder requested a 4th login method: email OTP as an alternative first factor — a user-initiated
code-for-password swap on the existing password-default login page, triggered from a secondary
"Sign in with email code" button.

This feature is NOT the IGNORE-listed OTP-first pattern. The IGNORE ban covers: OTP replacing
the password as the default gate for all users at signup, SMS as a delivery channel, and OTP as
the only login path. This feature is opt-in, email-delivered, behind the existing
password-default page, and requires an existing account — the same scope distinction ADR-0029
drew for TOTP-login vs the TOTP-as-mandatory-step-up concern.

**Decision:**

(a) **Email OTP = alternative first factor** — NOT 2FA, NOT the banned OTP-first pattern.
Endpoints: `POST /api/v1/auth/email-otp/request` (202 always — enumeration-safe even for
unknown email, cooldown, or daily cap; 503 `email_otp_not_configured` when `RESEND_API_KEY`
is unset, fail-closed matching SSO) and `POST /api/v1/auth/email-otp/login` (generic 401 on
every failure; RS256 `__Host-` cookie issuance via the shared `set_auth_cookies` path).

(b) **Redis-only state (no DB migration).** Five keys: `auth:email_otp:{uid}` (SHA-256 hash of
active code, TTL 600 s); `auth:email_otp_cooldown:{uid}` (send cooldown, SET NX 60 s);
`auth:email_otp_daily:{uid}` (daily send cap, SET NX + INCR + EXPIREAT);
`auth:email_otp_attempts:{uid}` (failed-verify lock, 5 attempts / 15 min, 401 not 429 —
not an account oracle); and `auth:email_otp_used:{uid}:{hash}` (per-code atomic consume
marker, SET NX — never deleted, per-code keying closes the TOCTOU double-spend race without
introducing a post-login lockout).

(c) **Delivery via `notifications.channels.deliver_email` (Resend; interface-only coupling;
code never logged).** Send is fire-and-forget (`asyncio.create_task`) to remove response time
as an enumeration oracle.

(d) **UI handover.** The login page's code-mode (previously the authenticator-app TOTP entry
form) is now email OTP. `POST /auth/totp/login` stays live API-side; settings → Security
enrolment is untouched.

(e) **Deletion-pending accounts:** silent 202 on the request endpoint; 403 only after code
verification on the login endpoint (not an account oracle — matching the TOTP-login accepted
residual, ADR-0029).

(f) **Digit validation hardening:** all OTP schemas (new email-OTP and existing TOTP) use
`[0-9]` not `\d` (Unicode-digit hardening).

**Consequences:** four login methods now converge on one session-issuance path. Email OTP is
fail-closed: absent `RESEND_API_KEY` → 503 (SSO pattern); TOTP login and Google SSO are
unaffected. The per-code consume marker (`auth:email_otp_used:{uid}:{hash}`) is the TOCTOU
fix — it is deliberately NOT cleared on success (clearing would reopen the race). A DPDP
counsel-confirmation residual is open for cross-border transactional auth email via Resend
(non-Indian processor; see B64). Gate ledger: `reviews/email-otp-login.md` (Security ACCEPT
after revise + re-verify; Compliance ACCEPT-WITH-CONDITIONS, all 3 conditions satisfied).
Net-new endpoints to fold into `CANONICAL_OPENAPI_ALIGNMENT.md` at the next contract-sync.

Alternatives considered:

- **Authenticator-app TOTP only (no email OTP):** the founder explicitly rejected this for
  friction — TOTP requires prior enrolment and a phone app; email OTP works for any account
  without setup.
- **Magic links (single-use URL emailed):** rejected because the token lives in the email body
  for longer than a 6-digit code (typical link expiry 15–30 min vs 10 min code), and a link
  in transit or in email search is a more phishable surface than a short code the user must
  type.

**Source:** `docs/project-state/reviews/email-otp-login.md`;
`BLOCKERS.md` B64; ADR-0029 (precedent for opt-in alternative factor scope).

## ADR-0032 — Concentration-band taxonomy for the mood-context surface (PU1)

**Date:** 2026-06-13 · **Status:** Accepted

**Context:** The mood-context educational surface (PU1) needs a coarse, descriptive read of
portfolio structure to pair with the market-regime read. The existing concentration endpoint
(`/api/v1/insights/{portfolio_id}/concentration`) exposes per-category `allocation_pct` and an
`observation` text line but no banded label. A raw percentage cannot be surfaced in the DOM
(non-neg #2: numeric score never reaches the client). A descriptive band — empty / high /
moderate / low — gives the educational read without exposing the underlying figure.

**Decision:** Introduce a descriptive (non-prescriptive, non-advisory) concentration band derived
from existing allocation math already computed in `get_concentration`. Thresholds:

- 0 funds → `empty`
- 1 fund OR top category ≥ 70 % → `high`
- Top category 40–69 % → `moderate`
- Top category < 40 % with 2+ funds → `low`

The underlying percentage is computed server-side and **never serialized** (non-neg #2). The band
is an educational description of structure, not an evaluation or a recommendation, and is always
rendered alongside the independence disclaimer and the full disclosure bundle (non-neg #1 / #9).
The independence disclaimer is placed **between** the regime read and the structure read in the
`observations` array (index 1) so the regime↔concentration pairing is never adjacent without the
"not a signal to act" line between them (Compliance review F2).

**Consequences:** This is a PU1-introduced taxonomy, distinct from the scoring engine's
`in_form/on_track/off_track/out_of_form` labels and from market mood. Thresholds are provisional
v1 heuristics sized for an initial educational read and may be recalibrated via the ADR gate if
label-distribution telemetry shows systematic mismatch. Any future surface needing a portfolio
concentration band should reuse `_concentration_band` in `backend/dhanradar/insights/service.py`,
not introduce a parallel banding scheme.

**Files:** `backend/dhanradar/insights/service.py` (`_concentration_band`, `_build_observations`);
`backend/tests/unit/test_mood_context_service.py`;
`frontend/src/features/insights/__tests__/MoodContextSection.test.tsx`.

**Source:** `BLOCKERS.md` PU1 row; `docs/project-state/reviews/pu1-mood-portfolio-context.md`;
Compliance review F2 (observation ordering).

## ADR-0033 — MF master-DB P2 data sourcing: build top-10 constituents scrapers, relative-only benchmark display, counsel-attested redistribution

**Date:** 2026-06-13 · **Status:** Accepted (ADR-0032 reserved by a concurrent session —
mood-context concentration-band taxonomy)

**Context:** The "local MF master DB" plan (memory `mf-master-db-plan-and-p0`; P0 NAV
provenance + compression shipped in ADR-0025-aligned migrations 0019/0020, PR #113) has a P2
tier that was BLOCKED pending three founder/compliance decisions: how to source fund
**constituents** (holdings-of-funds, needed for the overlap matrix which is permanently `{}`
today because `build_snapshot()` never receives a `constituents` feed), how to surface
**benchmark** comparisons (B1), and the **legal posture** for redistributing AMFI/NSE-BSE
index-derived data commercially. Deep research established: there is no free consolidated
constituents API; NSE/BSE restrict commercial *display/redistribution* of raw index values
(internal computation is lower-risk); and AMFI tightened fintech data access in Sept 2025. On
2026-06-13 the founder resolved all three.

**Decision:**

(a) **Constituents — BUILD, not buy (top-10 AMCs first).** Build per-AMC parsers for the
monthly SEBI-format portfolio disclosures of the **top ~10 AMCs by AUM** (≈75-80% of industry
assets), with name→ISIN resolution (SEBI's holdings table does not mandate ISIN). A licensed
feed (ICRA MFI360 / CMOTS) is explicitly deferred — revisited only once there is revenue. This
is a new sanctioned source under `DhanRadar-Data-Ingestion-Normalization`: it requires a
constituents canonical schema + provenance + monthly freshness SLA + a Tier-B/Compliance review
(scraping ToS + DPDP) before it goes live. Coverage below the top-10 is a documented, `log()`-ed
gap, never silently presented as full-universe overlap.

(b) **Benchmark — relative metrics only, no raw licensed index values in the DOM.** The public
surface shows only *derived/relative* educational metrics (e.g. "this fund vs its category
benchmark"), never raw NSE/BSE TRI point values. TRI series are stored for **internal
computation only**. This composes with the non-numeric-in-DOM boundary (ADR-0010) and keeps the
platform clear of NSE/BSE display-redistribution restrictions. Benchmark mapping depends on the
Task-3 scheme-master enrichment (`benchmark_index` population).

(c) **AMFI/NSE-BSE redistribution — counsel-attested (founder).** The founder attests on
2026-06-13 that counsel has signed off on the AMFI NAV / index-derived redistribution posture
for the educational platform. **This ADR records the founder's attestation; it does NOT
self-certify legal compliance** (per `DhanRadar-SEBI-Compliance-Guardrail`, which escalates legal
questions to counsel and never self-certifies). ACTION RESIDUAL: file the actual counsel sign-off
artifact (date, scope, signatory) under `docs/legal/` and link it here; the attestation stands as
the go-ahead, the filed document is the evidence of record.

**Consequences:** P2 is UNBLOCKED for implementation, but it is multi-session work sequenced
BEHIND its prerequisites — Task 2 (persisted `mf_fund_metrics` + cohort/scoring rewire, the 6M-row
OOM fix) and Task 3 (scheme-master enrichment incl. `benchmark_index` + a scheme-lineage table).
Order: Task 2 → Task 3 → P2a constituents (top-10) → P2b benchmark TRI (relative). Each P2 surface
that touches a public output is governed by `DhanRadar-SEBI-Compliance-Guardrail`; the constituents
scraper and the TRI ingestion each get their own data-source sanction + Tier-B/Compliance review
at build time. The "relative-only" benchmark rule is binding on all future benchmark UI.

**Alternatives considered:**

- **License a constituents feed now (ICRA MFI360 / CMOTS):** rejected for launch on cost vs the
  ₹15K/month budget target; ICRA ships an off-the-shelf Portfolio Overlap product, so buying stays
  the clean fallback once revenue justifies it.
- **Display raw TRI index values:** rejected — NSE/BSE commercial display/redistribution
  restrictions + the non-numeric-in-DOM boundary both cut against it; relative metrics deliver the
  educational value without the licensing exposure.
- **Defer P2 entirely until revenue:** rejected — the founder wants the overlap + benchmark wedge
  built on the free top-10/relative path, which is viable now.

**Source:** founder decisions 2026-06-13; memory `mf-master-db-plan-and-p0`; deep-research report
(this session); ADR-0010 (non-numeric/educational boundary), ADR-0025 (AMFI canonical NAV source);
`DhanRadar-Data-Ingestion-Normalization` (sanctioned-source regime),
`DhanRadar-SEBI-Compliance-Guardrail` (advice/redistribution boundary). Counsel artifact: TO FILE
under `docs/legal/`.
