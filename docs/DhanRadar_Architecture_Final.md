# DhanRadar — Final Detailed Architecture Document

**Status:** Canonical architecture of record. Supersedes the narrative content of the five source documents for engineering purposes.
**Audience tiers:** Tier A (exec / onboarding, read standalone in <10 min) · Tier B (layers & cross-cutting) · Tier C (per-module deep appendices, independently buildable).
**Synthesised from:** `DhanRadar_Master_Blueprint.md`, `Market Intelligence & Recommendation Ecosystem.md`, `dhanradar-v2-2-strategic-update.md`, `DhanRadar_Reality_Layer.md`, `DhanRadar_v2_3_Implementation_Addendum.md` (+ `.docx` duplicate). The two empty `New Text Document*.md` files contain nothing and are excluded.
**Date:** 2026-05-17.

> **On the absent v2.1.** No v2.1 architecture file exists in the corpus. It is **not required**: v2.2 and v2.3 are additive overlays that re-state every recommendation (Rec 1–14, R15–R24) and fully respecify the runtime stack (12-container Docker, OpenRouter strategy, cost model). Where a foundational detail could only have lived in v2.1, it is reconstructed here and marked **[ASSUMPTION]**. Nothing material is missing.

---

# TIER A — OVERVIEW

## A1. Context & Vision

DhanRadar is an **educational financial-intelligence platform for Indian retail investors**, spanning mutual funds, ETFs, stocks, portfolio analytics, and market-regime intelligence. Its defensible position is being *the most explainable analytics platform in India*: every ranking exposes its contributing and contradicting signals, every AI output carries a confidence band, and the public track record is unhidden.

**Why this document exists:** five source documents accreted across revisions (vision → competitive research → strategic re-alignment → regulatory reality → implementation stack). They overlap, occasionally diverge on numbers, and assume a v2.1 base that is absent. Engineering needs one voice. This document collapses every conflict to a single canonical decision (§A2), then specifies the platform as decoupled modules that can be built in dependency order without regressing completed work.

**Hard product boundary (non-negotiable, all tiers):** DhanRadar is educational. No buy/sell/hold advice, no guaranteed returns, no order routing, no discretionary portfolios. Output language is *signal / probability / trend / risk / momentum / historical pattern*. This boundary is an architectural constraint enforced in code (serializer-level disclaimer injection, schema-level rejection of advisory `recommendation_type`), not merely a copy guideline.

## A2. Reconciliation Ledger (the single source of truth for conflicts)

| # | Conflict across source docs | Canonical decision | Rationale |
|---|---|---|---|
| 1 | Product shape: MF-first wedge (Reality Layer) vs broad platform (v2.2/v2.3) | **Broad platform, MF-first phasing** | User decision. Full architecture documented; MF is launch scope, others sequenced. |
| 2 | Scoring: 5-axis DhanRadar Score + confidence (v2.2) vs 🟢🟡🟠🔴 verb labels (Reality Layer) | **Multiple methods backstage → ONE unified score + confidence band + verb label on UI** | User decision. See §S (Unified Scoring). |
| 3 | Cost/infra: ₹10,944/mo Hetzner+Anthropic (v2.2) vs ₹1,090/mo Hostinger+OpenRouter (v2.3) | **v2.3 wins** (Hostinger KVM2, 12 containers, OpenRouter free-pool→Sonnet spillover) | Latest overlay; "best of" for cost. |
| 4 | Pricing | **v2.2 wins** (Pro ₹1,999/yr, Pro+ ₹3,999/yr, founder lifetime ₹4,999, 33% annual discount) | v2.3 explicitly does not change pricing. |
| 5 | Data-source ladder differs per doc | **Best-of merge**: funds → MF Central → Account Aggregator → CAS parser → AMFI NAV; equities/ETF → Upstox → Kite → TwelveData → NSE dump — all behind one Market Data Adapter | Combines v2.2 Rec 5 + Reality Layer §1.3/§1.6. |
| 6 | Mood Compass cadence: "9 AM & 4 PM IST" (v2.2) vs "2× daily" (v2.3, unspecified) | **9:00 AM & 4:00 PM IST** | v2.2 is explicit; v2.3 is consistent, just unspecified. |
| 7 | SWOT: weekly + Sonnet (v2.2 R16) vs monthly TTL + free model (v2.3) | **Monthly cache TTL + earnings-triggered invalidation; free model (`deepseek-chat-v3:free`)** | v2.3 is the later overlay; earnings invalidation gives freshness when it matters. |
| 8 | AI budget cap: `DAILY_PREMIUM_BUDGET_USD=0.50` vs "$9.50/day hard cap" (v2.3 risk register) | **Free pool 1,000 req/day; premium spillover soft cap $0.50/day; $9.50/day absolute hard ceiling** | Both are v2.3; one is the soft governor, one the circuit-breaker. |
| 9 | "Why X Moved Today" ownership | **Stock Intelligence module owns it**; AI Enrichment references it | Removes the only module-ownership ambiguity the drafters surfaced. |
| 10 | Missing v2.1 | **Not reconstructed wholesale**; gaps marked `[ASSUMPTION]` | User decision; additive overlays are self-contained. |

**Provenance principle:** every Tier C appendix ends with a **Provenance** block tagging each element to its source doc and flagging content **UNIQUE** to one doc, so deduplication never silently drops a doc's distinctive contribution.

## A3. Layer Model (8 layers)

1. **Client / SSR** — Next.js App Router, anonymous-first, SEO/ISR, shared design system + `UnifiedScoreDisplay` + `RankingExplainer` primitives.
2. **API** — FastAPI; JWT tier gating via one shared `Depends`; anonymous read-only fidelity downgrade; public read-only API (Year 2).
3. **AI / LLM Gateway** — OpenRouter free-model round-robin → Claude Sonnet spillover; Pydantic `QualityValidator`; 3-strike skip; budget governor.
4. **Domain Services** — MF, ETF, Stock, Portfolio, Mood, News, Search, Track-Record, AI Enrichment, Alert/Digest, Nudge.
5. **Market Data Adapter** — provider-agnostic, config-driven routing, circuit breaker, fallback ladders.
6. **Data / Storage** — PostgreSQL (+ TimescaleDB hypertables, GIN `tsvector` FTS, monthly partitioned audit), Redis (namespaced), Cloudflare R2.
7. **Async / Scheduling** — Celery `batch`/`mood`/`misc` queues + Beat; event bus (Redis Streams / Celery fan-out).
8. **Cross-cutting** — Auth & tiering, Consent/DPDP, Compliance audit, Observability + Cost governor, Admin & governance, the educational/regulatory boundary.

## A4. Module Map & Dependency DAG (incremental build order)

The DAG is **acyclic by construction**. Every edge is a *documented interface* (REST contract or event) — never a shared mutable table. A module may be built, tested, and deployed once its in-edges exist as stubs.

```
                 ┌─────────────────────── GLOBAL / SHARED (Phase 0) ───────────────────────┐
                 │ UI/Design · Auth&Tiering · Consent/DPDP · Compliance Audit ·            │
                 │ Observability+CostGovernor · Admin&Governance · Notification            │
                 └───────────────┬──────────────────────────────────┬─────────────────────┘
                                 │ (interfaces only)                 │
                 ┌───────────────▼───────────────┐                  │
                 │  Market Data Adapter (P0/P1)   │                  │
                 └───────┬───────────────┬────────┘                  │
                         │               │                           │
              ┌──────────▼───┐   ┌───────▼────────┐                  │
              │ AI/LLM Gateway│  │ Rating/Scoring  │◄──── signals ────┤
              │   (P1)        │  │  Engine (P1)    │ (one unified     │
              └──────┬────────┘  └───────┬─────────┘  score out)      │
                     │                   │                            │
   ┌─────────────────┼───────────────────┼────────────────────────────┼───────────────┐
   │                 ▼                   ▼                            ▼               │
   │  MF (P1) → ETF (P2)   Stock (P2/P3) · News (P3) · Search (P2/P3)                 │
   │       │                     │                                                    │
   │       └──────► Portfolio Intelligence (P5) ──► Track-Record/Backtest (P4)         │
   │  Mood Compass (P2) ──► AI Enrichment (P2/P3) ──► Alert&Digest (P-retention)       │
   │                                              └─► Behavioral Nudge (P-conversion)  │
   └──────────────────────────────────────────────────────────────────────────────────┘
```

Build order: **Global/Shared → Market Data Adapter → AI Gateway + Rating Engine → MF → Mood Compass → Stock/Search → AI Enrichment/News → Track-Record → Portfolio → ETF → Alert/Digest → Nudge.** Each later module consumes earlier ones only through their published interface, so none forces edits upstream.

## A5. Phased Delivery (MF-first, reconciled)

| Phase | Weeks (v2.2 18-wk) / 90-day map | Scope |
|---|---|---|
| **P0 Foundation** | Day 1–15 | Legal entity, Hostinger KVM2, Cloudflare, GitHub (private), OpenRouter $10 unlock, Global/Shared modules skeleton, Consent/DPDP + Compliance audit live before any user data. |
| **P1 MF launch core** | Wk 1–4 / Day 16–60 | Market Data Adapter, AI Gateway, **Rating/Scoring Engine v1**, **Mutual Fund module** (CAS→60s report, AMFI NAV pipeline), Auth, Notification (Telegram). |
| **P2 Acquisition** | Wk 3–4 | **Mood Compass**, Signal & Source-Reliability, public discovery, Search (FTS), DhanRadar Score on public pages, ETF. |
| **P3 AI engine + explainability** | Wk 5–7 | Stock Intelligence, News tagging, AI Enrichment (SWOT, earnings, analogues, "Why this ranking"). |
| **P4 Trust** | Wk 8–10 | Track-Record / Backtest public page, onboarding + risk quiz, compliance disclaimer versioning. |
| **P5 Monetization** | Wk 11–13 | Portfolio Intelligence, Pro/Pro+ launch, founder lifetime pricing. |
| **P6 Growth** | Wk 14–18 | Gamification, referrals, WhatsApp, creator partnerships, public read-only API (Year 2). |

## A6. Non-Functionals & Constraints (summary)

- **Cost ceiling:** ≤ ₹1,090/mo infra (v2.3); AI free pool 1,000 req/day, premium spillover soft $0.50/day, hard $9.50/day. Break-even ≈ 6 Pro subscribers.
- **Capacity:** Hostinger KVM2 — 2 vCPU, 8 GB RAM; 12 containers ≈ 4.2 GB allocated, ~3.8 GB headroom; <10K MAU launch envelope.
- **Latency targets:** API p99 < 200 ms (degraded alert at 500 ms/5 min); CAS→report ≤ 60 s; typeahead < 50 ms.
- **Regulatory:** SEBI educational boundary; DPDP Act 2023 (granular consent, 72 h breach to Data Protection Board, erasure/portability, ≤₹250 Cr/incident penalty); CERT-In (6 h incident, 180-day India-resident logs, NIC NTP); SEBI 7-year audit retention; RIA path sequenced P1 education → Y2 partner-RIA → Y3 own-RIA (business decision, not a module).
- **Single-user Claude Code** is dev-only; never in production runtime (structural Linux-perm enforcement on VPS).

---

# TIER B — LAYERS & CROSS-CUTTING

## B1. Client / SSR Layer

Next.js App Router + React Server Components; Tailwind + shadcn/ui (vendored, not npm-linked); TradingView chart wrappers; dark-mode via `class` strategy with server-side cookie injection (no FOUC). Anonymous routes use `export const revalidate = 300` (5-min ISR); top-1,000 highest-traffic slugs pre-rendered via `generateStaticParams`; Cloudflare CDN absorbs anonymous traffic; Nginx routes `/api/*` to FastAPI, everything else to Next.js. Two platform UI primitives are mandatory and shared (no domain module re-implements them): `UnifiedScoreDisplay` (renders **one** label + one confidence word; numeric score and factor weights are *not* in the DOM) and `RankingExplainer` ("Why this ranking?" drawer). Detail in Tier C → Global/Shared §1.

## B2. API Layer

FastAPI. One shared dependency `Depends(require_tier(...))` and `Depends(current_user_or_anonymous)` — **domain modules never implement their own auth or fidelity logic**. Anonymous = no cookie → Nginx zone `anon:10m rate=30r/m`, lower-fidelity responses (top-5 not top-10, no AI thesis) with zero domain code change. Tier gate raises `HTTP 402` with `{upgrade_url}`. Public read-only API tier (developer/business rate plans) is deferred to Year 2 (v2.2 Rec 13). Detail in Tier C → Global/Shared §2.

## B3. AI / LLM Gateway Layer

`OpenRouterGateway` round-robins a free-model pool (DeepSeek V3, Llama 3.3 70B, Qwen 2.5 72B, Gemma 3 27B, Mistral Small 3.1) at 20 req/min/model; on `RateLimitError` rotates model; on schema-validation failure either spills to Claude Sonnet (high-stakes task types: `mood_commentary`, `earnings_summary`, `stock_pick`, `mf_pick`) within the premium budget, or applies the **3-strike-per-(ticker,day) skip**. Every output is validated by `QualityValidator` against a Pydantic schema extending `AIOutputBase` (see §S). Budget counters `ai:budget:free:today` / `ai:budget:premium:today` are authoritative and enforced *inside* the gateway (`budget_guard()`); domain modules never call the LLM directly and never see budget logic. Task→model routing lives in `TASK_MODEL_PREFERENCES`, sourced from the Admin module's versioned prompt templates (no hardcoded prompts).

## B4. Market Data Adapter Layer

Provider-agnostic gateway mirroring the LLM-gateway pattern: config-driven (YAML) routing with circuit breaker and ordered fallback ladders (ledger #5). It emits normalized events (`mfcentral.holdings.received`, `aa.holdings.received`, `broker.positions.received`, NAV/price refreshed) that domain modules consume — domain modules never call a data vendor directly, so a provider swap is config-only. Detail referenced throughout Tier C.

## B5. Data / Storage Layer

PostgreSQL 16 single instance, **separate schema per concern, new tables only, no cross-module shared mutable tables** (decoupling invariant). TimescaleDB hypertables for NAV/price time-series (`mf_nav_history`, `etf_price_history`) with monthly chunking + continuous aggregates. GIN `tsvector` + `pg_trgm` for full-text/typeahead (Elasticsearch explicitly dropped, v2.3). `ai_recommendation_audit` monthly-partitioned via `pg_partman`, 7-year retention. Redis is namespaced per module (`mf:`, `etf:`, `stock:`, `mood:`, `port:`, `tr:`, `news:`, `search:`, `anon:`, `ai:budget:`, `auth:`, `consent:`, `notif:`, `gamif:`, `nudge:`, `alert:`, `digest:`) with explicit TTLs (per appendix). Cloudflare R2 for nightly `pg_dump` backups, share-card PNGs, exports, audit archival (replaces MinIO; no streaming replica at <10K MAU).

## B6. Async / Scheduling Layer

Celery queues: `batch` (stock/MF analysis, news, search prewarm), `mood` (Mood Compass), `misc` (digest, gamification, notifications, backups, nudges). Celery Beat schedule is consolidated and conflict-checked across appendices (see §V Consistency). Inter-module communication is event-driven (Redis Streams or Celery fan-out); events are the *only* runtime coupling besides REST contracts.

## B7. Global / Shared Modules

Foundational, Phase-0/1, consumed by every domain module through stable interfaces (domain modules never reach around them). Full specs in **Tier C → Global / Shared Modules** §1–9: UI/Design System, Auth & Tiering, Consent & DPDP, Compliance Audit, Notification, Observability & Cost-Budget Governor, Gamification & Share Cards, Onboarding & Risk-Profile, Admin & Governance.

## B8. Cross-cutting Constraints (architectural, not appendix)

| Constraint | Enforcement point |
|---|---|
| SEBI educational boundary (no buy/sell, no intraday/Greeks, no guaranteed returns) | Serializer injects disclaimer; schema rejects advisory `recommendation_type`; Admin content-moderation regex on user text + prompt-injection filter on AI chat |
| DPDP per-purpose consent | `Depends(require_consent("purpose"))` gate on every data-processing endpoint; append-only `consent_audit_log` |
| DPDP rights (access/correct/erase/port) | `/api/v1/data-rights/*`; `process_erasure` Celery task; 30-day SLA monitor |
| CERT-In | 180-day India-resident `journald` logs (`MaxRetentionSec=15552000`); NIC NTP sync; 6 h incident runbook |
| AI governance (trust-collapse prevention) | Confidence floor (refuse < 0.30 → "Insufficient data"); >5% batch label-churn → human-review gate (Compliance module, fail-closed); methodology versioned in `rating_engine_changelog`; rating hysteresis (2 consecutive evals); label-distribution sanity; disagreement disclosure mandatory |
| RIA path | Business sequencing P1 education → Y2 partner-RIA → Y3 own-RIA; **not a software module** |
| Build-vs-partner | Build: rating engine, CAS parser, AI layer, analytics, notifications, observability. Partner: AA (Setu/Finvu), KYC (Karza/Digio/IDfy, Y2), payments (Razorpay), email (SendGrid), error tracking (Sentry), flags (PostHog), WhatsApp (Y2). |

---

# §S — UNIFIED SCORING (Rating / Scoring Engine)

This is the platform's IP core and the single answer to ledger #2. Multiple methods run **backstage**; the UI shows **one** number-free label + one confidence word.

### S1. Responsibility & decoupling

The Rating/Scoring Engine is a standalone Phase-1 service. Domain modules **feed signals** to it (via `*.holdings.updated` / `*.score.requested` events; it reads agreed read-only Postgres views) and **consume the result** (via `scoring.result.published` events / `GET /internal/v1/score/{instrument_type}/{identifier}` → `{score, confidence, label, valid_until, eval_seq}`). No domain module recomputes, reweights, or overrides the score. This is the strict coupling surface.

### S2. Background methods (multi-method, hidden)

For a given instrument the engine computes, in parallel:

1. **Deterministic factor model** — normalized factor inputs per instrument class:
   - *MF/ETF:* rolling 1M/3M/6M/1Y/3Y/5Y absolute & category-relative returns, Sharpe, Sortino, max drawdown, downside protection, expense ratio, AUM stability, category-rank percentile, (ETF) tracking error 1Y/3Y, premium/discount-to-NAV, liquidity score.
   - *Stock:* 5-axis DhanRadar Score — **Quality · Valuation · Momentum · Risk · Trend**, each 0–100, aggregate weighted (factor weights are versioned in `ranking_configs`, must sum to 1.0 ± 0.001, human-approved before activation).
2. **Deterministic verb-label rules** (Reality Layer §3.1):
   - 🟢 **In-form** — outperforming category 1Y *and* 3Y, controlled drawdown.
   - 🟡 **On-track** — matching category, no red flags.
   - 🟠 **Off-track** — underperforming category 12 m+ *or* fund-manager change.
   - 🔴 **Out-of-form** — sustained underperformance + structural concern.
3. **AI-assisted enrichment** — narrative/contradiction surfacing only; never sets the score numerically. Output validated against `AIOutputBase` (≥2 contributing signals; confidence > 0.7 ⇒ ≥3 signals).

### S3. Collapse function → one unified output

```
unified_score (0–100)  = weighted blend of deterministic factor model
                          (versioned weights; AI never moves the number)
verb_label             = deterministic rule table (S2.2), NOT derived from the number
confidence_band        = f(signal coverage, source_reliability_avg, agreement)
                          high ⇒ ≥3 contributing signals AND high-reliability sources
                          < 0.30 ⇒ refuse: emit "Insufficient data" (no label)
UI surface             = verb_label + confidence word ONLY
                          (numeric score + factor weights never reach the DOM)
methodology            = public page /methodology, versioned in rating_engine_changelog
```

### S4. Governance rules (hard, enforced in-engine)

- **Hysteresis:** a label flip publishes only after **2 consecutive evaluations** at the new label; `eval_seq` is exposed so downstream alerting can gate on it.
- **Confidence floor:** below 0.30 → no rating, return `"Insufficient data"`.
- **Label-distribution sanity:** per-batch share of 🟢/🟡/🟠/🔴 must stay within bounds (prevents all-🔴 collapse in a crash).
- **Human-review gate:** if > 5 % of the universe changes label in one batch, the batch is held in `pending_publish` (Compliance module, fail-closed) until admin approval.
- **Methodology versioning:** every change writes `rating_engine_changelog` (factors_before/after, published methodology URL); deterministic criteria are publishable, prompts/cadence/data-pipeline stay proprietary.
- **Disagreement disclosure:** contributing *and* contradicting signals always shown; uncertainty is never hidden.

---

# §C — COMPLIANCE & AI GOVERNANCE (first-class layer)

(See also Tier C → Global/Shared §3 Consent/DPDP, §4 Compliance Audit, §9 Admin.) Summary of the architectural obligations the Reality Layer imposes:

- **DPDP:** granular per-purpose consent (no bundling), append-only `consent_audit_log`, `data_principal_requests` for access/correction/erasure/portability (30-day SLA, daily breach-of-SLA monitor), 72 h breach notification to the Data Protection Board, cross-border check before routing user-specific data to non-Indian LLM APIs, children's-data flow feature-flagged off until verified-parental-consent UI exists.
- **CERT-In:** 6 h incident report runbook + templated forms; 180-day India-resident logs; NIC NTP (`time.nplindia.org` / `samay1.nic.in`) — timestamps are legally meaningful only if NTP is correct.
- **SEBI:** educational-only framing enforced in code; 7-year `ai_recommendation_audit` (monthly-partitioned, R2-archived) tying every served output to the exact disclaimer version in force; disclaimer versioning table; public Track Record with mandatory "past performance" disclaimer.
- **AI trust-safety:** adversarial red-team suite (hallucination, outdated data, confidence drift, bias, prompt injection, label collapse) pre-launch; refuse + log on prompt-injection ("pretend to be an advisor") attempts; confidence floor; human-review gate; methodology transparency (SEBI views favorably).
- **RIA sequencing (business, documented for context):** P1 pure education (lowest burden) → Y2 partner with existing RIA (validate ARPU) → Y3 own RIA only if AUA > ₹500 Cr. ₹50L net-worth + 2 officers + 5-yr records if/when own-RIA.

---

# TIER C — PER-MODULE DEEP APPENDICES

Each appendix is self-contained and follows a fixed template (Responsibility · Non-goals · Public interface (the only coupling surface) · Data schema · Pipeline + cache-invalidation · Scoring integration · Failure modes · Build-vs-partner · Provenance). Domain modules first, then Global/Shared.

## C-Domain

### Mutual Fund Module

**Phase:** Phase 1 (Launch-critical)

**Responsibility & scope:** The Mutual Fund Module is the primary portfolio intelligence layer for DhanRadar at launch. It ingests holdings from multiple data sources (MF Central API, Account Aggregator, CAS file upload, AMFI NAV fallback), normalizes them into a unified holdings schema, computes derived analytics (XIRR, category allocation, overlap, expense drag), and feeds scored signals to the shared Rating/Scoring Engine. It owns the full lifecycle from raw holding ingestion through the 60-second post-upload report hook, daily NAV refresh, and periodic rating cadence. It does not render UI or own the scoring algorithm.

**Non-goals:**

- Does not issue buy, sell, hold, or switch recommendations — all output is descriptive/analytical in accordance with SEBI's investment-adviser boundary; any LLM-generated commentary is labeled "AI-generated insight, not investment advice"
- Does not own or redefine the unified score, confidence band, or verb label (🟢/🟡/🟠/🔴) — these are consumed from the shared Rating/Scoring Engine via its documented interface
- Does not handle equity stocks, ETFs, bonds, or any non-MF instrument (even if the underlying holds them)
- Does not own Account Aggregator (AA) consent flows — the AA Adapter owns consent; this module only consumes the normalized holding events emitted by the Market Data Adapter
- Does not store raw CAS XML/PDF blobs beyond the 24-hour processing window; long-term storage is the user's responsibility
- Does not perform broker order routing or any transaction execution

**Public interface (only coupling surface):**

REST endpoints (all under `/api/v1/mf/`):

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/mf/upload/cas` | Accept CAS PDF/XML upload; enqueue `mf.cas.parse` Celery task; return `{ job_id, estimated_seconds: 60 }` |
| `GET` | `/api/v1/mf/upload/cas/{job_id}/status` | Poll parse status; returns `{ status: queued|processing|done|failed, progress_pct }` |
| `GET` | `/api/v1/mf/portfolio/{user_id}` | Return normalized holdings snapshot (latest NAV-adjusted) with XIRR, allocation breakdown, overlap matrix |
| `GET` | `/api/v1/mf/portfolio/{user_id}/report` | Return full 60-second report payload (summary + per-scheme analytics + score labels) once job is `done` |
| `GET` | `/api/v1/mf/fund/{isin}` | Return fund metadata, category, AMC, AUM, expense ratio, rolling returns |
| `GET` | `/api/v1/mf/fund/{isin}/nav/history` | Return NAV time-series (delegates to TimescaleDB view) |
| `GET` | `/api/v1/mf/portfolio/{user_id}/overlap` | Return pairwise fund overlap table |
| `POST` | `/api/v1/mf/portfolio/{user_id}/refresh` | Trigger manual NAV + rating refresh for a user (rate-limited: 1/hour) |

Events emitted: `mf.holdings.updated` (→ Rating/Scoring Engine, Notification), `mf.cas.parsed`, `mf.nav.refreshed` (→ Rating Engine batch rescore, cache invalidation), `mf.score.requested`.
Events consumed: `aa.holdings.received`, `mfcentral.holdings.received` (→ normalize), `scoring.result.published` (→ write `user_fund_scores`, invalidate score cache).

**Data schema (Postgres):** `mf_funds` (isin PK, amfi_code, scheme_name, amc_name, category, sub_category, aum_crore, expense_ratio_pct, exit_load_pct/days, benchmark_index, sebi_category, risk_o_meter); `mf_nav_history` (TimescaleDB hypertable, PK (isin, nav_date), nav, source; 1-month chunks; continuous aggregate `mf_nav_monthly_agg` with rolling_return_1y); `mf_user_holdings` (user_id, isin, folio_number, units, avg_cost_nav, invested_amount, source ∈ cas|mfcentral|aa|manual, as_of_date; UNIQUE(user_id,isin,folio_number)); `mf_portfolio_snapshots` (user_id, snapshot_date, total_invested, current_value, xirr_pct, category_allocation JSONB, overlap_matrix JSONB; UNIQUE(user_id,snapshot_date)); `mf_cas_jobs` (job_id PK, user_id, status, progress_pct, source_hash, error_message, completed_at); `user_fund_scores` (user_id, isin, unified_score, confidence_low/high, verb_label, scored_at; UNIQUE(user_id,isin)).

**Redis keys / TTLs:** `mf:nav:{isin}:latest` 6 h · `mf:fund:{isin}:meta` 24 h · `mf:portfolio:{user_id}:snapshot` 15 m · `mf:report:{job_id}` 2 h · `mf:cas:dedup:{source_hash}` 48 h · `mf:overlap:{user_id}` 1 h · `mf:score:{user_id}:{isin}` 30 m · `mf:refresh:ratelimit:{user_id}` 1 h · `mf:isin_users:{isin}` (no TTL, reverse index for targeted invalidation).

**Pipeline — CAS→60s report:** (1) POST, SHA-256, `mf:cas:dedup` check → existing job_id if hit. (2) write `mf_cas_jobs` queued, enqueue `mf.cas.parse`, return `{job_id, estimated_seconds:60}` in <200 ms. (3) parse via `casparser`, validate ISINs, progress 40. (4) upsert `mf_user_holdings` (source='cas'), progress 70, emit `mf.cas.parsed`. (5) `mf.holdings.materialize`: latest NAV from Redis/DB, compute current_value, XIRR, category allocation, overlap. (6) write snapshot, cache report 2 h, progress 100, status done. (7) emit `mf.holdings.updated` → Rating Engine rescore → `scoring.result.published` → `user_fund_scores` upsert. (8) client polls status→report; round trip ≤ 60 s.
**Daily NAV (Celery beat 23:30 IST):** fetch AMFI `NAVAll.txt`, bulk-upsert `mf_nav_history`, refresh Redis, emit `mf.nav.refreshed`, targeted invalidation via `mf:isin_users:{isin}`.
**MF Central / AA (event-driven):** adapter emits `*.holdings.received` → upsert (source) → materialize.
**Beat:** `mf.nav.daily_fetch` 23:30 · `mf.fund.meta_refresh` 02:00 · `mf.batch.rescore` 03:00 · `mf.snapshot.materialize_all` 03:30 · `mf.nav.history_backfill` Sun 04:00.
**Cache-invalidation matrix:** `mf.nav.refreshed`(isin)→`mf:nav:{X}:latest` + holders' snapshots; `mf.holdings.updated`(user)→snapshot/overlap/score; `scoring.result.published`→`mf:score:{U}:{X}`; meta refresh→`mf:fund:{isin}:meta`; manual refresh→snapshot/overlap.

**Scoring integration:** feeds rolling returns, expense ratio, category-relative percentile, portfolio XIRR vs benchmark, overlap concentration, AUM trend to the Rating/Scoring Engine; consumes unified score solely via `scoring.result.published`; stores/serves verb label + confidence verbatim. Never interprets or overrides.

**Failure modes & fallbacks:** source ladder MF Central → AA → CAS → AMFI (NAV-only) via chained Celery tasks (`max_retries=2`, backoff), `mf.datasource.failed` events. Stale cache: NAV falls back to latest `mf_nav_history` row (T-1); snapshots > 2 days flagged `stale`. LLM commentary is non-blocking and SEBI-disclaimer-postfixed at serialization; omitted on failure. CAS parse failure → status=failed, temp file purged at 24 h.

**Build vs partner:** Build in-house (core differentiator; AMFI public, MF Central published API, `casparser` OSS). Only third-party dependency is the non-blocking OpenRouter commentary call. Consistent with Reality Layer §6.

**Provenance:** CAS→60s & data ladder — v2.3 (canonical) reinforced by Reality Layer §4/§1.6 & Master Blueprint; AMFI/TimescaleDB — Master Blueprint + v2.2; scoring contract — v2.2 + v2.3; Redis/TTL/invalidation — v2.3 §10.3; Celery beat — v2.3; SEBI boundary — Reality Layer §1.1 + Master Blueprint; build-vs-partner — Reality Layer §6. **UNIQUE to v2.3:** 60-second SLA, `mf:cas:dedup` hash check, `mf:isin_users:{isin}` reverse index.

### ETF Module

**Phase:** Phase 2 (post-MF stabilization).

**Responsibility & scope:** Extends portfolio intelligence to exchange-traded funds — shares NAV lineage with MFs but trades intraday on NSE/BSE with market-price-vs-NAV spread dynamics. Ingests ETF holdings (AA / broker feed via Market Data Adapter), computes expense ratio, tracking error vs benchmark, ETF↔MF overlap, liquidity score, momentum; feeds the shared Rating/Scoring Engine. Reuses TimescaleDB infra; reads `mf_funds` read-only; owns its own intraday price-feed pipeline.

**Non-goals:** no buy/sell/rebalance; does not own/redefine the unified score (consumes via interface, MF pattern); no intraday trading/order routing/streaming-quote subscription; no MFs/stocks/options handling; does not own broker/AA consent; does not replicate MF metadata (reads `mf_funds`, writes own `etf_metadata`).

**Public interface:** `/api/v1/etf/portfolio/{user_id}`, `/etf/fund/{isin}`, `/etf/fund/{isin}/price/history`, `/etf/portfolio/{user_id}/overlap`, `/etf/portfolio/{user_id}/report`, `POST /etf/portfolio/{user_id}/refresh` (1/h, shared rate-limit namespace with MF). Emits `etf.holdings.updated`, `etf.price.refreshed`, `etf.score.requested`; consumes `aa.holdings.received`, `broker.positions.received`, `scoring.result.published`, `mf.nav.refreshed` (premium/discount recompute).

**Data schema (Postgres):** `etf_metadata` (isin PK, symbol_nse/bse, scheme_name, amc_name, benchmark_index, etf_category, aum_crore, expense_ratio_pct, lot_size, exchange, tracking_error_1y/3y, liquidity_score); `etf_price_history` (TimescaleDB, PK (isin, price_date), OHLC, volume, nav_on_date, premium_discount_pct, source; continuous aggregate `etf_price_monthly_agg`); `etf_user_holdings` (user_id, isin, quantity, avg_cost_price, invested_amount, source ∈ aa|broker|manual; UNIQUE(user_id,isin,source)); `etf_portfolio_snapshots` (user_id, snapshot_date, total_invested, current_value, absolute_return_pct, etf_allocation JSONB, avg_expense_ratio, avg_tracking_error); `etf_user_scores` (UNIQUE(user_id,isin)).
**Redis:** `etf:price:{isin}:latest` 6 h · `etf:meta:{isin}` 24 h · `etf:portfolio:{user_id}:snapshot` 15 m · `etf:overlap:{user_id}` 1 h · `etf:score:{user_id}:{isin}` 30 m · `etf:refresh:ratelimit:{user_id}` 1 h · `etf:isin_users:{isin}` (no TTL).

**Pipeline:** event-driven holdings ingest (filter `instrument_type='ETF'`, fetch metadata if unknown ISIN, upsert, materialize). EOD price `etf.price.daily_fetch` 16:30 IST (NSE→BSE fallback), compute `premium_discount_pct` vs `mf_nav_history`, emit `etf.price.refreshed`. Beat: meta refresh 02:30; tracking-error & liquidity weekly Sun 03:00; `etf.batch.rescore` 03:15. Invalidation matrix parallels MF; `mf.nav.refreshed` triggers premium/discount recompute.

**Scoring integration:** feeds expense ratio, tracking error 1Y/3Y, trailing-30d avg premium/discount, liquidity score, benchmark-relative momentum, ETF↔MF overlap concentration (read-only cross-module DB view). Consumes unified score via `scoring.result.published`.

**Failure modes:** holdings ladder broker→AA→manual; price ladder NSE→BSE→`nav_proxy` (flagged `price_type:"nav_proxy"`); stale flags; tracking error stale-tolerant (`tracking_error_as_of`); commentary non-blocking + disclaimer.

**Build vs partner:** build analytics; thin price-feed integration (free NSE/BSE EOD now; vendor behind adapter later). Reality Layer §6.

**Provenance:** ETF Phase 2 — v2.2/v2.3; analytics — Master Blueprint + v2.2; TimescaleDB reuse — v2.3; cross-module read-only join — Master Blueprint + Ledger; price ladder — Reality Layer; build-vs-partner — Reality Layer §6. **UNIQUE to v2.3:** `etf:isin_users` reverse index, `nav_proxy` flag, shared MF/ETF refresh rate-limit namespace.

### Stock Intelligence Module

**Phase:** Phase 3 (AI engine + explainability); DhanRadar Score on public stock pages from Phase 2; "Why X Moved Today" Phase 3; Track Record page Phase 4. **Owns "Why X Moved Today" (ledger #9).**

**Responsibility & scope:** Ingests price/fundamental/institutional signals for the top-500 NSE universe, runs them through the shared Rating/Scoring Engine, publishes per-ticker analysis + curated daily picks, owns the SWOT engine and "Why X Moved Today" SEO pages. All AI via OpenRouter Gateway; read-only to end users; educational, not trade instructions.

**Non-goals:** no buy/sell or action verb beyond the 4-label taxonomy; no intraday/Greeks/day-trader/tick streaming; no per-user per-stock personalized advice; no order routing/brokerage; does not define scoring (consumes via interface); no Elasticsearch.

**Public interface:** `GET /api/stocks/picks` (anon top-5 no thesis / authed full-10), `/stocks/{ticker}/analysis`, `/stocks/{ticker}/score`, `/stocks/{ticker}/swot`, `/stocks/{ticker}/history`, `/market/movers/{date}/{ticker}` (anon, 24 h), `/market/movers/{date}`, `/track-record` (Next.js ISR). Emits `stock.label_changed` (hysteresis-gated, 2 consecutive evals), `stock.price_threshold_crossed` (>5% day move).

**Data schema:** `stocks` (ticker PK, name, sector, market_cap_cr, exchange, active); `stock_picks` (ticker, pick_date, dhanradar_score, label, confidence_score, confidence_band, bull_target_12m, bear_target_12m, thesis, contributing_signals JSONB, contradicting_signals JSONB, source_reliability_avg, signal_age_hours, model_used, prompt_version; UNIQUE(ticker,pick_date)); `stock_swot`; `pick_outcomes`; `why_moved_today` (ticker, move_date, price_change_pct, ai_explanation, top_signals JSONB; UNIQUE(ticker,move_date)).
**Redis:** `stock:pick:{TICKER}` 7 d (early-invalidate on >5% move / earnings / major news) · `stock:score:{TICKER}` 7 d · `stock:swot:{TICKER}` 30 d (earnings-invalidated) · `stock:why_moved:{TICKER}:{DATE}` 24 h · `stock:movers:{DATE}` 24 h · `stock:label_prev:{TICKER}` 24 h (hysteresis) · `ai:fails:{TICKER}:{DATE}` 24 h · `ai:budget:free|premium:today` (UTC midnight) · `anon:stock:picks` 6 h.

**Pipeline:** (1) price ingest `ingest_stock_prices` 09:30 & 15:35 IST via Market Data Adapter (Upstox primary, Kite fallback), >5% move emits `stock.price_threshold_crossed`. (2) SimHash dedup before any LLM call. (3) signal assembly (7 layers). (4) Rating/Scoring Engine call → score/label/confidence/signals (module never computes score). (5) LLM thesis+SWOT via OpenRouter task `stock_pick`. (6) `StockPickV2` validation: confidence ∈[0,1]; bull ∈[-0.50,2.00]; bear ∈[-0.80,1.00]; bear<bull; conf>0.7⇒≥3 contributing; thesis 50–500 chars; contributing 2–10. (7) hysteresis gate vs `stock:label_prev`. (8) write Postgres + Redis 7 d. (9) `generate_swot_batch` weekly Sun 02:00, earnings-invalidated, `swot_engine`→`deepseek-chat-v3:free`, cache 30 d. (10) "Why X Moved" post-close 16:00 top-50 movers, `deepseek-v3`, 24 h, Next.js ISR. (11) `compute_pick_outcomes` nightly 01:00 → `pick_outcomes` vs NIFTY 50.
**Beat:** `ingest_stock_prices` 09:30/15:35 · `run_stock_batch` 16:30 (~500 LLM/day) · `generate_why_moved` 16:00 · `generate_swot_batch` Sun 02:00 · `compute_pick_outcomes` 01:00.

**Scoring integration:** assembles 7 signal layers → `SignalBundle` → Rating/Scoring Engine; stores returned `dhanradar_score`/`label`/`confidence_score`/signals verbatim; `confidence_band` derived as a pure read (≥0.7 high / ≥0.4 medium / <0.4 low) for Track-Record grouping only.

**Failure modes:** validation fail → jitter retry → `ai:fails` 3-strike skip (serve stale ≤7 d or `analysis_unavailable`); 429 → round-robin model; free budget exhausted → Sonnet spillover (stock_pick only, ≤$0.50/day) → premium exhausted → cached/unavailable + Prometheus alert; Upstox down → circuit-breaker → Kite → stale prices flagged; >5% universe label-flip → hold + human-review gate.

**Build vs partner:** build entirely (core IP, explainability moat, Track Record trust); data source partnered behind Market Data Adapter.

**Provenance:** phases — v2.2 P2/P3 + v2.3 §10.11; `StockPickV2`/`QualityValidator`/Redis/TTL/round-robin/spillover — v2.3 §10.3; "Why X Moved" — v2.2 R20; Track Record/`pick_outcomes` — v2.2 Rec 7; hysteresis & label-flip gate — Reality Layer §5.1/§5.2; adapter — v2.2 Rec 5 + v2.3 §10.7; taxonomy — Reality Layer §3.1; SEBI boundary — v2.2 Part VII + Reality Layer §1.1. **UNIQUE:** explicit "Why X Moved" → Stock module ownership (ledger #9).

### News Tagging & Summary Module

**Phase:** Phase 3 (ingestion infra from Phase 2).

**Responsibility & scope:** Ingests financial news feeds, applies Bloom-filter + SimHash dedup *before any LLM call*, tags articles with tickers/sectors/sentiment/source-reliability/signal-type, generates concise AI summaries. Publishes tagged records consumed by Stock Intelligence (cache invalidation/signal enrichment) and Mood Compass (`news_sentiment` 6 % input). Enforces the Source Reliability weight hierarchy. Produces no picks/scores/views.

**Non-goals:** no buy/sell framing; no intraday/tick news; no sentiment→trade pipeline (sentiment is an input to the Rating Engine via interface only); no Greeks; social/Twitter is tier-3 (0.20) contradicting-only; no proprietary content redistribution beyond fair-use summaries.

**Public interface:** `GET /api/news`, `/news/{article_id}`, `/news/ticker/{ticker}`, `/news/sector/{sector}`, `/news/today-summary` (anon). Emits `news.tagged:{TICKER}`, `news.major_event:{TICKER}` (high-tier source + |weighted_score|≥0.6 → Stock cache invalidation), `news.sentiment_batch_ready:{DATE}` (→ Mood Compass).

**Data schema:** `news_articles` (url UNIQUE, url_hash, simhash, title, source_domain, published_at, source_tier, source_weight, raw_body_r2_key, summary, summary_model); `news_tags` (article_id, tag_type ∈ ticker|sector|macro_event|signal_type, tag_value, confidence); `news_sentiment` (article_id PK, overall_score [-1,1], bullish/bearish JSONB, weighted_score = overall×source_weight); `source_reliability` (domain PK, tier, weight, category, last_reviewed).
**Redis:** `news:hash:{SHA256}` 7 d (exact-URL dedup) · `news:simhash_bloom` (persistent BITFIELD Bloom) · `news:summary:{article_id}` 24 h · `news:ticker_feed:{TICKER}` 24 h · `news:sector_feed:{SECTOR}` 24 h · `news:today_summary` 24 h · `news:sentiment_daily:{DATE}` 48 h.

**Pipeline:** `ingest_news_feeds` every 4 h (06/10/14/18 IST). Exact dedup (SHA-256 vs Redis) → near-dup (SimHash Hamming ≤3 vs Bloom, ~1 % FP accepted) → source-reliability tag (unknown→low 0.20) → batched LLM tag+summary (≤10 articles/call, `news_summary`→Llama 3.3 70B free) → `NewsSummaryV1` validation (summary 50–250; sentiment [-1,1]; ticker tags validated vs `stocks`; `AIOutputBase` rules) → persist tags/sentiment → invalidate `news:ticker_feed`; high-tier + |weighted|≥0.6 → `news.major_event` → Stock invalidates `stock:pick`. `aggregate_daily_sentiment` 08:45 IST → `news:sentiment_daily` for Mood Compass. `generate_news_digest` 07:30 IST (Sonnet spillover). 3-strike skip per (domain,date).

**Scoring integration:** no Rating Engine call; produces `weighted_score` signals the engine *may* consume as the sentiment layer, and the `news_sentiment` daily aggregate Mood Compass consumes (6 %).

**Failure modes:** hallucinated ticker → reject tag + retry + 3-strike; domain 3-strike → raw ingest only (`summary:null`); 429 → round-robin (batch non-time-critical); free budget exhausted → raw ingest + cached summaries; feed down → skip source; `news.major_event` fanout capped at 20 invalidations/cycle.

**Build vs partner:** build pipeline; partner feed sources (RSS/announcement APIs); `source_reliability` table is published-methodology IP.

**Provenance:** dedup — v2.3 §10.3 + v2.2 P2; TTLs — v2.3 §10.3; Source Reliability + `AIOutputBase` — v2.2 Rec 3; news_sentiment 0.06 — v2.2 Rec 2; Sonnet digest spillover — v2.3 §10.3; 3-strike — v2.3 §10.3; SEBI — v2.2 Part VII + Reality Layer §1.1. **UNIQUE:** 7-day hash window; `news.major_event` event-contract name.

### Search Module

**Phase:** Phase 2 (FTS setup) → Phase 3 (LLM semantic rerank).

**Responsibility & scope:** Unified search across stocks/MFs/ETFs/sectors/news via Postgres GIN `tsvector` + `pg_trgm` typo-tolerant matching, plus lightweight LLM semantic reranking for ambiguous/educational queries. Owns query-hash caching and natural-language→structured-filter interpretation. No Elasticsearch, no external search SaaS. No server-side user search history in Phase 1.

**Non-goals:** no real-time search; no buy/sell framing in results/interpretation; no intraday screener; no Greeks/derivatives/options-chain; no Phase-1 search-history persistence; no Elasticsearch.

**Public interface (pure read-only consumer, emits no events):** `GET /api/search?q=&type=&page=`, `/api/search/suggest?q=` (<50 ms, no LLM), `/api/search/interpret?q=` (Pro), `/api/search/news?q=&from=&to=`.

**Data schema:** generated `search_vector tsvector` columns (weighted A/B/C) + GIN indexes on `stocks`/`mutual_funds`/`news_articles`; `pg_trgm` GIN on names/tickers; `search_queries` audit (query_hash, query_text [30-day DPDP purge], entity_types[], result_count, cache_hit).
**Redis:** `search:cache:{HASH}` 24 h · `search:suggest:{PREFIX}` 1 h · `search:interpret:{HASH}` 24 h · `search:popular` 6 h.

**Pipeline:** normalize → SHA-256 → `search:cache` check (dominant path). Miss → per-type FTS (`websearch_to_tsquery`, `ts_rank`); typeahead via `pg_trgm` similarity. Enrich snippets by reading `stock:pick:{TICKER}` / `mf:pick:{SCHEME_CODE}` from Redis (cold cache → `score:null`, never blocks). Ambiguous query + budget available → LLM rerank (`search`→Llama 3.3 70B free), `SearchRerankedV1` validation (reranked_ids must be a permutation; entities must exist). Pro `/interpret` → structured filter (cached 24 h) handed to Screener. Write `search:cache` 24 h. `prewarm_search_cache` 06:00 IST (top-50 popular). `purge_old_search_logs` Sun 03:00 (DPDP 30-day). No event-driven invalidation (24 h TTL aligned to slowest entity cadence).

**Scoring integration:** none; pure consumer of Rating-Engine outputs via other modules' Redis caches; search latency intentionally decoupled from scoring latency.

**Failure modes:** rerank validation fail → FTS-only + 3-strike; 429/budget exhausted → FTS-only (no premium; non-critical path); FTS timeout >500 ms → partial results `partial:true`; `pg_trgm` missing → prefix `LIKE`; Redis down → direct FTS, no cache; prewarm fail → first query takes miss path.

**Build vs partner:** build (Postgres GIN + `pg_trgm`; v2.3 canonical "no Elasticsearch"); LLM via existing gateway.

**Provenance:** FTS P2 / LLM P3 — v2.2 P2 + v2.3 §10.7; no-ES — v2.3 §10.2; `search:cache` 24 h + 50 free reqs/day + Llama — v2.3 §10.3; DPDP purge — Reality Layer §1.2; SEBI — v2.2 Part VII + Reality Layer §1.1. **UNIQUE:** prewarming pattern; explicit pick-cache enrichment flow; `pg_trgm` typeahead choice.

### Portfolio Intelligence Module

**Phase:** Phase 5 (Pro launch); AA integration begins in parallel in Phase 2.

**Responsibility & scope:** Ingests holdings via MF Central → AA → CAS PDF → manual (+ broker OAuth read-only for equities) and produces unified portfolio analytics: sector allocation, diversification score, portfolio overlap, XIRR vs NIFTY, max drawdown. Read-only analytics only; never holds/transmits/acts on trading intent. Pro/Pro+ gated; consumes the unified score by interface only.

**Non-goals:** no order placement/routing/brokerage; no auto-rebalancing/advisory baskets/model portfolios; no broker write-back; no per-security buy/sell; no social/peer comparison; no screen-scraping (AA framework only); not an RIA substitute (educational analytics label).

**Public interface:** `POST /api/v1/portfolio`, `GET /portfolio/{id}`, `POST /portfolio/{id}/sync`, `GET /portfolio/{id}/analytics`, `GET /portfolio/{id}/overlap`, `GET /portfolio/{id}/report-card` (R19 OG PNG via celery-misc), `DELETE /portfolio/{id}` (DPDP erasure cascade). Internal events `portfolio.snapshot.daily`, `portfolio.cas_parse.requested`, `portfolio.aa_consent.granted`, `portfolio.broker_sync.scheduled`. Consumes Rating Engine `GET /internal/v1/score/{instrument_type}/{identifier}` (annotation only).

**Data schema:** `portfolios` (user_id, name, source, broker, sync_enabled, aa_consent_id, last_synced); `portfolio_holdings` (portfolio_id, instrument_type, ticker, isin, scheme_code, quantity, avg_buy_price, buy_date, current_value; UNIQUE(portfolio_id,isin), CHECK ticker|isin); `portfolio_snapshots` (portfolio_id, snapshot_date, total_value, invested_value, unrealised_pnl GENERATED, sector_allocation JSONB, top_holdings JSONB, diversification_score, xirr, max_drawdown, benchmark_xirr, overlap_cache JSONB; UNIQUE(portfolio_id,snapshot_date)).
**Redis (`port:`):** `port:analytics:{id}` 24 h · `port:overlap:{id}:{other}` 7 d · `port:cas_status:{job}` 1 h · `port:aa_consent:{user}` (=consent expiry) · `port:report_card:{id}` 24 h · `port:xirr_cashflows:{id}` 7 d.

**Pipeline:** event-driven ingest (MF Central pull Y2; AA on consent; CAS via pdfplumber+regex ~80 % accuracy, unmatched → manual confirm; manual POST; broker OAuth nightly via adapter). Daily snapshot `18:30 IST` (current prices via adapter; sector allocation; diversification; XIRR if ≥2 cashflows; max drawdown trailing 365 d; benchmark XIRR vs NIFTY 50 TRI). Overlap on-demand + weekly Sun 03:00. Share-card render → celery-misc Pillow 1200×630 → R2. Invalidation: holdings upsert → analytics/xirr/overlap; snapshot → analytics; AA revoked → consent + stale flag; broker token expiry → stale + notify.

**Scoring integration:** consumes unified score/label per security via Rating Engine interface; computes *portfolio-level* analytics locally (inverse-HHI diversification; Jaccard overlap; XIRR via `numpy_financial` + `scipy.brentq`; max drawdown via `numpy` accumulate). Concentration warning when any sector > 40 %.

**Failure modes:** CAS ~80 % → manual confirm + partial compute; AA revoked → stale banner; broker token expiry → skip + alert + notify; MF Central down → ladder failover; XIRR non-convergence → null; price feed down at snapshot → carry-forward stale + 30-min retry; numpy/scipy hard dependency (fail-fast).

**Build vs partner (Reality Layer §6):** CAS parser=build; AA=partner (Setu preferred); broker OAuth=build via adapter; MF Central=partner/apply early; KYC=partner; portfolio math=build.

**Provenance:** schema — v2.2 Rec 4 (isin column UNIQUE); formulas — v2.2 Rec 4 (expansions UNIQUE); ladder — Reality Layer §1.6 + v2.2 Rec 4; build-vs-partner — Reality Layer §6; R19 — v2.2 R19; infra — v2.3 §10.2/§10.8; Phase 5 + Pro gate — v2.2 Part IV/VI. **UNIQUE:** 40 % concentration threshold; `port:` TTLs; R2+celery-misc share-card routing.

### Track-Record / Backtest Module

**Phase:** Phase 4 (public `/track-record` ships before the Pro gate — acquisition/trust mechanic, not a Pro feature).

**Responsibility & scope:** Records verifiable outcomes for every published pick, computes realised 30/90/365-day returns vs NIFTY 50, exposes them on a fully anonymous public page. Append-only and auditable — no record modified after the window closes. Secondary: a Pro+-gated backtesting harness replaying a saved screener query against history. Pure consumer/recorder of `stock_picks`.

**Non-goals:** no buy/sell (historical fact, not guidance); no paper trading; no future-from-past prediction (mandatory "past performance" disclaimer); no per-user track record; no user-portfolio backtesting; no intraday/options backtest; not SEBI-regulated research.

**Public interface:** `GET /api/v1/track-record`, `/track-record/band/{band}`, `/track-record/sector/{sector}`, `/track-record/picks?limit=&offset=`, `/track-record/og-image` (R19), `POST /api/v1/backtest/run` (Pro+), `GET /api/v1/backtest/{job_id}` (Pro+). Events: `outcomes.nightly.record` (Beat 00:30 IST), `outcomes.pick.published` (consumed from AI Enrichment → stub row, returns NULL).

**Data schema:** `pick_outcomes` (pick_id FK ON DELETE RESTRICT, ticker, sector, pick_date, confidence_band, price_at_pick, price/return/benchmark_return/beat for 30d/90d/365d, outcome_recorded_at; partial indexes on pending windows); `track_record_cache` (period_days∈{30,90,365}, confidence_band, sector, pick_count, beat_count, hit_rate, avg_return, avg_benchmark, avg_alpha; UNIQUE(period,band,sector)).
**Redis (`tr:`):** `tr:summary` 6 h · `tr:band:{band}:{period}` 6 h · `tr:sector:{sector}:{period}` 6 h · `tr:picks:page:{offset}` 1 h · `tr:og_image:weekly` 24 h · `tr:backtest:{job_id}` 7 d.

**Pipeline:** stub creation on `outcomes.pick.published` (band mapped ≥0.7/0.4 from `confidence_score`, `price_at_pick` back-filled EOD). Nightly recorder 00:30 IST uses partial indexes for due windows, fetches close + NIFTY 50 TRI, computes return/benchmark/beat, atomically rebuilds `track_record_cache`, invalidates `tr:*`. Public page Next.js SSR 6 h ISR, fully anonymous (`anon:` namespace), mandatory disclaimer + methodology link; cohorts < 30 picks hidden ("Insufficient data"). Weekly OG card Sun 07:00 → R2. Pro+ backtest: enqueue `run_backtest_task` (celery-batch, low priority), replay screener over history, limits (≤5 yr, ≤10 filters, 120 s timeout), cache 7 d.

**Scoring integration:** no query-time Rating Engine call; `confidence_band` frozen at publication from `stock_picks.confidence_score`; never re-scored retroactively (auditability).

**Failure modes:** adapter down → skip + retry next night (no partial writes); missing NIFTY date → nearest preceding (`benchmark_date_adjusted`); job > 30 min → alert + atomic rollback + resume; cache rebuild fail → stale `tr:summary` + staleness timestamp; backtest timeout → `{status:timeout}`; cohort < 30 → hidden; `ON DELETE RESTRICT` prevents orphaned outcomes.

**Build vs partner:** build (core trust IP); historical/benchmark prices via Market Data Adapter; OG render reuses Portfolio pattern.

**Provenance:** `pick_outcomes` — v2.2 Rec 7; public page/last-100 — v2.2 Rec 7; R19 — v2.2 R19; acquisition-before-Pro — v2.2 Finding 7; backtest Pro+ — v2.2 Part IV; disclaimer — v2.2 Rec 9 + SEBI. **UNIQUE:** `beat_*` booleans, `track_record_cache`, 00:30 IST cadence, 30-pick floor, append-only `ON DELETE RESTRICT`, `tr:` TTLs.

### Mood Compass Module

**Phase:** Phase 2 — acquisition magnet; anonymous-accessible; ships before auth/Pro.

**Responsibility & scope:** Twice-daily regime score (0–100) over 11 weighted macro/market inputs, classified into 5 buckets, with a Sonnet-class plain-English commentary. Owns `market_mood` + `mood:*` Redis. Does NOT deliver WhatsApp/Telegram (Notification module subscribes to `mood.snapshot.published`).

**Non-goals:** no buy/sell/advice; not an input to per-security DhanRadar Score (separate concept/contract); no hallucinated commentary (withheld if <7 inputs); raw inputs shown as evidence not directives; does not own Historical Analogue (AI Enrichment consumes `mood_history`).

**Public interface (anon):** `GET /api/v1/market/mood`, `/market/mood/history` (≤365 d), `/market/why-today` (12 h), `/market/mood/embed`. Emits `mood.snapshot.published {snapshot_date,mood_score,regime,confidence_score}`.

**Data schema:** `market_mood` (snapshot_date PK, snapshot_time, mood_score 0–100, regime, confidence_score, inputs_available, input_vector JSONB, contributing_factors JSONB, contradicting_factors JSONB, ai_commentary, model_used); `mood_history` (snapshot_date PK, mood_vector `vector(11)` pgvector ivfflat cosine, mood_score, regime) — populated by trigger, consumed by AI Enrichment analogues.
**Redis:** `mood:latest` 12 h · `mood:why-today` 12 h · `mood:history:{from}:{to}` 1 h · `mood:embed` 12 h · `ai:budget:*` (UTC midnight).

**Pipeline:** Celery `mood` queue `compute_mood_snapshot` at **09:00 & 16:00 IST** (`crontab` 03:30 & 10:30 UTC) — *ledger #6*. Ingest 11 signals via Market Data Adapter, normalize 0–1, missing→NULL (decrement `inputs_available`). Weighted score = Σ(input·w)/Σ(available w)·100; weights: nifty_trend .15 · market_breadth .12 · india_vix .10 · fii_flows .10 · global_indices .10 · dii_flows .08 · us_bond_10y .08 · oil_brent .07 · usd_inr .07 · put_call_ratio .07 · news_sentiment .06 (Σ=1.00). Buckets: extreme_fear [0–19] · fear [20–39] · neutral [40–59] · greed [60–79] · extreme_greed [80–100]. Contributing vs contradicting factors stored (disagreement disclosure mandatory). Commentary `mood_commentary`→Claude Sonnet (premium spillover; skipped if premium ≥ $0.50/day, score still published). `MoodSnapshot(AIOutputBase)` validation, one Sonnet retry, second fail → write without commentary. Persist → trigger populates `mood_history` → emit event → invalidate `mood:latest/why-today/embed`.

**Scoring integration:** the regime score is **explicitly distinct** from the per-security DhanRadar Score; not an input to security rankings in v2.2/v2.3 scope (future integration requires an explicit interface change).

**Failure modes:** 1–4 inputs missing → rescaled score, lower confidence, note; ≥5 missing (`inputs_available`<7) → confidence ≤0.40, commentary withheld, `data_quality:degraded`; all missing → skip+retry 30 min, cache extended; invalid news_sentiment → 10-input fallback + 3-strike; Sonnet validation fail → write w/o commentary; premium exhausted → no commentary, no user-facing degradation; Beat miss → restart recovery, >6 h gap → Prometheus alert.

**Build vs partner:** build entirely (primary public differentiator; inputs via in-house Market Data Adapter).

**Provenance:** 11 inputs/weights/buckets, `market_mood`, 9 AM/4 PM cadence — v2.2 Rec 2 (canonical; cadence reconciled vs v2.3 "2× daily" — ledger #6); `mood_history`/vector — v2.2 Rec 10; Sonnet spillover + 12 h TTL — v2.3 §10.3; SEBI/no-hallucination/confidence-floor — Reality Layer §5.1/§5.2 + Master Blueprint. **UNIQUE:** extra `market_mood` columns; `mood_history` DDL; `mood.snapshot.published` shape.

### Signal & Source-Reliability Module

**Phase:** Phase 2 (ships with Mood Compass; applies to all AI outputs from Phase 3 via `AIOutputBase`).

**Responsibility & scope:** Maintains the canonical source-reliability registry (3 tiers, seeded at deploy), enforces multi-signal confidence rules on every AI output, and provides the `AIOutputBase` Pydantic schema all AI services must extend. Validates/annotates; does not generate content. Owns `source_reliability` and the `AIOutputBase` contract.

**Non-goals:** no news ingestion/scraping; no runtime-dynamic source scoring (tiers updated only via migration + human review — SEBI changelog); no user-facing content; hallucination-prevention at prompt level is the Gateway's job (this validates structured output post-generation); not applied to anonymous metadata.

**Public interface:** `GET /api/v1/admin/source-reliability`, `PUT /api/v1/admin/source-reliability/{domain}` (writes audit + cache clear). True coupling surface = the shared `AIOutputBase` schema imported by all AI-output services: `StockPickV2`, `MFPickV2`, `MoodSnapshot`, `NewsSummary`, `SWOTOutput`, `EarningsSummary`, `WhyTodayOutput`. No AI output bypasses it.

**`AIOutputBase` contract:** `confidence_score∈[0,1]`; `contributing_signals` (≥2, each Signal{source_domain, description, age_hours, reliability_tier∈{high,medium,low}, reliability_weight∈[0,1]}); `contradicting_signals`; `signal_age_hours`; `source_reliability_avg`. Validators: `confidence>0.7 ⇒ ≥3 contributing signals`; `source_reliability_avg` must equal mean of signal weights ±0.05.

**Data schema:** `source_reliability` (domain PK, tier CHECK, weight CHECK [0,1], category ∈ regulator|filing|journalist|social|ai_derived, last_reviewed, updated_by, notes). Seed (canonical v2.2 Rec 3, extended): rbi.org.in/sebi.gov.in/bseindia.com/nseindia.com/federalreserve.gov = high 1.00; amfiindia.com high 0.95; economictimes.com 0.65 / moneycontrol.com/livemint.com/businessstandard.com 0.60 = medium; twitter.com 0.20 / reddit.com 0.15 / news_sentiment_ai 0.20 = low. Tier weights: high 1.0 / medium 0.6 / low 0.2.
**Redis:** `source_reliability:registry` 24 h (invalidated on admin PUT).

**Pipeline:** seed at deploy (idempotent ON CONFLICT). On every AI call, `QualityValidator.validate_or_skip()` instantiates the right `AIOutputBase` subclass; failure increments `ai:fails:{ticker}:{today}`, 3 strikes → skip. `confidence>0.7 ⇒ ≥3 signals` enforced in Pydantic (not prompt). Gateway resolves each signal domain vs cached registry → weight → average injected pre-validation; unknown → low 0.20 + admin-review log. Admin PUT → DB + `ai_recommendation_audit` (`source_reliability_update`) + registry cache invalidation.

**Scoring integration:** `source_reliability_avg` surfaces in "Why this ranking"; `confidence>0.7 ⇒ ≥3 signals` structurally prevents high-confidence low-coverage outputs. Tier weights 1.0/0.6/0.2.

**Failure modes:** unknown domain → low 0.20 + alert; registry miss → DB fallback; schema rejection → 3-strike skip, alert if >10 % batch fails; high-conf <3 signals → hard reject → Sonnet spillover (stock_pick/mf_pick) or skip; admin PUT fail → rollback; >5 % label churn → human-review gate.

**Build vs partner:** build entirely (core to explainability positioning).

**Provenance:** 3-tier framework + seed + `AIOutputBase` + `confidence>0.7⇒≥3` — v2.2 Rec 3 (canonical); `QualityValidator` 3-strike + `StockPickV2` bounds — v2.3 §10.3; human-review gate — Reality Layer §5.2. **UNIQUE:** extended seed rows; `Signal` sub-model + cross-validator; `source_reliability:registry` key; admin endpoints; `updated_by` audit column.

### AI Enrichment Module

**Phase:** SWOT/Earnings/Why-Today/Explainability Phase 3; Historical Analogue Phase 2 (consumes Phase-2 `mood_history`).

**Responsibility & scope:** Four enriched surfaces — SWOT (free model, monthly TTL + earnings invalidation, *ledger #7*), Earnings-call summary (Sonnet, 24 h post-results), Historical Analogue (cosine similarity on 11-dim mood vectors, no LLM), "Why this ranking" (deterministic factor decomposition + optional LLM prose). All anonymous-accessible/cached; all LLM via OpenRouter Gateway + `AIOutputBase`. Mood/earnings/analogue WhatsApp delivery belongs to Notification (events only). References — not owns — "Why X Moved Today" (Stock module owns it, ledger #9).

**Non-goals:** no buy/sell (descriptive education); no hallucination (cite structured signals; withhold on validation fail); no hidden uncertainty (mandatory `contradicting_signals`); does not redefine/feed the Rating Engine (consumes its factor outputs to explain, never alters); analogue is historical fact not forecast; does not own Notification delivery.

**Public interface (anon):** `/api/v1/stocks/{ticker}/swot` (30 d, earnings-invalidated), `/stocks/{ticker}/earnings-summary[/{quarter}]`, `/market/analogues[/{date}]`, `/stocks/{ticker}/why-ranking`, `/mf/{scheme_code}/why-ranking`, `/market/movers/{date}/{ticker}` (content owned by Stock module; AI Enrichment populates). Emits `ai.swot.published`, `ai.earnings.published`, `ai.analogue.found` (→ Notification).

**Data schema:** `stock_swot` (ticker, snapshot_date, S/W/O/T JSONB, confidence_score, source_reliability_avg, contributing/contradicting JSONB, model_used, prompt_version, valid_until; UNIQUE(ticker,snapshot_date)); `earnings_summaries` (ticker, quarter, results_date, headline, key_highlights JSONB, management_tone, guidance_summary, risk_flags JSONB, …; UNIQUE(ticker,quarter)); `historical_analogues` (query_date, analogue_date, similarity_score, rank, what_happened_30d/90d/365d, context_label; UNIQUE(query_date,rank)).
**Redis:** `swot:{ticker}` 30 d · `earnings:{ticker}:latest` (=next earnings) · `earnings:{ticker}:{quarter}` permanent · `analogues:today` 12 h · `analogues:{date}` 7 d · `why-ranking:stock|mf:{id}` 24 h · `why-today:{date}:{ticker}` 24 h.

**Pipeline:** **SWOT** — Beat weekly Sun 02:00 + `ai.earnings.published`-triggered regen; inputs (fundamentals, 30-day reliability-filtered news, Rating-Engine factor breakdown); `swot_engine`→`deepseek-chat-v3:free`; `SWOTOutput(AIOutputBase)` validate; cache 30 d (ledger #7). **Earnings** — adapter hourly announcement poll → `generate_earnings_summary` (+30 min) → `earnings_summary`→Claude Sonnet (premium; if exhausted, queue next-day + placeholder); validate; emit `ai.earnings.published`; invalidate `swot:{ticker}`. **Analogue** — Beat 10:00 IST (after 09:00 Mood run); cosine similarity of today's `mood_vector` vs `mood_history` excluding last 180 d; top-3; persist + emit `ai.analogue.found`; mandatory historical-only disclaimer at serializer. **Why-ranking** — on-demand, deterministic decomposition (`contribution = factor_weight × normalised_value`, sorted by |contribution|); optional Pro LLM prose (`why_ranking_explainer`→Llama free); Redis-only, no table.

**Scoring integration:** none alter scores. SWOT/Earnings enforce `AIOutputBase`; Earnings gets ≥1 high-reliability filing source (confidence up to 0.85). Analogue is zero-LLM cosine on the 11-dim vector; similarity shown as % ; Why-ranking is a deterministic decomposition of the Rating Engine's output.

**Failure modes:** SWOT 3-strike → skip + stale 30 d cache + alert >10 %; earnings Sonnet exhausted → next-day + placeholder; earnings transcript missing → press-release-only, confidence ≤0.60; analogue <180 d history → empty + `insufficient_history`; all similarity <0.50 → top-3 + `low_similarity_warning`; why-ranking stale → cached + `data_age_hours`; analogue Redis miss → recompute on demand (<200 ms, ~5,475 rows).

**Build vs partner:** build entirely (shared Gateway; analogue pure compute; explainability deterministic).

**Provenance:** SWOT R16 (weekly+Sonnet) reconciled to v2.3 monthly+free (ledger #7); Earnings R17 + v2.3 routing; Analogue algorithm — v2.2 Rec 10; "Why this ranking" — v2.2 Rec 6; TTLs/routing — v2.3 §10.3; Notification separation — Ledger; SEBI/no-hallucination — Reality Layer §5.1/§5.2. **UNIQUE:** SWOT/earnings/analogue DDL; backend endpoint paths; historical disclaimer text; `ai.*` event shapes.

### Alert & Weekly Digest Module

**Phase:** Retention phase.

**Responsibility & scope:** Decides *what* alerts fire and *when* and assembles the weekly digest narrative; monitors portfolio/fund-event/score-change streams; applies dedup, quiet-hours, hysteresis; emits structured events to the Notification module (which owns channel/format). Never sends messages itself.

**Non-goals:** does not send messages (emits events); no buy/sell; does not own Rating Engine (consumes via interface/events); no transport-layer credentials/retry; no rebalancing/SIP scheduling; digest is informational not advice.

**Public interface:** emits `alert.fund_event_fired`, `alert.score_transition_fired`, `digest.weekly_ready`, `alert.concentration_breach`; consumes `rating_engine.score_updated`, `mf_data.fund_event`, `portfolio.holdings_snapshot`, `market_mood.mood_updated`; internal admin/debug REST (`/internal/alerts/*`, `/internal/digest/*`).

**Data schema:** `alert_subscriptions` (user_id, alert_type, severity_floor, is_active; UNIQUE(user_id,alert_type)); `digest_preferences` (user_id PK, delivery_day, delivery_hour_ist, sections_enabled JSONB, sector_interests[]); `alert_dedup_log` (dedup_key UNIQUE, fired_at, expires_at); `digest_records` (digest_id PK, user_id, week_start_date, sections JSONB, delivery_status; UNIQUE(user_id,week_start_date)); `fund_event_log` (fund_id, event_type, event_meta JSONB, detected_at, alert_fired).
**Redis:** `alert:dedup:{user}:{key}` 24 h · `alert:quiet_hour:{user}` dynamic · `digest:assembled:{user}:{week}` 8 d · `digest:lock:{user}:{week}` 10 m · `score:last_seen:{fund}:{user}` 30 d · `fund_event:seen:{fund}:{type}` 7 d.

**Pipeline — real-time:** consumer subscribes to score/fund-event/holdings events → hysteresis gate (accept label transition only when upstream `eval_seq` reflects 2 consecutive evals; log+skip otherwise) → severity classification (HIGH: Sell→Buy or AUM drop >30 %; MEDIUM: adjacent transition / manager change; LOW: style drift / minor drawdown) → dedup (`sha256(user+type+fund+severity+utc_day)`) → quiet-hour gate (10 PM–7 AM IST, defer to `alerts.deferred` ETA 7 AM) → subscription/severity-floor filter → emit to Notification (`notification_dispatch`) + write dedup. Concentration alert synchronous on holdings snapshot (any category >60 %, or 8th same-category fund with overlap ≥50 %). Fund-event catalogue: manager change (HIGH), AUM ±≥30 %/30 d (drop HIGH/rise LOW), style drift ≥0.4 (MEDIUM), drawdown ≤−10 % (HIGH), SEBI circular (HIGH).
**Pipeline — weekly digest:** Beat `assemble_all_digests` Sun 03:30 IST → fan-out per active user (celery_batch) → Redis lock → 5 sections (top-3 movers by |score_delta| 7 d; mood delta sentence; top new pick in user sectors; concentration alert if breached; 1 rotating pre-authored explainer) → persist `digest_records` pending → emit `digest.weekly_ready` at user's window (default Sun 09:00 IST). Beat maintenance: quiet-hour set 22:00 / clear 07:00; dedup prune 01:00.

**Scoring integration:** consumes `rating_engine.score_updated` only (engine owns computation); caches last-seen label per (fund,user) for deltas; gates on `eval_seq ≥ 2` hysteresis.

**Failure modes:** Notification delivery fail → backoff 30 s/2 m/10 m, 3× then `failed` + page; assembly timeout 90 s → retry+300 s → skip-week + metric; dedup Redis down → Postgres fallback → both down → suppress (fail-closed); quiet-hour key missing → assume quiet + UTC time check; Beat overlap → Redis lock; events older than 24 h → audit only, no user alert.

**Build vs partner:** build in-house (Telegram/email free at scale; delivery in Notification module).

**Provenance:** digest sections + Sunday 9 AM — v2.2 Rec 8; fund-event triggers — Reality Layer; hysteresis — v2.2 Rec 14 + Master Blueprint; queues — v2.3. **UNIQUE:** quiet-hour Redis lifecycle, fail-closed dedup fallback, 60 % concentration threshold (Reality Layer §3.4).

### Behavioral Nudge Module

**Phase:** Conversion phase.

**Responsibility & scope:** Detects anxiety/FOMO/confusion/over-concentration signals and delivers timely *educational coaching* nudges (never advice). Owns signal→nudge mapping + timing; Notification owns delivery. Nudges are one-way, async, non-prescriptive, pre-authored copy (no runtime LLM).

**Non-goals:** does not send messages; no buy/sell/switch/redeem recommendation; coaching not regulated advice; does not own/modify portfolio (reads via events); does not score; no A/B infra (may emit variant IDs); no runtime LLM personalization.

**Public interface:** emits `nudge.triggered`; consumes `user_interaction.portfolio_viewed|fund_searched|fund_add_attempted|redemption_attempted`, `portfolio.holdings_snapshot`, `market_mood.mood_updated`; internal `/internal/nudges/*` (staging test-fire).

**Data schema:** `user_behaviour_signals` (user_id, signal_type, signal_meta JSONB, recorded_at; append-only); `nudge_dedup_log` (dedup_key UNIQUE); `nudge_rules` (rule_id PK, is_enabled, trigger_params JSONB, dedup_window_h, priority); `nudge_templates` (nudge_type PK, title/body templates with `{{param}}`, learn_more_url); `nudge_audit_log` (user_id, rule_id, nudge_type, suppressed, suppress_reason).
**Redis:** `nudge:signal:portfolio_views:{user}` 25 h counter · `nudge:dedup:{user}:{type}` dynamic · `nudge:cooldown:{user}` 4 h (max 2/4 h) · `nudge:redemption_flag:{user}:{fund}` 48 h · `nudge:rule_config_cache` 5 m.

**Pipeline:** consumer (celery_misc) persists raw signal (<5 s) → enqueue rule eval (2 s batch). Rules (Reality Layer §3.4): `anxiety_check_frequency` (>5 portfolio views/24 h while mood Fearful/Cautious); `overlap_add` (`overlap_pct≥0.67` AND category reaches ≥8 funds); `fomo_search` (query ∈ DB-editable `fomo_keywords` e.g. "best fund 2026"); `redemption_drawdown` (`current_drawdown_pct≤−10`, sets 48 h flag). Then dedup → cooldown (delay not drop) → quiet-hour (shared 10 PM–7 AM, defer ETA 7 AM) → template render (param substitution, no LLM) → emit `nudge.triggered` + write dedup + audit. Reactive (no Beat for firing); Beat maintenance only (dedup prune 02:00, rule-cache warm).

**Scoring integration:** not a primary trigger; may read current label via Rating-Engine read endpoint for template context; score transitions are Alert module's domain; engine unavailable → omit score context (graceful).

**Failure modes:** consumer lag → signals still persisted, counters accurate; Redis counters down → Postgres count fallback; Notification backpressure → backoff then drop + metric; dedup Redis down → Postgres → both down → suppress (fail-closed); template missing → no malformed nudge + alert; FOMO list stale → DB-editable, no deploy.

**Build vs partner:** build in-house (threshold evaluator; pre-authored copy; only external dep is internal Notification).

**Provenance:** four trigger rules — Reality Layer §3.4; conversion phase — v2.2 Rec 12; real-time cadence — Reality Layer; `user_behaviour_signals` — Reality Layer §3.4 / v2.2 Rec 12; educational-not-advice — v2.2 Rec 12; queues — v2.3. **UNIQUE:** full schema + `signal_meta` JSONB, per-rule Redis counters, 4 h/2-nudge cooldown, DB-editable FOMO list.

## C-Global / Shared Modules

> Full specifications (template-conformant) for the nine foundational modules. They expose stable interfaces consumed by every domain module; domain modules never reach around them.

### 1. UI / Design System

**Phase:** Phase 0 (before any domain module). **Responsibility:** single visual language, component library, anonymous-first SSR/ISR, SEO/OG tags, dark-mode tokens, TradingView wrappers, and the two mandatory shared primitives `UnifiedScoreDisplay` (one label + one confidence word; numeric score and factor weights **never in the DOM**) and `RankingExplainer` ("Why this ranking?" drawer). **Non-goals:** no domain logic in components; no data sales/profiling; no confetti/gambling motion (spin-the-wheel = single restrained CSS rotation); no production Claude Code; no buy/sell buttons anywhere. **Interface:** `<UnifiedScoreDisplay label confidence validUntil methodologyUrl/>`, `<RankingExplainer itemId factors modelConfidence contradictingSignals/>`, `<TradingViewChart symbol interval theme/>`, `generateOgMeta(entity)`, shared `revalidate=300`. **Data:** no Postgres; Redis `anon:page:{path}:html` 6 h, `anon:og:{type}:{id}` 24 h. **Mechanics:** App Router RSC; `revalidate=300`; top-1,000 slugs `generateStaticParams`; Cloudflare CDN; Nginx split; dark-mode `class` + server cookie (no FOUC); RankingExplainer data via `GET /api/v1/explain/{entity_type}/{id}`; OG PNGs from Notification Pillow service (this module only references R2 URL). **Failure modes:** ISR stale-while-revalidate; explainer slow→skeleton, error→graceful message; TradingView fail→placeholder image; cookie absent→system preference. **Build vs partner:** build; shadcn/ui vendored. **Provenance:** Master Blueprint Tech Stack/UI; v2.2 Rec 1/6/11; Reality Layer §3.1; v2.2 Part VII. **UNIQUE synthesis:** numeric-score hidden from DOM while computed backend.

### 2. Auth & Tiering

**Phase:** Phase 0. **Responsibility:** full auth lifecycle (signup/login/session/logout/2FA), RBAC, tier gating; RS256 JWT in HttpOnly Secure cookies (never JS-exposed); single `Depends(require_tier)` consumed by all domains; anonymous read-only fidelity downgrade via Nginx zone. **Non-goals:** no KYC (partner Y2); no broker-credential storage (Portfolio module scope); no session sharing/service-account Claude Code. **Interface:** `Depends(require_tier("free"|"pro"|"pro_plus"))` (402 + `{upgrade_url}`), `Depends(current_user_or_anonymous)`→`UserContext`, `/api/v1/auth/{signup,login,logout,totp/setup,totp/verify,me}`, `POST /api/v1/subscriptions/webhook` (Razorpay; flush `auth:tier:{user_id}`). **Data:** `users` (id, email, hashed_password, tier ENUM anonymous|free|pro|pro_plus|founder_lifetime, totp_secret, totp_verified, risk_profile, dpdp_consent_version, dpdp_consents JSONB, deletion_requested_at); `subscriptions` (user_id, razorpay_subscription_id, plan, status, period start/end). Redis `auth:tier:{user}` 15 m, `auth:totp_attempts:{user}` 900 s (max 5), `auth:refresh:{jti}` 7 d. **Mechanics:** access JWT 15 m RS256 `__Host-access`; refresh 7 d `__Host-refresh` silent-refresh in Next.js middleware; TOTP via `pyotp` mandatory for Pro+ sensitive actions; tier = active Razorpay sub → `users.tier`, cached 15 m; founder lifetime stored on `users`. **Failure modes:** tier cache miss→Postgres; webhook delay→old tier ≤15 m (no false upgrade); TOTP lost→email-OTP recovery; key rotation→JWKS, old key 24 h. **Build vs partner:** auth=build; payment=Razorpay; KYC=partner (Y2); AA=partner (Portfolio P2+). **Provenance:** Master Blueprint Security; v2.2 Phase 3/Rec 1/Part IV; v2.3 §10.6; Reality Layer §1.2 (`ALTER TABLE users`).

### 3. Consent & DPDP Module

**Phase:** Phase 0 (before any user data). **Responsibility:** end-to-end DPDP Act 2023 — granular per-purpose CMP, `consent_audit_log`, `data_principal_requests`, four rights endpoints; every data-processing module declares a purpose and checks `Depends(require_consent("purpose"))`; cross-border check before user-specific data to non-Indian LLM APIs. **Non-goals:** no data sales; no children's data without verified parental consent (feature-flagged off); no purpose reuse without fresh consent; no sensitive-data processing pre-consent. **Interface:** `Depends(require_consent("mf_analytics"|"ai_insights"|"marketing"|"portfolio_sync"|"behavioral_nudges"))` (403 CONSENT_REQUIRED), `GET /api/v1/consent/status`, `POST /consent/{grant,revoke}`, `POST /data-rights/request`, `GET /data-rights/requests`, `<ConsentBanner/>`. **Data:** `consent_audit_log` (user_id, purpose, action∈granted|revoked|updated, source∈onboarding|settings|banner, ip_address, user_agent; append-only); `data_principal_requests` (request_type∈access|correction|erasure|portability, status, filed_at, resolved_at). Redis `consent:{user}:purposes` 30 m. **Mechanics:** onboarding step-1 CMP (mf_analytics required; marketing optional; ai_insights/behavioral_nudges opt-in); append-only audit; erasure Celery `process_erasure` anonymizes PII, hard-deletes holdings, retains `consent_audit_log` + 7-yr `ai_recommendation_audit`, completes ≤30 d; portability JSON to R2 signed 24 h; breach → `notify_data_protection_board()` ≤72 h; NIC NTP for legally-meaningful timestamps. **Failure modes:** consent cache miss→Postgres; erasure fail→retry 5×/24 h then admin page; 25-day SLA pre-alert. **Build vs partner:** build entirely. **Provenance:** Reality Layer §1.2 (verbatim SQL/table), §1.4 (CERT-In), penalties ≤₹250 Cr.

### 4. Compliance Audit Module

**Phase:** Phase 0/1. **Responsibility:** immutable audit trail for every served AI output, disclaimer versioning, 7-year R2 archival; provides `disclaimer_version` FK; implements AI-governance gates (changelog, >5 % label-churn human-review gate, methodology versioning). Records and gates; does not produce content. **Non-goals:** no user UI beyond disclaimer text; no RIA logic; rejects `recommendation_type='buy_sell'` at schema level. **Interface:** `get_active_disclaimer(type)`, `log_ai_recommendation(...)` (fire-and-forget), `GET /api/v1/disclaimers/{type}`, admin `POST /disclaimers`, `/disclaimers/{id}/activate`, `GET /admin/audit/label-churn`. **Data:** `disclaimers` (type, version, content, active, effective_from/to; UNIQUE(type,version)); `ai_recommendation_audit` (user_id, served_at, recommendation_type, content_hash SHA-256, model, prompt_version, confidence_score, disclaimer_version FK, session_id; monthly partitioned via `pg_partman`, 7-yr); `rating_engine_changelog` (version, change_summary, factors_before/after JSONB, published_url). Redis `disclaimer:active:{type}` 1 h. **Mechanics:** daily `archive_audit_daily` 02:00 IST → R2 parquet (7-yr lifecycle); disclaimer HTML snapshot to R2 on activate; **human-review gate**: if `changed_labels/total > 0.05` batch → `pending_publish` + admin Telegram, released by `POST /admin/batches/{id}/approve` (synchronous, fail-closed); confidence <0.30 → `ai_low_confidence_log` (not served). **Failure modes:** archival fail→retry 3× then alert (non-blocking); review-gate no-approval 4 h→escalate (stays unpublished — safe default); disclaimer cache miss→Postgres. **Build vs partner:** build (boto3/S3). **Provenance:** v2.2 Rec 9 (verbatim DDL, 7-yr, monthly partition); v2.3 §10.7 (R2 replaces MinIO); Reality Layer §5.2 (gate, changelog). **UNIQUE synthesis:** `prompt_version` column.

### 5. Notification Module

**Phase:** Phase 1 (Telegram with Mood Compass P2; email digest P5; WhatsApp P6). **Responsibility:** all outbound delivery (Telegram, SendGrid email, WhatsApp Y2) + Pillow share-card PNG service; consumes structured events from Alert/Mood/Nudge/Gamification; enforces quiet hours + per-channel rate limits so domains need not. Delivery only, no content generation. **Non-goals:** no WhatsApp P1; no mobile push; no creator revenue-share; no content generation. **Interface:** `publish_notification(user_id, channel, template_id, data, priority)` (Redis LPUSH), `generate_share_card(template, data)→R2 URL`, `GET/POST /api/v1/notifications/preferences`, `POST /notifications/test` (Pro). **Data:** `notification_preferences` (telegram_chat_id, email_verified, whatsapp_number, quiet_hours_start/end, channels_enabled JSONB); `notification_log` (channel, template_id, status, error_text). Redis `notifications:queue:{telegram,email,whatsapp}` (no TTL), `notif:rate:{user}:{channel}:{date}` 86400 s (max 3 Telegram/day, 1 email digest/day), `notif:share_card:{template}:{hash}` 3600 s. **Mechanics:** `celery-misc` BLPOPs, checks quiet hours + rate limit, delivers via SendGrid/Telegram, logs; Pillow SVG→PNG 1200×630 → R2 (signed expiry for private portfolio cards, no expiry for public mood/badge); daily public-channel Mood card post-09:00 (also OG image of `/market/mood`); SendGrid free 100/day (digest prioritized). **Failure modes:** Telegram fail→3× 5 s backoff then `failed` (stale alerts have negative value); SendGrid bounce→`email_verified=false` + in-app banner; Pillow crash→fallback static PNG; worker down→queue persists (no TTL), quiet-hours checked at delivery time. **Build vs partner:** Telegram/SendGrid/Pillow=build/free; WhatsApp=partner (Y2); email=SendGrid free. **Provenance:** Master Blueprint Notification; v2.2 R18/R19/Rec 8; Reality Layer §4.2; v2.3 §10.1/§10.2. **UNIQUE:** 1200×630 OG dimension synthesis.

### 6. Observability & Cost-Budget Governor

**Phase:** Phase 0 (before first production AI call). **Responsibility:** Prometheus/Grafana/Uptime-Kuma/Sentry observability + the authoritative AI budget governor (`ai:budget:free|premium:today` enforced inside `OpenRouterGateway`); 3-strike skip telemetry. Free pool 1,000/day; premium spillover soft cap $0.50/day; **$9.50/day absolute hard ceiling** (ledger #8). **Non-goals:** no Loki/Promtail at launch (docker logs + journald); no K8s; no external APM; no PagerDuty (Telegram admin). **Interface:** Redis `ai:budget:free:today` (int, EXPIREAT midnight UTC, cap 1,000), `ai:budget:premium:today` (float USD, cap $0.50 soft/$9.50 hard), `ai:fails:{ticker}:{date}` 86400 s (3-strike); `/metrics` per FastAPI; `budget_guard()` context manager (raises `BudgetExhaustedError` before external call; domains never call it directly). **Data:** no Postgres; Redis as above; Prometheus TSDB 15 d; Sentry SaaS free. **Mechanics:** 15 s scrape; Grafana alerts (container mem >80 %; free >900; premium >$0.40; p99 >500 ms/5 m → Telegram); budget keys auto-reset via EXPIREAT (no Celery); 3-strike via `QualityValidator.validate_or_skip`; Uptime-Kuma 60 s on health/Postgres/Redis/workers; CERT-In journald `MaxRetentionSec=15552000` (180 d) on VPS NVMe. **Failure modes:** Prometheus down→"No data", restart (stateless); budget key missing→`SET NX`+EXPIREAT (treated as 0, conservative-safe); Sentry quota→structlog fallback; Uptime-Kuma down→Cloudflare HTTP monitor backup. **Build vs partner:** observability=build/free; Sentry=partner free; governor=build. **Provenance:** v2.3 §10.2/§10.3 (verbatim Redis keys/code), §10 risk register ($9.50 ceiling, 80 % alert), Docker (15 d); Reality Layer §1.4 (180 d, NIC NTP).

### 7. Gamification & Share Cards

**Phase:** P1 (badges/streaks), P4 (spin-the-wheel R23), P6 (refer-3 R22, share cards R19). **Responsibility:** badges, SIP-streak, spin-the-wheel (R23), refer-3-get-Pro (R22); owns the data populating share-card templates and trigger logic (PNG render delegated to Notification). No confetti/slot-machine physics; spin outcome pre-assigned server-side at account creation. **Non-goals:** no confetti/gambling UX; no day-trader gamification; no social feed of others' badges/portfolios; no cash revenue-share with referrers. **Interface:** `award_badge(user_id, badge_type)` (idempotent), `get_user_gamification_state(user_id)`, `POST /api/v1/referral/track`, `GET /referral/status`, `POST /signup/spin` (returns pre-assigned outcome), `POST /share-card/generate` (→ Notification). **Data:** `user_badges` (UNIQUE(user_id,badge_type)); `sip_streaks` (current/longest_streak_days, last_sip_detected); `referrals` (referrer/referred, code, converted_at, reward_granted); `spin_outcomes` (user_id UNIQUE, outcome, assigned_at, revealed_at). Redis `gamif:streak:{user}` 7 d, `gamif:referral:{code}` 90 d. **Mechanics:** SIP-streak nightly (celery-misc, AMFI NAV × holdings; reset if gap >35 d); spin weighted distribution assigned at account creation (1mo_pro 10 %, 1wk_pro_plus 5 %, og_badge 25 %, r100_credit 10 %, standard 50 %) — stored before animation (no client manipulation); refer-3 → variable reward; founder lifetime is Auth-module-handled (not gamification). **Failure modes:** spin miss→re-assign (UNIQUE prevents double); streak false-negative tolerant to 35-day gap; reward grant fail→retry 3× then admin manual. **Build vs partner:** build; broker-credit fulfillment=partner (not P1). **Provenance:** Master Blueprint Admin; Reality Layer §4.2; v2.2 R21/R22/R23/R19; v2.2 Part VII. **UNIQUE:** server-side spin pre-assignment anti-fraud.

### 8. Onboarding & Risk-Profile

**Phase:** P1 infra, P4 full UX. **Responsibility:** 5-step anonymous→authenticated funnel, 5-question risk quiz, quarterly drift nudge (Rec 14), upgrade prompts; **sole writer of `users.risk_profile`** (domains read only). **Non-goals:** no KYC at onboarding (AA Y2); no forced signup wall (anonymous-first); not RIA suitability (educational self-assessment). **Interface:** `GET /api/v1/onboarding/state`, `POST /onboarding/step/{n}`, `POST /onboarding/risk-quiz`, `GET /risk-profile/history`, `POST /risk-profile/retake`, `X-Upgrade-Prompt` header. **Data:** `onboarding_states` (user_id UNIQUE, current_step 1–5, step_data JSONB, spin_revealed); `risk_profile_log` (risk_profile∈conservative|moderate|aggressive|not_set, quiz_answers JSONB, source∈onboarding|retake|quarterly_nudge, confirmed_by_user). Redis `onboarding:progress:{user}` 7 d. **Mechanics:** steps = DPDP consent → email verify → spin → 5-Q risk quiz (weighted: conservative 0–35 / moderate 36–65 / aggressive 66–100) → watchlist/alert quick-setup; quarterly nudge cron `0 9 * 3,6,9,12 *` IST for profiles >90 d old → Notification → diff shown only after retake; `users.risk_profile` updated only on confirmation. **Failure modes:** Redis expiry→Postgres `step_data` resume; quiz tie→moderate; Beat miss→skip quarter (no double-send). **Build vs partner:** build. **Provenance:** v2.2 Phase 4/Rec 14/Rec 1/R23; Reality Layer §4.2/§3.1; Master Blueprint Product Strategy. **UNIQUE synthesis:** sole-writer ownership of `users.risk_profile`.

### 9. Admin & Governance Module

**Phase:** P0/1 (flags + prompt management before any domain ships). **Responsibility:** internal control plane — versioned AI prompt templates (Postgres, not hardcoded), ranking-config factor weights, PostHog feature flags, signal/API health, content moderation, methodology-version control gate. Admin RBAC only; writes `rating_engine_changelog` (owned by Compliance). No public surface. **Non-goals:** no user UI; no direct DB access for operators (typed audited endpoints); no production Claude Code (prompt editing via this UI). **Interface:** `get_prompt_template(id, version="active")`, `get_ranking_config(entity_type)`, PostHog client-side `is_feature_enabled`, `POST /admin/prompts/{id}/versions|activate`, `POST /admin/ranking-config/{entity_type}`, `POST /admin/batches/{id}/approve` (releases Compliance hold), `GET /admin/signal-health`, `POST /admin/content-moderation/review/{id}`. **Data:** `prompt_templates` (id, version, content, variables JSONB, active, model_hint; UNIQUE(id,version)); `ranking_configs` (entity_type, version, factor_weights JSONB sum=1.0±0.001, active, approved_by; UNIQUE(entity_type,version)); `content_moderation_queue` (content_type, content_text, flag_reason, decision). Redis `admin:prompt:{id}:active` 1 h, `admin:ranking:{entity}:active` 1 h. **Mechanics:** immutable prompt/config history (one active row; rollback=activate prior); weight-sum validator before store; PostHog flags per-user (beta models, Pro+ early access, A/B, kill-switches); signal-health Beat every 5 min (`signal:{adapter}:last_success`, alert if >30 m stale); content moderation regex on user text + prompt-injection filter on AI chat → review queue; methodology gate: `approved_by ≠ created_by` (two-person soft control). **Failure modes:** cache miss→Postgres; invalid weight sum→422 (prev active stays); PostHog down→flags default false (safe-off); moderation backlog→async non-blocking + alert >50. **Build vs partner:** admin=build; flags=PostHog free; moderation=build. **Provenance:** Master Blueprint Admin (verbatim feature list); v2.3 §10.1/§10.3; Reality Layer §5.1/§5.2. **UNIQUE synthesis:** `model_hint` per prompt template; `factor_weights` sum-to-1.0 DB constraint.

---

# §V — VERIFICATION

## V1. Coverage matrix (every source element → location, zero silent drops)

| Source element | Lands in |
|---|---|
| Master Blueprint 12 core modules | All mapped: Auth→Global §2; MF/ETF/Stock/Portfolio/Mood→C-Domain; AI Enrichment/Signal→C-Domain; Alert→C-Domain; Admin→Global §9; User-Preference→Onboarding Global §8; Reporting→Track-Record/Portfolio report-card |
| Master Blueprint signal layers, source-reliability, ranking factors, AI principles | §S Unified Scoring + Signal & Source-Reliability appendix |
| Market Intelligence positioning/differentiators/regulatory framing | §A1, §B8, §C cross-cutting (educational boundary), monetization in §A2 #4 |
| v2.2 Rec 1–14 | Rec1→Global §2/UI §1; Rec2→Mood Compass; Rec3→Signal&Source-Reliability; Rec4→Portfolio; Rec5→Market Data Adapter §B4; Rec6→AI Enrichment + UI §1; Rec7→Track-Record; Rec8→Alert&Digest; Rec9→Compliance Audit §4; Rec10→AI Enrichment (analogues); Rec11→UI §1; Rec12→Behavioral Nudge; Rec13→§B2 (Year-2 API); Rec14→Onboarding §8 |
| v2.2 R15–R24 | R15(5-axis)→§S; R16 SWOT/R17 Earnings→AI Enrichment; R18→Notification §5; R19→Portfolio/Track-Record/Gamification; R20→Stock module; R21 founder→§A2/Auth §2; R22/R23→Gamification §7; R24 creator→§A5 P6 |
| Reality Layer Parts 1–7 + Appendices | Part1 regulatory→§C + Consent §3/Compliance §4; Part2 unit economics→§A6; Part3 UX taxonomy→§S labels + UI §1; Part4 wedges/infra reuse→§A5/§B; Part5 AI governance→§S4/§C; Part6 build-vs-partner→§B8 + per-appendix; Part7 90-day→§A5 |
| v2.3 §10.1–10.13 | Infra/cost→§A6/§B5/§B6; OpenRouter→§B3 + Observability §6; containers→§A6; day-one→§A5 P0; doc structure→this file |

## V2. Uniqueness check
Each appendix's **Provenance** block explicitly flags content UNIQUE to one source (e.g. v2.3's 60-s SLA + `mf:cas:dedup` + reverse-index; v2.2 Rec 4 schema; Reality Layer §3.4 nudge rules + §1.2 DPDP SQL; v2.2 Rec 2 mood weights). No doc's distinctive contribution is dropped during dedup.

## V3. Consistency check (ledger applied uniformly)
- Cost/infra: only v2.3 numbers appear (₹1,090/mo, 12 containers, OpenRouter). ✔
- Pricing: only v2.2 (₹1,999 / ₹3,999 / ₹4,999 lifetime). ✔
- Mood cadence: 09:00 & 16:00 IST everywhere (ledger #6); v2.3 "2× daily" noted as consistent-but-unspecified. ✔
- SWOT: monthly TTL + earnings invalidation + free model everywhere (ledger #7); the Stock-appendix "weekly Sun 02:00 batch" is the *regeneration job*, the 30-day TTL is the *cache* — reconciled, not contradictory. ✔
- AI budget: free 1,000/day; premium soft $0.50/day; hard $9.50/day — single definition in Observability §6, referenced elsewhere. ✔
- "Why X Moved Today": Stock module owns; AI Enrichment references (ledger #9). ✔

## V4. Modularity check
Dependency DAG (§A4) is acyclic; every edge is a REST contract or named event; no shared mutable Postgres table across modules (separate schemas, new tables only); Redis namespaced per module; each module independently testable with upstream stubbed. Build order is a topological sort where no later module forces edits to an earlier one. ✔

## V5. Audience check
Tier A (§A1–A6) is standalone and reads in <10 min (vision, ledger, layers, DAG, phases, NFRs). Tier C appendices are each independently buildable (fixed template: interface, schema, pipeline, failure modes). ✔

## V6. Open items / assumptions
- No `[ASSUMPTION]` blocks were required: v2.2/v2.3 additivity left no material reconstruction gap (confirms ledger #10).
- Output file: `e:\code\DhanRadar\DhanRadar_Architecture_Final.md` (this file).
- Numeric factor weights for the *stock* 5-axis aggregate live in `ranking_configs` (versioned, human-approved) — values are an operational tuning decision, not an architectural one, intentionally left to the Admin/Compliance governance flow.
