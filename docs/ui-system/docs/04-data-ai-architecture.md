# DhanRadar — Data & AI Architecture

*Implementation-ready architecture for data ingestion and the AI platform. Complements the backend architecture (doc 03). Stack-compatible: FastAPI · PostgreSQL · Redis · Elasticsearch · Celery + a vector store and an AI gateway.*

**Prepared by:** AI Architecture · Data Architecture · **Date:** June 2026 · **Status:** v1 for build

---

## 0. System map

```
 ┌──────────────────────── DATA PLANE ────────────────────────┐
 │  Sources           Ingestion            Storage            │
 │  ┌──────┐                                                   │
 │  │ NSE  │─┐                          ┌─▶ Postgres (truth)   │
 │  │ BSE  │─┤   ┌──────────────────┐   ├─▶ Timescale (ticks)  │
 │  │ AMFI │─┼──▶│ Connectors →     │──▶├─▶ Elasticsearch       │
 │  │ News │─┤   │ Validate → Norm  │   ├─▶ Vector store (pgvec)│
 │  │ Corp │─┘   │ → Dedupe → Load  │   └─▶ Object store (raw)  │
 │  │ Act. │     └──────────────────┘                          │
 │                       │ (Celery: ingest queue)              │
 └───────────────────────┼─────────────────────────────────────┘
                         ▼  events (Redis streams / Kafka-ready)
 ┌──────────────────────── AI PLANE ──────────────────────────┐
 │   ┌────────────────────────────────────────────────────┐   │
 │   │                  AI GATEWAY                          │   │
 │   │  authz · rate/cost budget · prompt mgr · model      │   │
 │   │  router · RAG retriever · safety · cache · trace     │   │
 │   └───┬──────────┬───────────┬───────────┬──────────────┘   │
 │       ▼          ▼           ▼           ▼                   │
 │  Recommendation  News      Portfolio   Confidence           │
 │  Engine          Summ.     Insights    Scoring              │
 │       │          │           │           │                  │
 │       └────── Vector Search · Semantic + Score cache ───────┘
 └─────────────────────────────────────────────────────────────┘
                         ▼
              Monitoring · Cost Control · Evals (AI Ops)
```

**Tenets**
1. **One ingestion contract** — every source flows through the same Connect → Validate → Normalize → Dedupe → Load → Emit pipeline, differing only in the connector.
2. **The gateway is the only door to models** — no service calls an LLM directly; routing, cost, safety, and caching are centralized.
3. **Ground everything** — AI reads internal data via RAG; no open-web inference.
4. **Cheap by default** — cache → small model → large model, in that order. Cost is a first-class budget, not an afterthought.
5. **Provenance always** — every datum carries `source`, `as_of`, `ingest_id`; every AI output carries `sources`, `confidence`, `model_version`.

---

# PART 1 — DATA INGESTION

## 1.1 Common ingestion pipeline

```
Connector ──▶ Validate ──▶ Normalize ──▶ Dedupe ──▶ Load ──▶ Emit
  (pull/      (schema,      (to canonical  (idempotency  (Postgres/  (Redis
   push/       ranges,       instrument     key per       ES/vector)   stream
   file)       freshness)    + units)       record)                    event)
```

- **Idempotency key** per record (e.g., `nse:{symbol}:{ts}` for prices, `amfi:{scheme}:{nav_date}` for NAV, `news:{hash(url+title)}`) → safe re-runs, exactly-once effect.
- **Watermarking** — each source tracks `last_ingested_at` / `last_seq`; connectors resume from the watermark.
- **Dead-letter queue** — records failing validation land in `ingest_dlq` with the reason; AI-Ops/admin can replay.
- **Schema registry** — each source has a versioned input schema; a registry rejects/migrates on drift.
- **Lineage** — every loaded row links to an `ingest_runs(id, source, started, status, counts)` row for traceability.

## 1.2 Source-by-source

### NSE / BSE (equity & ETF prices, ref data)
- **Mode:** intraday via licensed market-data vendor (WebSocket/streaming) for live price/volume; EOD bhavcopy (file) for official OHLC + corporate reference.
- **Cadence:** stream (sub-second, throttled to 5–15s persisted snapshots) + EOD reconcile (authoritative close overwrites intraday).
- **Targets:** `instrument_prices` (Timescale hypertable), Redis `px:{sym}` (hot), ES price fields for screener.
- **Concerns:** exchange holiday calendar, circuit limits, symbol changes/mergers (handled via corporate actions), dual-listing (NSE+BSE) reconciled to one canonical instrument with venue tags.

```
NSE/BSE WS ─▶ stream consumer ─▶ throttle/snapshot ─▶ Redis px + Timescale
EOD bhavcopy ─▶ file connector ─▶ validate vs intraday ─▶ authoritative close
                                                       └─▶ trigger score recompute
```

### AMFI (mutual fund NAVs)
- **Mode:** daily NAV text file (AMFI publishes EOD); scheme master for fund metadata.
- **Cadence:** daily after publish (~23:00 IST); Celery beat poll + ETag/checksum to avoid reprocessing.
- **Targets:** `instrument_prices` (NAV as close for `type=fund`), fund meta (expense, AUM, category) to `instruments.meta`, ES for fund screener.
- **Concerns:** scheme code ↔ ISIN mapping, direct vs regular plan dedupe, scheme mergers/closures, backfill of historical NAV for rolling-return computation.

### News
- **Mode:** licensed news API + RSS/feeds; pull on schedule + webhook where available.
- **Pipeline:** fetch → dedupe (URL+title hash) → clean (boilerplate strip) → **entity linking** (map to instruments/sectors via NER + symbol dictionary) → tag (category) → store → **embed** (vector) → emit.
- **Targets:** `news` table, ES (full-text feed), vector store (for semantic retrieval + summarization grounding), Redis (recent feed cache).
- **Cadence:** hourly bulk + near-real-time for tagged tickers in users' holdings/watchlists.

### Corporate actions
- **Mode:** exchange/registrar feeds + EOD files (dividends, splits, bonuses, buybacks, mergers, name/symbol changes, record/ex dates).
- **Why critical:** they correct price series (split/bonus adjustment), keep holdings accurate, and drive earnings/event alerts.
- **Pipeline:** ingest → classify action → **apply adjustment** to historical `instrument_prices` (adjustment factor) and to user `holdings` (split-adjust qty/avg) → schedule event alerts (ex-date, record-date) → audit every adjustment.
- **Targets:** `corporate_actions` table, adjustment job on price series, alert scheduler.

## 1.3 Orchestration & reconciliation
- **Celery `ingest` queue** with Beat schedules per source; backfill jobs are separate, rate-limited.
- **Reconciliation pass** (nightly): cross-check vendor vs exchange EOD; flag variances > tolerance to a data-quality dashboard (feeds the Admin "Data Source Monitor").
- **Freshness SLAs** drive **confidence** downstream — a stale source lowers AI confidence and is surfaced in Source Attribution.

| Source | Cadence | SLA freshness | Authority |
|---|---|---|---|
| NSE/BSE intraday | stream | < 15 s | vendor |
| NSE/BSE EOD | daily | by 20:00 IST | exchange (authoritative) |
| AMFI NAV | daily | by 23:30 IST | AMFI |
| News | hourly + RT for held | < 60 min | publisher |
| Corporate actions | daily | by 19:00 IST | exchange/registrar |

---

# PART 2 — AI GATEWAY

The single, mandatory entry point for all AI. No service imports an LLM SDK directly.

```
request → AI GATEWAY ────────────────────────────────────────────────┐
  1. AuthZ + plan + per-user AI quota                                 │
  2. Cost budget check (token/₹ budget; reject/queue if exhausted)    │
  3. Cache lookup (semantic + exact) → hit? return (no model call)    │
  4. Prompt Manager: select versioned template + inject context       │
  5. RAG Retriever: vector + keyword fetch grounding (internal only)  │
  6. Model Router: pick model by task/complexity/cost/latency        │
  7. Safety (pre): prompt-injection + PII scrub                       │
  8. Model call (stream or batch) with timeout + fallback             │
  9. Safety (post): advice-boundary + groundedness + unsafe filter    │
 10. Attribution: attach sources + confidence + model_version         │
 11. Cache write · cost meter · trace span · feedback hook            │
  ←──────────────────────────────────────────────────────────────────┘
```

**Why centralized:** one place to enforce cost, safety, grounding, caching, and observability; swap models without touching feature code; A/B prompts and models safely.

---

# PART 3 — MODEL ROUTING

Route by **task class → complexity → cost/latency budget**, with fallback.

| Task | Default tier | Escalate when | Fallback |
|---|---|---|---|
| Embeddings | small embed model | — | secondary embed |
| Intent/classify (search) | small/cheap LLM | ambiguous | mid LLM |
| News summarization | small→mid LLM | long/multi-doc | mid LLM |
| Explainability (why-score) | mid LLM (templated) | low groundedness | large LLM |
| Assistant (multi-turn reasoning) | mid LLM | hard comparison/portfolio | large LLM |
| Portfolio deep-dive (Premium) | large LLM | — | mid + retry |

**Routing inputs:** task type, token estimate, user plan (Premium may unlock larger models), current cost budget, p95 latency target, and a complexity score (query length, # entities, retrieval spread).
**Mechanics:** router returns `(model, params, max_tokens, timeout)`; on error/timeout → **circuit-breaker** to fallback model; persistent failure → graceful degraded answer ("I can explain the factors but can't run a full comparison right now").
**Determinism where it matters:** explainability uses low temperature + templated scaffolds so the same score yields stable language.

---

# PART 4 — PROMPT MANAGEMENT

- **Versioned templates** in a registry (`prompts` table / repo): `id`, `version`, `task`, `template`, `vars`, `model_constraints`, `status` (draft/canary/live/retired).
- **Composition:** system prompt (role + guardrails: "explain, never advise; cite sources; admit uncertainty") + task template + retrieved context + user query.
- **Guardrails baked in:** every template carries the non-advice instruction, the citation requirement, and the confidence-disclosure rule — so the contract can't be forgotten per-feature.
- **A/B & canary:** route a % of traffic to a new prompt version; compare on the eval suite + feedback; promote or roll back (managed in AI Ops).
- **Change control:** prompt edits are reviewed, versioned, and audited (a prompt is product logic, not config-to-edit-freely).
- **Injection defense:** retrieved/user content is delimited and never interpolated as instructions; a pre-filter strips known injection patterns.

---

# PART 5 — RECOMMENDATION ENGINE (data/AI view)

Quant scoring is deterministic; AI sits **on top** for explanation — never to generate the number.

```
Nightly (post-close):
  prices+fundamentals+NAV ─▶ FACTOR COMPUTE ─▶ NORMALIZE (sector/peer z→0-100)
     ▼                         (valuation, growth, quality, momentum, risk)
  COMPOSITE (weighted, model_version) ─▶ score + signal band
     ▼
  FAIR VALUE (DCF + relative + EPV, weighted) ─▶ target + confidence
     ▼
  WRITE scores(as_of, model_version)  [immutable]
     ▼
  DIFF vs prior ─▶ score-change events ─▶ alerts + cache invalidation
     ▼
  AI: pre-generate explanations (bull/bear/why) for top-N + held instruments
      → store with sources + confidence (cache-warm)
```

- **Determinism & auditability:** the score is reproducible from inputs + `model_version` weights; no LLM in the number.
- **AI's role:** turn `factors` JSON into Explainability, Bull/Bear, and Why-This-Stock language, grounded in the same sources.
- **Versioning/canary/rollback** as in doc 03 (Part I) — repoint active `model_version`, no migration.

---

# PART 6 — CONFIDENCE SCORING

A first-class, explainable number attached to **every** AI output and recommendation — separate from the Score.

```
confidence = f(
  data_freshness,        # all sources current? stale → down
  source_coverage,       # how many primary sources grounded the claim
  factor_agreement,      # do the score factors point the same way?
  retrieval_relevance,   # vector similarity of grounding chunks
  model_self_signal      # logprob / self-consistency across samples
) → 0–100 → band (High ≥75 / Moderate 50–74 / Low <50)
```

- **Honest by design:** Low confidence is shown prominently with the reason (e.g., "news feed 8m stale"), never hidden.
- **Calibration:** periodically validate that stated confidence matches realized accuracy (reliability curve) in AI Ops; recalibrate weights.
- **Propagation:** confidence flows into UI (Confidence Visualization), gates auto-actions (we never auto-anything on Low), and adjusts caching TTL (low-confidence answers cached shorter).

---

# PART 7 — NEWS SUMMARIZATION

```
news item ─▶ already embedded (ingest) ─▶ cluster related stories
   ▼
RAG: pull the story + linked instrument context (score, recent moves)
   ▼
Summarize (small→mid model) ─▶ neutral, factual, 2–3 sentences
   ▼
Entity link → attach affected instruments + direction hint
   ▼
Safety (no advice/prediction) + Attribution (publisher, time)
   ▼
Cache (by story cluster) ─▶ serve in News feed / Daily digest
```

- **Dedup/cluster** so the same event isn't summarized five times; one summary per cluster.
- **Tone guardrail:** factual, no buy/sell language, no price prediction — enforced by template + post-filter.
- **Personalization:** "my holdings" view filters clusters to the user's instruments (retrieval-scoped), summary itself is shared/cached.
- **Cost:** summaries are pre-generated on ingest (batch, cheap model) and cached — reads cost nothing.

---

# PART 8 — PORTFOLIO INSIGHTS

```
trigger (portfolio change | nightly | monthly report)
   ▼
DETERMINISTIC ANALYTICS first:  concentration, sector exposure,
   risk metrics, score drift, benchmark delta   (pure compute, no LLM)
   ▼
RANK observations by impact (rule-based severity)
   ▼
RAG: ground each flagged observation in instrument data
   ▼
AI narrates each into plain English (non-prescriptive)  + confidence
   ▼
Safety (observe/flag, never instruct) → store/serve
```

- **Numbers come from code, words from AI** — the AI never computes risk; it explains the computed result. Prevents hallucinated stats.
- **Consent-gated:** uses the user's holdings only if the "use my portfolio for insights" toggle is on.
- **Output is observations, not orders** — "Top 3 = 58% (concentration)", never "sell TITAN".

---

# PART 9 — CACHING (AI + data)

Layered, with semantic caching unique to the AI plane.

| Layer | What | Key | TTL | Notes |
|---|---|---|---|---|
| Exact AI cache | identical query+context+model | `ai:exact:{hash}` | 1h–1d | instant, zero-cost |
| **Semantic cache** | near-duplicate questions | vector NN over cached Q | sim ≥ 0.95 | reuse answer; biggest cost saver |
| Explanation cache | per-instrument why/bull/bear | `ai:explain:{sym}:{model_v}` | until recompute | pre-warmed nightly |
| News summary cache | per story cluster | `ai:news:{cluster}` | story life | pre-generated |
| Embedding cache | doc/text → vector | content hash | long | avoid re-embedding |
| Score cache | quant score | `score:{sym}` | until recompute | pub/sub invalidation |
| Instrument/price | data plane | `instr:`/`px:` | 1h / 15s | doc 03 |

- **Invalidation:** event-driven (score recompute, news update, corporate action) via Redis pub/sub; confidence-aware TTL (low confidence → shorter).
- **Semantic cache guardrail:** only reuse when retrieval context is equivalent (same instrument/timeframe) to avoid stale-context reuse.

---

# PART 10 — VECTOR SEARCH

- **Store:** `pgvector` in Postgres to start (operational simplicity, transactional with metadata); migrate to a dedicated vector DB (e.g., Qdrant/Milvus) if scale/latency demands.
- **Indexed corpora:** news articles, filings/factsheet chunks, glossary/learn content, instrument descriptions, and **cached Q&A** (for semantic cache).
- **Index:** HNSW; metadata filters (instrument_id, type, recency, source) applied alongside ANN for **hybrid** retrieval.
- **Hybrid retrieval:** combine vector similarity + Elasticsearch keyword/BM25 (reciprocal-rank fusion) → better grounding than either alone.
- **Chunking:** semantic chunking with overlap; each chunk carries `source`, `as_of`, `instrument_id` for attribution + freshness-based confidence.
- **Refresh:** embeddings updated on ingest (new news/filings) and via nightly backfill for changed content; model-version of the embedder tracked (re-embed on upgrade).

```
query ─▶ embed ─┬─▶ vector ANN (HNSW) ──┐
                └─▶ ES BM25 keyword ─────┼─▶ RRF fuse ─▶ top-k chunks ─▶ context
            metadata filters (sym, recency, source) applied to both
```

---

# PART 11 — COST CONTROL

```
every AI request debits a budget:
  per-user (plan-tiered) · per-feature · global daily ₹ cap
        │
   ┌────┴───────────────────────────────────────────────┐
   ▼                ▼                 ▼                   ▼
 cache-first   route to cheapest   batch & pre-gen    cap max_tokens
 (exact+       adequate model      (news, explains    per task; stream
  semantic)    (Part 3)            off the hot path)  to stop early
```

- **Cache-first** is the #1 lever — exact + semantic caches target a high hit-rate so most reads cost nothing.
- **Right-sizing** — small model by default; escalate only on need (Part 3).
- **Pre-generation** — explanations and news summaries are produced in cheap nightly/ingest batches, not per request.
- **Budgets & caps** — per-user (Free 5 AI/day), per-feature, and a global daily spend cap; breaching queues or degrades gracefully (never silently overspends).
- **Token discipline** — max_tokens per task, prompt-compression of context, streaming to allow early stop.
- **Visibility** — AI-Ops Cost Monitor tracks ₹/feature, ₹/user, cache-hit-rate, and model mix; alerts on anomalies (a runaway loop or a costly prompt regression).

---

# PART 12 — MONITORING

**Data plane**
- Freshness/lag per source, ingest success/failure counts, DLQ depth, reconciliation variance → **Data Source Monitor** (Admin).
- Alerts: source stale beyond SLA, schema drift, variance > tolerance, DLQ growth.

**AI plane (AI Ops dashboards)**
- **Quality:** groundedness score, eval-suite pass rate, hallucination/safety flags, factor-stability, confidence calibration curve.
- **Performance:** p50/p95/p99 latency per task, model error/timeout rate, fallback rate, cache hit-rate (exact + semantic).
- **Cost:** ₹/day, ₹/feature, ₹/user, token volume, model mix.
- **Feedback loop:** thumbs up/down on every answer → triaged in AI Ops → routes to prompt/data/retrieval fix or training label.

**Cross-cutting**
- OpenTelemetry traces span gateway → retrieval → model → post-processing with one `request_id`.
- Metrics (Prometheus) + dashboards (Grafana); logs structured + correlated; SLO burn-rate alerts.
- **Safety monitor** (real-time): advice-boundary breaches, unsafe content, low-groundedness — flagged outputs blocked/queued and reviewed.

```
              ┌──────── feedback (👍/👎) ────────┐
              ▼                                   │
 user ─▶ gateway ─▶ model ─▶ answer ─▶ UI ────────┘
   every hop emits: trace span · cost meter · quality signal
              ▼
   Monitoring (Prometheus/Grafana) + AI-Ops console + Safety monitor
              ▼
   regressions → rollback prompt/model version (canary controls)
```

---

## Appendix — build order

1. Ingestion contract + NSE/BSE EOD + AMFI (the spine of every score).
2. Corporate actions (correctness) + intraday stream.
3. Vector store + hybrid retrieval + embeddings on ingest.
4. AI Gateway (auth, cache, router, safety, attribution) — before any AI feature.
5. Explainability + News summarization (pre-generated, cached) — cheapest, highest-trust wins.
6. Assistant + Portfolio Insights (consent-gated).
7. Cost Monitor + Eval suite + Safety monitor live **before** scaling AI traffic.

*Pairs with doc 03 (backend) and the AI-layer UX (answer → reasoning → confidence → sources). Next artifacts: connector interface spec, eval-suite definition, and the prompt registry seed.*

## Addendum — AI Governance (see /ai-governance)
Full governance framework added: prompt management/versioning/testing/approval workflow, evaluation framework (test/A-B/regression with golden sets + release gates), quality scoring, LLM observability (cost/token/latency/routing budgets + alerts), and hallucination/grounding/source-attribution controls. Every model-touching path runs through the single AI Gateway; releases pass automated evals + compliance/research/governance approval before canary→promote, with instant rollback.
