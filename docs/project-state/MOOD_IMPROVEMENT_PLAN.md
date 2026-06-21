# Market Mood — Improvement Plan

Status: PLAN (no code yet). Owner: founder + Builder/Architect. Created 2026-06-21.

Direction confirmed by founder 2026-06-21: **educational purpose only** — Market Mood
stays a descriptive sentiment-and-literacy surface, never a decision-support, market-timing,
or "did I make money" engine.

## 1. Why this doc exists

A product spec, `docs/DMMI.md` ("DhanRadar Market Mood Intelligence"), proposed turning Market
Mood into a decision-support system organised around one question: *"If an investor followed this
signal historically, would they have made money?"*

That framing is the exact line DhanRadar is built **not** to cross. This plan keeps DMMI's strong
UX ideas, reframes the ones that can be made educational, and rejects the ones that are advisory
or predictive. `docs/DMMI.md` has been removed — every salvageable idea it contained is triaged
in §5 below, so nothing of value is lost, and the non-compliant surfaces are not left lying around
to be built from verbatim.

## 2. Binding rules this plan must respect

From the project non-negotiables and the `DhanRadar-Market-Mood-Trend` governance skill:

- **SEBI educational boundary** — no buy / sell / hold / "now is the time" anywhere (copy, enum,
  AI output). Mood describes sentiment; it never recommends an action.
- **No numeric in DOM** — the public surface shows a **label + confidence band** only. The raw
  `mood_score` (0–100), `confidence_score` (0–1), and per-factor weights never reach the client.
- **Never predict** — *Describe · Measure · Explain · NEVER Predict*. Mood is not market
  direction. No "after similar readings the market did X", no win rates, no return projections.
- **Confidence band-only** — `high / medium / low`; below the refuse floor → `insufficient_data`.
- **Disclosure + audit** — every mood surface renders the disclosure bundle + `NOT_ADVICE`, tied
  to the in-force disclaimer version, and is logged to the served-label audit trail.

Governance: every new mood surface is a label/AI surface, so at build time each one goes through
`DhanRadar-Market-Mood-Trend` + `DhanRadar-SEBI-Compliance-Guardrail`. This plan is build-eligible
**phase by phase under those reviews**, not as a whole.

## 3. Current state (as-built, 2026-06-21)

Market Mood is already live and already compliant — it is more mature than DMMI assumes.

- **Page** `/mood`: a regime-**label** gauge (`extreme_fear → extreme_greed`), a confidence
  **band word**, Supporting / Counterweights factor lists, a 30-day history colour strip, the
  disclosure bundle + `NOT_ADVICE`, refreshed twice daily (09:00 and 16:00 IST).
- **Compliance already enforced**: no numeric score or percentage in the DOM; `mood_score` and
  `confidence_score` stay server-side and are asserted absent from the API response in tests; an
  advisory-verb regex withholds AI commentary on any match; every snapshot is audit-logged.
- **Engine**: 11 weighted factors aggregated to a 0–100 score, then bucketed to a regime. Real
  data exists for **7** factors (Yahoo Finance: Nifty trend, India VIX, S&P 500, US 10Y yield,
  Brent, USD/INR, Nifty-50 market breadth).
- **History**: every snapshot is persisted to `mood.market_mood` from day one, but only **weeks**
  of history exist so far — not the multi-year history DMMI's backtests and heatmaps assume.

### 3.1 The real weakness — permanent degraded mode

Four factors are **stubbed** (no data source wired): FII flows, DII flows, put-call ratio, news
sentiment. With 7 of 11 signals, the engine sits in **degraded mode every day**: confidence is
capped at ~0.40 and **AI commentary is withheld every single day**. The single highest-value,
fully-compliant improvement is to exit this state — and it is not in the DMMI doc at all.

## 4. Key files (for the builder)

- `frontend/src/app/mood/page.tsx` — public mood page (sections, copy, compliance checklist).
- `frontend/src/components/mood/MoodGauge.tsx` — regime enum + display/colour maps + confidence
  band words.
- `frontend/src/features/mood/{types.ts,api.ts}` — response types (no numeric fields) + query
  hooks.
- `backend/dhanradar/mood/compute.py` — pure score logic (11 weighted inputs, buckets, confidence,
  contributing/contradicting split). Server-side numerics only.
- `backend/dhanradar/mood/service.py` — fetch → compute → persist → cache → audit; advisory-verb
  filter; the AI-commentary hook (built but never passed today).
- `backend/dhanradar/mood/{schemas.py,router.py}` — API contract + endpoints.
- `backend/dhanradar/models/mood.py` — `mood.market_mood` table (numerics stored, never
  serialized).

## 5. DMMI idea triage

### 5.1 KEEP / build — compliant, with data we already have

- **Regime-vs-yesterday + trend** — show "Yesterday: Neutral → Today: Greed · trend improving"
  using labels and the existing `trend` word. DMMI's "72, +8" numbers stay out.
- **Relative time** — "updated 2 hours ago" instead of a literal date. Small real UX win.
- **Drivers upgrade** — we already show Supporting / Counterweights; add ordering or relative
  magnitude **bars without numbers**. DMMI's "Breadth 82/100" numerics are dropped.
- **Confidence in words** — explain *why* confidence is what it is ("most signals available today"
  vs "limited signals today"), never "84%".

### 5.2 REFRAME to comply — good idea, advisory/predictive framing removed

- **Educational market-history storytelling** (DMMI §8 timeline, Mood Journey, yearly heatmap) —
  describe past episodes by their **sentiment regime** ("COVID crash → extreme fear") as financial
  literacy, with **no** "+68% next 12M / invest-and-profit" return columns. Needs accrued history.
- **Band-crossing timeline** (DMMI §4) — keep "when sentiment shifted bands" as descriptive
  history; **drop** the "market performance after" return columns.
- **Sentiment-band distribution** (DMMI "Opportunity History") — "how often sentiment has sat in
  each band" is a fine descriptive stat; **drop** the "Opportunity" naming and the "creates
  urgency" framing.

### 5.3 DROP — no compliant version exists

- **Opportunity Meter / "Strong Opportunity" zones** (DMMI §2) — a market-timing **buy signal** in
  disguise, plus a raw 0–100 number. The only future salvage is a descriptive **valuation context**
  band, never called "opportunity".
- **"What History Says" win rate + return projections** (DMMI §3) and **Investor Action Card**
  returns (DMMI §9) — implied **prediction** + past-performance / return claims.
- **Signal Accuracy Dashboard** (DMMI §5) — "this signal is 85% accurate" is the predictive-signal
  claim SEBI prohibits.
- **Investment Simulator** (DMMI §6) — explicit "buy when DMMI < 25, sell when > 75 → 17.8% CAGR"
  is buy/sell advice + a backtested return projection. Maximally non-compliant.
- **Rupee projections** ("₹10,000 would be worth ₹24,300") and the **"creates urgency"** framing —
  performance promises + a dark pattern.

## 6. Data reality check

Independent of compliance, DMMI's marquee features cannot be made **real** yet:

- **Years of mood history** are required for heatmaps, journeys, and any historical study; we have
  weeks. Backfilling fabricated history would be both wrong and non-compliant.
- **Missing data sources** — valuation (P/E percentile), sector strength, MF flows, FII/DII flows,
  put-call ratio, drawdown levels are not wired. FII/DII/PCR have **no clean free feed** today —
  the same class of source-block as the per-scheme AUM problem (`docs` B67). No imputing.

## 7. Phased plan

- **Phase 1 — compliant quick wins (data we have).** Regime-vs-yesterday + trend, relative time,
  numberless driver bars, confidence-in-words. Pure label/DOM work; low risk. Tier-A + compliance
  spot-check.
- **Phase 2 — exit degraded mode (highest real value).** Source the 4 missing signals (FII/DII
  flows, PCR, news sentiment) and wire the already-built AI-commentary hook so the page produces a
  fresh, explained read every day above the confidence floor. The hard part is data sourcing, not
  code. Load-bearing-adjacent (AI gateway consumer) → full inline Tier-B review when the commentary
  hook is wired.
- **Phase 3 — educational history layer (needs accrued history + reframe).** Mood-journey path,
  yearly heatmap, curated market-history episodes — all label-only, past-tense, heavily disclosed.
  Pairs with the educational-content / programmatic-SEO effort.
- **Rejected (logged so they do not resurface).** Opportunity Meter, win-rate / accuracy signals,
  Investment Simulator, rupee projections.

## 8. Open decisions for founder

- **Phase 2 data dig** — should the next step be a sourcing investigation for FII/DII/PCR/news
  feeds (cost, ToS, freshness)? Exiting degraded mode is the biggest real win and gates the daily
  AI commentary.
- **Phase 3 scope** — how far to take the educational history layer (a single curated "market
  history" page vs an interactive heatmap/journey), given it needs accrued history.
- **News sentiment** — confirm the AI path is the governed OpenRouter gateway (it is, by stack
  lock) and that sentiment output is descriptive only, screened by the advisory-verb filter.

## 9. Success metric (reframed for the educational posture)

When a user opens `/mood`, within ~10 seconds they should understand, **descriptively and without
any call to action**:

1. What is the current market sentiment (the regime label)?
2. How did it move versus yesterday (label-to-label, with a trend word)?
3. What is driving it (the supporting / counterweight factors)?
4. How reliable is today's read (the confidence band, explained in words)?
5. Where can I learn more about what market sentiment means (educational links)?

No numeric score, no opportunity rating, no historical return, no projection — just a clear,
honest, educational read of how the market feels today.

## 10. Sources

- `docs/DMMI.md` (removed 2026-06-21) — original spec; ideas triaged in §5.
- Current implementation — files in §4.
- Governance — project non-negotiables (CLAUDE.md), `DhanRadar-Market-Mood-Trend`,
  `DhanRadar-SEBI-Compliance-Guardrail`.
