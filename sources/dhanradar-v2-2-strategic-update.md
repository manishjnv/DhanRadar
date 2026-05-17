# DhanRadar v2.2 — Strategic & Architectural Update

**Status:** Development Ready · **Date:** May 2026 · **Prepared by:** Manish · **Classification:** Internal

**Builds on:** DhanRadar Architecture v2.1 (March 2026) · Master Blueprint · Competitive Landscape Research

---

## Document Changelog

| Version | Date | Scope | Status |
|---|---|---|---|
| v2.0 | Feb 2026 | Initial production architecture | Superseded |
| v2.1 | Mar 2026 | Production-grade gap resolution (14 gaps + 8 partials) | Superseded |
| **v2.2 (this document)** | **May 2026** | **Strategic & product alignment with Master Blueprint + competitor analysis** | **Active** |

**v2.2 introduces:**
- 7 Executive Findings re-aligning v2.1 with product strategy
- 14 Architecture Recommendations (anonymous access, Mood Compass, Track Record, etc.)
- Revised pricing & subscription tiering aligned to Indian market reality
- Viral growth mechanics specification
- 18-week phased implementation plan
- Cost impact analysis vs v2.1

---

# Part I — Executive Findings

These seven findings frame everything that follows. Each is a strategic gap or misalignment between v2.1 and either the Master Blueprint or the Indian competitive reality.

## Finding 1 — v2.1 is technically excellent but product-strategically incomplete

v2.1 executes the "how" beautifully — Docker Compose, observability, security, testing — but has drifted from the "what" defined in the Master Blueprint. Three flagship product pillars from the Blueprint are entirely absent from v2.1: anonymous-first access, Market Mood Index, and explainability/confidence scoring as a first-class layer. The platform as architected today is a high-quality SaaS product with features competitors already have. v2.2 closes this gap.

## Finding 2 — Indian retail price ceiling for analytics is ~₹2,400/year

Tickertape Pro at ₹2,399/year is the de-facto anchor in the Indian retail analytics market. ETMoney Genius effectively prices at ~₹996/year. Trendlyne Pro Plus Global at ₹11,900/year is reserved for serious-retail / professional users. **v2.1's implied ₹499/month (₹5,988/year) Pro tier is 2.5× the market reference price** and will not work without dramatic feature differentiation. v2.2 reprices Pro at ₹1,999/year and adds Pro+ at ₹3,999/year — clear, defensible positioning relative to anchors.

## Finding 3 — "Educational only" positioning is DhanRadar's biggest constraint AND biggest moat

DhanRadar cannot give buy/sell recommendations (positioning), cannot run advisory portfolios (no SEBI RA registration), and cannot place trades (no broker license). This rules out Liquide's, ETMoney Genius's, and smallcase's monetization paths. **But this constraint is also a moat:** DhanRadar can launch faster, scale anonymously, and never carry the regulatory liability that has slowed those competitors. Position the platform as "the most explainable analytics platform in India" — a claim none of the regulated players can credibly make because their incentives push them toward conviction-language, not nuance-language.

## Finding 4 — "Market Mood Index" is already owned by Tickertape — rename

Tickertape's Market Mood Index (MMI) is their flagship sentiment feature and is well-known among 6M+ Indian retail investors. v2.1 plans a feature with the same name. Either rename it (recommended: **"Mood Compass"**) or accept being seen as a copy. Renaming is free and immediate; allow the broader 11-input multi-signal architecture from the Master Blueprint to actually differentiate it from Tickertape's narrower MMI.

## Finding 5 — Indian fintech subscription willingness-to-pay is improving but ARPU caps at ~₹250/month

Indian retail consumers are becoming more willing to pay for digital financial tools — but the per-user revenue ceiling for educational analytics platforms is roughly ₹100–250/month, with annual prepay discounts of 30–40% being psychologically required. v2.2 sets Pro at ₹199/month and Pro+ at ₹499/month, with annual discounts of ~33%. Critically: every Pro feature must produce **tangible time savings or risk reduction** — not just "more data." Indian users churn fast from subscriptions that feel like content libraries.

## Finding 6 — Indian fintech subscriptions are sold through video creators, not paid acquisition

ETMoney, Liquide, and Tickertape all rode YouTube finance creator endorsements (Pranjal Kamra, Akshat Shrivastava, CA Rachana Ranade, Labour Law Advisor) to scale. Performance marketing CAC for Indian fintech retail is ₹800–2,500 per signup; creator partnership CAC averages ₹300–600. v2.2 commits ~₹2–3L/month to creator partnerships for months 1–6 post-launch. **Use flat fees, not revenue share** — revenue share invites bias and erodes the trust positioning that is DhanRadar's core moat.

## Finding 7 — v2.1 sequenced gamification before acquisition mechanics — backwards

v2.1's roadmap places gamification, share cards, and referral as Phase 5 (Weeks 11–12). These features monetize users you already have. **Anonymous access, Mood Compass, and Track Record are how you get users in the first place.** v2.2 swaps the sequencing: acquisition mechanics ship in Phase 1–2, retention mechanics ship in Phase 4–5. This is more capital-efficient and better-matched to the funnel.

---

# Part II — The 14 v2.2 Recommendations

These are the ranked architectural and product additions to v2.1, ordered by ROI and acquisition impact.

## Recommendation 1 — Anonymous-First Access Tier 🔴 Critical

**Source:** Master Blueprint · **Effort:** Medium · **Priority:** Critical

The Master Blueprint mandates anonymous access. v2.1 is heavily JWT-gated and walls AI features behind consent + auth. This is a business model conflict that kills SEO acquisition.

**Implementation:**
- Public read-only tier with separate Nginx rate limit bucket: `limit_req_zone $binary_remote_addr zone=anon:10m rate=30r/m`
- SSR-rendered MF/ETF/stock detail pages with `<meta>` tags for SEO and OG tags for sharing
- Anonymous Redis cache namespace (`anon:`) with 6-hour TTL since data is non-personal
- Picks shown to anonymous users at lower fidelity (top 5 instead of 10, no AI thesis text — just headline + chart + DhanRadar Score)
- "Sign up to see full thesis" upgrade prompt on every public page
- Cloudflare ISR (Incremental Static Regeneration) for top 1,000 most-viewed stocks/MFs — near-zero load on origin

**Schema additions:** None. New Redis namespace only.

**Cost impact:** ~₹0/month. Cloudflare CDN absorbs anonymous traffic.

---

## Recommendation 2 — Mood Compass Module 🔴 Critical

**Source:** Master Blueprint · **Effort:** Low · **Priority:** Critical

Renamed from Master Blueprint's "Market Mood Index" (Tickertape conflict). The 11-input regime indicator is DhanRadar's most differentiated public-facing feature.

**Implementation:**

```python
# backend/app/services/mood_compass.py
MOOD_INPUTS = [
    ("nifty_trend", 0.15),       # 50DMA vs 200DMA
    ("market_breadth", 0.12),    # advance/decline ratio
    ("india_vix", 0.10),         # volatility
    ("fii_flows", 0.10),         # FII net buy/sell
    ("dii_flows", 0.08),         # DII net buy/sell
    ("global_indices", 0.10),    # S&P + Hang Seng + Nikkei
    ("us_bond_10y", 0.08),       # macro signal
    ("oil_brent", 0.07),         # commodity / inflation
    ("usd_inr", 0.07),           # currency
    ("put_call_ratio", 0.07),    # derivative sentiment
    ("news_sentiment", 0.06),    # AI-scored daily news
]

def compute_mood_score() -> dict:
    # Returns: {score: 0-100, regime: "extreme_fear"|"fear"|"neutral"|"greed"|"extreme_greed",
    #          confidence: 0-1, contributing_factors: [...], contradicting_factors: [...]}
```

**New schema:**

```sql
CREATE TABLE market_mood (
    snapshot_date DATE PRIMARY KEY,
    mood_score INTEGER NOT NULL,           -- 0-100
    regime VARCHAR(20) NOT NULL,
    confidence_score NUMERIC(3,2),
    contributing_factors JSONB,
    contradicting_factors JSONB,
    ai_commentary TEXT,                    -- Sonnet-generated daily explainer
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mood_recent ON market_mood(snapshot_date DESC);
```

**New worker:** `celery-mood` runs at 9:00 AM IST (post-open) and 4:00 PM IST (post-close)

**APIs:**
- `GET /api/v1/market/mood` — anonymous, current mood + 30-day history
- `GET /api/v1/market/mood/history?from=...&to=...` — anonymous, full history
- `GET /api/v1/market/why-today` — anonymous, AI explainer

**Cost impact:** +₹450/month (mood AI calls + new Celery container)

---

## Recommendation 3 — Source Reliability Framework + Multi-Signal Schema 🟠 High

**Source:** Master Blueprint · **Effort:** Small · **Priority:** High

Master Blueprint defines a three-tier reliability framework (RBI/Fed/filings → journalists → social). v2.1 has no source weighting. Every AI output must carry confidence + contributing/contradicting signals.

**Implementation:**

```sql
CREATE TABLE source_reliability (
    domain VARCHAR(255) PRIMARY KEY,
    tier VARCHAR(20) NOT NULL,           -- 'high', 'medium', 'low'
    weight NUMERIC(3,2) NOT NULL,        -- 0.00 to 1.00
    category VARCHAR(50),                -- 'regulator', 'filing', 'journalist', 'social'
    last_reviewed DATE
);

-- Seed data
INSERT INTO source_reliability VALUES
('rbi.org.in', 'high', 1.00, 'regulator', '2026-05-01'),
('sebi.gov.in', 'high', 1.00, 'regulator', '2026-05-01'),
('bseindia.com', 'high', 1.00, 'filing', '2026-05-01'),
('nseindia.com', 'high', 1.00, 'filing', '2026-05-01'),
('moneycontrol.com', 'medium', 0.60, 'journalist', '2026-05-01'),
('economictimes.com', 'medium', 0.65, 'journalist', '2026-05-01'),
('twitter.com', 'low', 0.20, 'social', '2026-05-01');
```

**Schema enforcement on all AI outputs:**

```python
# Pydantic v2 — applies to StockPick, MFPick, MoodSnapshot, NewsSummary
class AIOutputBase(BaseModel):
    confidence_score: float = Field(ge=0.0, le=1.0)
    contributing_signals: list[str] = Field(min_length=2)  # min 2 sources
    contradicting_signals: list[str] = Field(default_factory=list)
    signal_age_hours: int = Field(ge=0)
    source_reliability_avg: float = Field(ge=0.0, le=1.0)
    
    @field_validator('confidence_score')
    @classmethod
    def confidence_requires_evidence(cls, v, info):
        signals = info.data.get('contributing_signals', [])
        if v > 0.7 and len(signals) < 3:
            raise ValueError("High confidence requires 3+ supporting signals")
        return v
```

**Cost impact:** +₹0/month (logic only)

---

## Recommendation 4 — Portfolio Intelligence Module 🟠 High

**Source:** Master Blueprint + competitor parity · **Effort:** Large · **Priority:** High

Master Blueprint specifies portfolio overlap, ETF overlap, diversification score, sector allocation, XIRR, drawdown. v2.1 has only `watchlist` table. Tickertape and Trendlyne have full portfolio analytics; INDmoney has tracking but no analytics. This is the strongest Pro tier hook.

**New schema:**

```sql
CREATE TABLE portfolios (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    name VARCHAR(100) NOT NULL,
    broker VARCHAR(20),                  -- 'zerodha', 'groww', 'upstox', 'manual'
    sync_enabled BOOLEAN DEFAULT false,
    last_synced TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE portfolio_holdings (
    id SERIAL PRIMARY KEY,
    portfolio_id INTEGER REFERENCES portfolios(id),
    instrument_type VARCHAR(20),         -- 'stock', 'mf', 'etf'
    ticker VARCHAR(20),
    quantity NUMERIC(15,4),
    avg_buy_price NUMERIC(15,2),
    buy_date DATE,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    portfolio_id INTEGER REFERENCES portfolios(id),
    snapshot_date DATE,
    total_value NUMERIC(15,2),
    invested_value NUMERIC(15,2),
    sector_allocation JSONB,
    diversification_score NUMERIC(3,2),  -- HHI inverse, 0-1
    xirr NUMERIC(6,4),
    max_drawdown NUMERIC(6,4),
    UNIQUE(portfolio_id, snapshot_date)
);
```

**New service module:**

```python
# backend/app/services/portfolio_intelligence.py
class PortfolioIntelligenceService:
    def compute_overlap(self, p1_id: int, p2_id: int) -> dict:
        # Jaccard similarity on holdings
        # Returns: {overlap_pct, common_holdings[], unique_to_p1[], unique_to_p2[]}
        
    def diversification_score(self, portfolio_id: int) -> dict:
        # Inverse Herfindahl-Hirschman Index on sector weights
        # Returns: {score: 0-1, sector_breakdown, concentration_warnings}
        
    def compute_xirr(self, portfolio_id: int) -> float:
        # Uses numpy_financial.xirr on cashflow history
        
    def max_drawdown(self, portfolio_id: int, lookback_days: int = 365) -> float:
        # Peak-to-trough decline
```

**Pro tier features:**
- Multi-broker sync (read-only): Zerodha, Groww, Upstox in Phase 1
- Overlap detection between MFs and direct stock holdings (e.g., "your MF already holds 12% Reliance, you also hold direct Reliance")
- Diversification score with sector concentration warnings
- XIRR vs NIFTY benchmark
- Maximum drawdown analysis

**Cost impact:** +₹350/month (broker API calls, additional DB load)

---

## Recommendation 5 — Market Data Adapter Layer 🟠 High

**Source:** Earlier architecture plan + Master Blueprint · **Effort:** Medium · **Priority:** High

v2.1 hardcodes NSE/AMFI ingestion. Master Blueprint and earlier plan both call for an adapter layer so providers can be swapped (Kite, Upstox, MFAPI, TwelveData). This mirrors the existing LLM Gateway pattern.

**Implementation:**

```
backend/app/gateway/market_data/
├── ports.py                 # MarketDataPort ABC
├── registry.py              # provider routing config
├── adapters/
│   ├── kite.py             # Kite Connect v3
│   ├── upstox.py
│   ├── mfapi.py            # mutual fund NAV
│   ├── amfi.py             # AMFI dump
│   ├── twelvedata.py       # historical fallback
│   └── nse_dump.py         # instrument master
└── circuit_breaker.py      # same pattern as LLM gateway
```

**Provider routing (config-driven, not code change):**

```yaml
# config/market_data_routing.yml
quotes:
  primary: upstox
  fallback: kite
  
historical:
  primary: kite
  fallback: twelvedata
  
mutual_fund_nav:
  primary: mfapi
  fallback: amfi
  
instrument_master:
  primary: nse_dump
```

**Cost impact:** Additional broker API costs only as utilized. Kite Connect ~₹500/month if added; free fallbacks (NSE/AMFI/MFAPI) are zero-cost.

---

## Recommendation 6 — "Why This Ranking" Explainability Panel 🟠 High

**Source:** Master Blueprint · **Effort:** Small · **Priority:** High

Tickertape, Trendlyne, and Liquide all show scores without exposing the model logic. DhanRadar's positioning *requires* explainability. This becomes a major differentiator.

**Implementation:**
- Every ranked list (top picks, MF rankings, screener results) has a "Why this ranking?" button
- Opens a panel showing the contributing factors and their weights
- For AI-generated rankings, shows the source signals + confidence breakdown
- Hover/tap on any metric (RSI, Sharpe, P/E) opens a 2-line plain-English explanation + link to learn page

**Frontend:**

```typescript
// frontend/components/RankingExplainer.tsx
interface RankingExplainerProps {
  itemId: string;
  factors: {
    name: string;
    weight: number;
    value: number | string;
    contribution: number;     // factor_weight × normalized_value
    explanation: string;      // plain English
  }[];
  modelConfidence: number;
  contradictingSignals: string[];
}
```

**Cost impact:** ~₹0 — frontend logic + existing data

---

## Recommendation 7 — Backtest Harness + Public Track Record Page 🟠 High

**Source:** New (research-driven) · **Effort:** Medium · **Priority:** High

If DhanRadar publishes picks with confidence scores, it must prove they work. Liquide and Jarvis Invest hide their hit rate. **A public Track Record page is a major trust signal** that competitors structurally cannot match.

**New schema:**

```sql
CREATE TABLE pick_outcomes (
    id SERIAL PRIMARY KEY,
    pick_id INTEGER REFERENCES stock_picks(id),
    pick_date DATE NOT NULL,
    confidence_band VARCHAR(20),         -- 'low', 'medium', 'high'
    return_30d NUMERIC(6,4),
    return_90d NUMERIC(6,4),
    return_365d NUMERIC(6,4),
    benchmark_return_30d NUMERIC(6,4),   -- NIFTY for comparison
    benchmark_return_90d NUMERIC(6,4),
    benchmark_return_365d NUMERIC(6,4),
    outcome_recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_outcomes_band_date ON pick_outcomes(confidence_band, pick_date);
```

**New worker:** `celery-outcomes` — nightly job that computes returns for picks aged 30/90/365 days

**Public page:** `/track-record` — anonymous-accessible

Shows:
- Hit rate by confidence band (high/medium/low confidence) over rolling 12 months
- Hit rate by sector
- Average return vs NIFTY by holding period
- Sample size and time period clearly stated
- "Last 100 picks" table with current status

**Cost impact:** +₹200/month (additional Celery worker)

---

## Recommendation 8 — Weekly Digest Engine 🟡 Medium

**Source:** Master Blueprint + research · **Effort:** Small · **Priority:** Medium

Master Blueprint lists email digests. v2.1 has SendGrid in stack but no digest service. Highest-retention email pattern in fintech.

**Implementation:**
- New worker `celery-digest` runs Sunday 9 AM IST
- Sends Pro users a personalized week-in-review:
  - Watchlist movers (top 3 up, top 3 down)
  - Mood Compass change vs last week
  - Top new pick in user's sectors
  - Portfolio diversification alert if sector concentration changed
  - One educational explainer relevant to recent market moves

**APIs:**
- `GET /api/v1/digest/preview` — Pro+ — see next week's digest preview
- `POST /api/v1/digest/preferences` — control content + frequency

**Cost impact:** +₹100/month (Sonnet calls for personalization + SendGrid)

---

## Recommendation 9 — Compliance Disclaimer Versioning + Audit Log 🟡 Medium

**Source:** New (regulatory hedging) · **Effort:** Small · **Priority:** Medium

v2.1 has the AI consent modal but no broader compliance scaffolding. Defensible if regulator inquires.

**New schema:**

```sql
CREATE TABLE disclaimers (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50) NOT NULL,           -- 'ai_picks', 'mf_research', 'mood', 'portfolio'
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    active BOOLEAN DEFAULT false,
    effective_from TIMESTAMPTZ,
    effective_to TIMESTAMPTZ,
    UNIQUE(type, version)
);

CREATE TABLE ai_recommendation_audit (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    served_at TIMESTAMPTZ DEFAULT NOW(),
    recommendation_type VARCHAR(50),     -- 'pick', 'mood', 'mf_ranking'
    content_hash VARCHAR(64),
    model VARCHAR(50),
    prompt_version VARCHAR(20),
    confidence_score NUMERIC(3,2),
    disclaimer_version INTEGER REFERENCES disclaimers(id)
);

-- Partition by month for performance
```

**Daily archival:**
- Disclaimer state screenshot stored in MinIO daily
- 7-year retention (matches SEBI standards)

**Cost impact:** +₹50/month (MinIO storage)

---

## Recommendation 10 — Historical Analogue Detection 🟡 Medium

**Source:** New (research-driven) · **Effort:** Small · **Priority:** Medium

"Today's market action most resembles 2018-Q3 or 2020-Q1." Cosine similarity on daily mood-vector against 15-year mood-vector history. **No competitor in India does this.** Highly shareable.

**Implementation:**

```python
# backend/app/services/historical_analogue.py
def find_analogues(current_date: date, top_n: int = 3) -> list[dict]:
    current_vector = build_mood_vector(current_date)
    
    historical = db.execute("""
        SELECT snapshot_date, mood_vector 
        FROM mood_history 
        WHERE snapshot_date < :cutoff
    """, {"cutoff": current_date - timedelta(days=180)})
    
    similarities = [
        (row.snapshot_date, cosine_similarity(current_vector, row.mood_vector))
        for row in historical
    ]
    return sorted(similarities, key=lambda x: x[1], reverse=True)[:top_n]
```

**Public-facing:**
- `/market/analogues` — anonymous-accessible
- Shows: "Today resembles 14-Sep-2018 (89% similar) and 23-Mar-2020 (76% similar)"
- For each analogue: market context, what happened next 30/90/365 days
- One-tap WhatsApp share

**Cost impact:** ~₹0 — pure compute on existing mood data

---

## Recommendation 11 — SEO Meta + ISR for Public Pages 🟡 Medium

**Source:** New (acquisition strategy) · **Effort:** Small · **Priority:** Medium

If anonymous access (Rec 1) is added, every public page must be SEO-optimized. Tickertape, Screener, and Moneycontrol all rank top-3 because their pages are crawlable.

**Implementation:**

```typescript
// frontend/app/stocks/[ticker]/page.tsx
export async function generateMetadata({ params }): Promise<Metadata> {
  const stock = await getStockByTicker(params.ticker);
  return {
    title: `${stock.name} Share Price, Score, Analysis — DhanRadar`,
    description: `${stock.name} (${stock.ticker}) stock analysis. DhanRadar Score ${stock.score}/100. Sector: ${stock.sector}. Latest news, fundamentals, peer comparison.`,
    openGraph: {
      title: `${stock.ticker} — DhanRadar Score ${stock.score}/100`,
      description: stock.brief_thesis,
      images: [`https://dhanradar.com/og/stock/${stock.ticker}.png`],
    },
  };
}

// 5-minute ISR
export const revalidate = 300;
```

**Pages with priority SEO:**
- Stock detail pages (`/stocks/[ticker]`)
- MF detail pages (`/mf/[scheme_code]`)
- ETF detail pages (`/etf/[ticker]`)
- Sector pages (`/sectors/[sector]`)
- Mood Compass (`/market/mood`)
- Track Record (`/track-record`)
- "Why X moved today" pages (`/market/movers/[date]`)

**Cost impact:** ~₹0 (Cloudflare CDN absorbs)

---

## Recommendation 12 — Behavioural Nudge Engine 🟡 Medium

**Source:** Master Blueprint extension · **Effort:** Medium · **Priority:** Medium

Master Blueprint mentions "Behavioral finance education" but it's static content. Contextual nudges differentiate massively. *"You viewed RELIANCE 8 times this week — consider whether this is conviction or anchoring."*

**New schema:**

```sql
CREATE TABLE user_behaviour_signals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    signal_type VARCHAR(50),             -- 'repeated_view', 'panic_check', 'fomo_pattern'
    ticker VARCHAR(20),
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB,
    nudge_shown BOOLEAN DEFAULT false,
    nudge_response VARCHAR(20)           -- 'dismissed', 'engaged', 'ignored'
);
```

**Nudge patterns:**
- **Repeated view nudge:** Same ticker viewed >5× in 7 days → "Conviction or anchoring? Here's how to tell."
- **Panic check nudge:** User opens portfolio >3× in a single trading day during market drop → "Frequent checking during volatility predicts worse outcomes."
- **FOMO nudge:** User views top-gainer chart immediately after viewing a stock that just rallied → "What's your investment thesis here?"

**Cost impact:** +₹50/month (Celery job + storage)

---

## Recommendation 13 — Read-Only Public API Tier 🟢 Low (Phase 6)

**Source:** Earlier architecture plan · **Effort:** Medium · **Priority:** Low (defer)

Tickertape doesn't expose this; underserved market. Adapter layer (Rec 5) makes this nearly free.

**Implementation:**
- Same FastAPI routes as web frontend
- API key auth via new `api_keys` table
- Separate rate limit tier: Developer (₹2,000/mo, 10K calls/day), Business (₹15,000/mo, 100K calls/day)
- Documentation auto-generated from FastAPI OpenAPI spec
- Webhook support for alerts

**Cost impact:** Defer to Year 2

---

## Recommendation 14 — Quarterly Risk-Profile Drift Nudge 🟢 Low

**Source:** New (UX + regulatory hedging) · **Effort:** Extra Small · **Priority:** Low

v2.1 onboarding (P6) captures `risk_profile` once. Risk tolerance drifts. Also a regulatory hedge.

**Implementation:**
- Cron job: every 90 days, push notification to retake 5-question risk quiz
- Show diff visualization: old profile vs new profile
- Update `users.risk_profile` only with user confirmation
- Audit log of all risk profile changes

**Cost impact:** ~₹0

---

# Part III — Additional v2.2 Recommendations from Competitor Research

These are not in the original 14 but emerged from competitor analysis and should ship alongside v2.2.

## R15 — DhanRadar Score (5-Axis Stock Scorecard) 🟠 High

Equivalent to Tickertape's Investment Scorecard, Trendlyne's DVM, Simply Wall St's Snowflake. Without one of these, DhanRadar isn't taken seriously.

**Five axes:** Quality · Valuation · Momentum · Risk · Trend

Each axis 0–100, click-through to see contributing factors. Aggregate score is weighted average. Visible on every stock page (anonymous + authed).

## R16 — SWOT Engine 🟠 High

Trendlyne has this; LLM-fit perfectly. Auto-generated weekly per stock by Sonnet, refreshed on earnings. Cached 7 days. Public-facing on stock detail pages.

## R17 — Earnings Call AI Summary Library 🟠 High

Public.com and Trendlyne both have this. Auto-generated 24h post-results announcement. Free for anonymous users on stock detail pages — major SEO + share driver.

## R18 — Daily Mood Compass to WhatsApp/Telegram 🔴 Critical (acquisition)

Free public WhatsApp + Telegram channel pushes the daily Mood Compass at 9:00 AM IST. Forwardable PNG card. Single most important acquisition mechanic for India.

## R19 — Portfolio Report Card Share Cards 🟡 Medium

OG-tagged PNG generated on demand: portfolio score, sector breakdown, vs NIFTY benchmark. Shareable to WhatsApp groups. Humble-brag mechanic that drives organic acquisition.

## R20 — "Why X Moved Today" Public Pages 🟠 High

For top 50 daily movers, auto-generate AI-explained pages (`/market/movers/2026-05-08/RELIANCE`). High-volume SEO landing pages. Free for anonymous users. Massive Google query coverage ("why did Reliance fall today").

## R21 — Lifetime Founder Pricing (First 1,000 Users) 🟡 Medium (launch)

Limited-time ₹4,999 lifetime Pro for first 1,000 signups. Generates ~₹50L upfront capital, creates evangelist user base, runs 21–30 days max. Standard challenger play in saturated markets.

## R22 — Refer-3-Get-Pro-Free with Variable Rewards 🟡 Medium

Variable rewards drive 30–50% higher sharing rates than fixed cash bonuses. After 3 successful referrals: random reward from {1 month Pro free / 1 week Pro+ free / DhanRadar OG badge / ₹500 broker partner credit}.

## R23 — Spin-the-Wheel on Signup 🟡 Medium

CRED-style mechanic. Single spin on signup: {1-month Pro / 1-week Pro+ / lifetime ₹100 off / standard welcome}. Boosts signup completion by 15–25% in Indian fintech contexts.

## R24 — Creator Partnership Program 🔴 Critical (marketing)

Budget ₹2–3L/month for first 6 months. Flat-fee partnerships (no revenue share). Target Indian finance creators: Pranjal Kamra, Akshat Shrivastava, CA Rachana Ranade tier (₹1.5L/sponsorship); micro-influencers ₹15–30K/sponsorship. Custom UTM tracking per creator.

---

# Part IV — Revised Subscription Tiering (v2.2)

## The Four Tiers

### Anonymous (₹0, no signup)
**Purpose:** SEO acquisition + funnel top.

- All public stock/MF/ETF detail pages with DhanRadar Score
- Top 5 picks per category (lower fidelity)
- Mood Compass (full)
- "Why X moved today" for top 50 daily movers
- Historical Analogue Detection
- 5 stock screener queries/day per IP
- Public Track Record page (full)
- Educational content + explainers

### Free Signed-In (₹0, account)
**Purpose:** Identification, retention, gamification eligible.

All anonymous features plus:
- 3 watchlists, max 25 stocks each
- 10 price alerts, 3 screener alerts (daily refresh)
- Read-only broker portfolio sync (1 broker)
- Basic portfolio overlap report
- AI chat: 5 messages/day
- Weekly digest email (light version)

### Pro (₹199/month or ₹1,999/year)
**Purpose:** Mass-market premium. Below Tickertape's ₹2,399/yr anchor.

All free features plus:
- Unlimited watchlists + alerts
- Full 130+ filter screener with 15-min refresh on alerts
- Multi-broker portfolio sync (up to 3 brokers)
- Full portfolio analytics: overlap, diversification, drawdown, XIRR
- MF fund manager tracking + red flags
- AI chat: 50 messages/day
- Earnings call AI summaries (full library)
- Historical analogue detection (extended)
- SWOT engine per stock (full)
- Data exports (CSV)
- Personalized weekly digest (full)
- Ad-free everywhere

### Pro+ (₹499/month or ₹3,999/year)
**Purpose:** Power user / serious retail. Sits between Tickertape and Trendlyne Pro Plus.

All Pro features plus:
- Unlimited broker syncs + family/joint portfolios
- AI chat: unlimited
- 5-minute refresh on screener alerts
- Excel/Google Sheets live add-in
- Backtesting engine (run a screen historically)
- Priority support (24h response SLA)
- API access (10,000 calls/day)
- Beta features early access
- Quarterly deep-dive research reports

## Pricing Rationale

| Decision | Anchor | Rationale |
|---|---|---|
| Pro at ₹199/mo | Tickertape ₹249/mo | 20% undercut — challenger move |
| Pro at ₹1,999/yr | Tickertape ₹2,399/yr | ₹400 undercut — meaningful but not desperate |
| Pro+ at ₹3,999/yr | Trendlyne ₹11,900/yr | Captures serious-retail without entering pro/institutional pricing |
| Annual discount 33% | Industry standard 30–40% | Psychological breakpoint for Indian users |
| Founder lifetime ₹4,999 | Industry common | Limited 21–30 days, capped at 1,000 users |

---

# Part V — Cost Impact Analysis

## Monthly Operating Cost: v2.1 vs v2.2

| Line Item | v2.1 | v2.2 | Delta |
|---|---|---|---|
| Hetzner CPX21 VPS | ₹1,680 | ₹1,680 | ₹0 |
| Stock batch AI (Haiku) | ₹3,780 | ₹3,780 | ₹0 |
| MF/ETF batch AI (Haiku) | ₹1,008 | ₹1,008 | ₹0 |
| News AI (Gemini Flash-Lite) | ₹168 | ₹168 | ₹0 |
| Search AI (Haiku) | ₹420 | ₹420 | ₹0 |
| Content AI (Sonnet) | ₹336 | ₹336 | ₹0 |
| AI chat (Sonnet) | ₹588 | ₹588 | ₹0 |
| **Mood Compass AI + worker** | — | ₹450 | +₹450 |
| **Portfolio sync (broker APIs)** | — | ₹350 | +₹350 |
| **Track Record worker** | — | ₹200 | +₹200 |
| **Digest worker (Sonnet + SendGrid)** | — | ₹100 | +₹100 |
| **Behavioural nudges** | — | ₹50 | +₹50 |
| **Compliance archival (MinIO)** | — | ₹50 | +₹50 |
| Domain + Cloudflare | ₹84 | ₹84 | ₹0 |
| Claude Pro dev account | ₹1,680 | ₹1,680 | ₹0 |
| Loki + Promtail (self-hosted) | ₹0 | ₹0 | ₹0 |
| All other free tiers | ₹0 | ₹0 | ₹0 |
| **Subtotal infrastructure** | **₹9,744** | **₹10,944** | **+₹1,200** |
| **Creator partnerships (months 1–6)** | — | ₹250,000 | +₹250,000 |

## Budget Utilization

- v2.1: ₹9,744 / ₹15,000 = 65% utilization
- v2.2 infrastructure: ₹10,944 / ₹15,000 = 73% utilization
- Buffer: ₹4,056

**Creator partnership budget is separate from infrastructure** and should be tracked under marketing/CAC, not ops. At ~₹50K/month (lower-end), it represents ~₹500 CAC if 100 paid signups/month result — still well below performance marketing CAC of ₹800–2,500.

## Break-even Analysis (v2.2)

- Monthly infrastructure: ₹10,944
- Pro at ₹199/mo, contribution ₹150/mo (after payment processing)
- **Break-even: 73 Pro subscribers** (or 14 Pro+ at ₹500 contribution)
- v2.1 break-even was 20 Pro at ₹499/mo — v2.2 needs 3.6× more subscribers but at ~40% the price each, which is dramatically more achievable in the Indian market

---

# Part VI — Phased Implementation Plan (18 Weeks)

v2.2 extends v2.1's 14-week plan by 4 weeks to absorb new features. Critical reordering: acquisition mechanics ship before retention mechanics.

## Phase 1 — Foundation + Anonymous Access (Weeks 1–2)
**Theme:** Setup + open the front door.

- Docker Compose (19 services from v2.1 + 3 new workers from v2.2)
- PostgreSQL schema including all v2.2 tables (mood, source_reliability, portfolios, pick_outcomes, disclaimers, audit log, behaviour_signals)
- Index creation (CONCURRENTLY)
- **Anonymous tier — Nginx config, Redis `anon:` namespace, public route allowlist**
- Cloudflare ISR setup
- structlog PII masking
- FastAPI deps.py DI pattern
- GitHub Actions CI with pytest gate + Dependabot

**Priority:** Critical · **Output:** Public-facing site is live (no signup required) on Day 14

## Phase 2 — Mood Compass + Public Discovery (Weeks 3–4)
**Theme:** Acquisition magnets.

- Data ingestion pipeline + Bloom/SimHash dedup
- Market Data Adapter Layer (Rec 5)
- **Mood Compass module (Rec 2)** — daily worker, public API, frontend
- **Source Reliability framework (Rec 3)**
- **DhanRadar Score (R15)** — 5-axis scorecard live on every stock page
- **Historical Analogue Detection (Rec 10)**
- SEO meta + OG tags for all public pages (Rec 11)
- PostgreSQL read replica setup
- Loki + Promtail log aggregation, SLO dashboard

**Priority:** Critical · **Output:** Mood Compass is live and shareable; SEO begins indexing

## Phase 3 — AI Engine + Explainability (Weeks 5–7)
**Theme:** What separates DhanRadar from competitors.

- LLM Gateway, batch workers
- AI chat widget (Sonnet)
- **"Why this ranking" explainability panel (Rec 6)**
- **Multi-signal schema enforcement on all AI outputs (Rec 3)**
- **SWOT engine (R16)** — Sonnet-generated weekly per stock
- **Earnings AI summary library (R17)**
- **"Why X moved today" public pages (R20)**
- AI consent modal + enforcement
- TOTP 2FA for Pro actions
- **Compliance disclaimer versioning + audit log (Rec 9)**

**Priority:** High · **Output:** Full public AI explainer suite live; trust signals operational

## Phase 4 — Frontend + Onboarding (Weeks 8–10)
**Theme:** Convert anonymous to authenticated.

- Next.js dynamic imports, bundle analysis
- TanStack Query, PWA
- PostHog feature flags
- 5-step onboarding flow with risk quiz
- **Spin-the-wheel signup mechanic (R23)**
- Share card buttons on every pick / portfolio / mood card
- **Public Track Record page (Rec 7)** with backtest harness
- **Behavioural nudge engine (Rec 12)**

**Priority:** High · **Output:** Free-signed-in tier launches with full UX

## Phase 5 — Portfolio Intelligence + Pro Launch (Weeks 11–13)
**Theme:** What Pro users pay for.

- **Portfolio Intelligence module (Rec 4)** — overlap, diversification, XIRR, drawdown
- **Multi-broker sync** — Zerodha, Groww, Upstox first
- **MF fund manager tracking + red flags**
- **Weekly digest engine (Rec 8)**
- **Quarterly risk-profile drift nudge (Rec 14)**
- Razorpay subscription integration
- **Pro and Pro+ tiers go live**
- **Lifetime Founder pricing (R21)** — first 1,000 users

**Priority:** Critical · **Output:** Subscription revenue begins

## Phase 6 — Growth Mechanics + Distribution (Weeks 14–16)
**Theme:** Compounding loops.

- Gamification engine (badges, streaks, milestones — from v2.1)
- **Refer-3-Get-Pro-Free with variable rewards (R22)**
- **Portfolio Report Card share cards (R19)**
- **Daily Mood Compass to WhatsApp + Telegram (R18)**
- Telegram Bot for personalized alerts
- Instagram + WhatsApp social posting automation
- **Creator partnership program activation (R24)** — first 5 partnerships live

**Priority:** High · **Output:** Viral coefficients begin; CAC drops as creator content compounds

## Phase 7 — Launch Prep + Hardening (Weeks 17–18)
**Theme:** Production readiness.

- k6 load test (200 concurrent — verify SLOs)
- Full OWASP security review
- Snyk scan pass
- 80% pytest coverage gate confirmed
- Compliance review with legal counsel
- Disclaimer copy finalized + versioned
- Staged rollout (10% → 50% → 100% over 14 days)
- **Production go-live**

**Priority:** Critical · **Output:** v2.2 is live in production

---

# Part VII — Strategic Positioning Summary

## DhanRadar's Defensible USPs (post-v2.2)

| USP | Evidence Layer |
|---|---|
| **The most explainable analytics platform in India** | "Why this ranking" panel (Rec 6) + multi-signal schema (Rec 3) + DhanRadar Score breakdown (R15) |
| **Honest about what we don't know** | Public Track Record (Rec 7) + confidence bands + signal contradiction warnings |
| **No signup, no wall — real intelligence** | Anonymous tier (Rec 1) + SEO discovery (Rec 11) + free Mood Compass (Rec 2) |
| **Multi-asset, India-native, multi-signal AI** | Source reliability framework (Rec 3) + Adapter Layer (Rec 5) + Mood Compass 11-input regime indicator (Rec 2) |
| **Educational by design, not by disclaimer** | Every metric has explanation + Why-X-moved pages (R20) + behavioural nudges (Rec 12) |
| **The first Indian platform with public Track Record** | Auto-generated daily — no competitor has this |

## What DhanRadar Will NOT Do (Strategic Boundaries)

These boundaries are explicit and product-shaping. They are advantages, not limitations.

- **No buy/sell stock recommendations** — preserves educational positioning, avoids SEBI RA registration
- **No advisory portfolios / Smallcase-style baskets** — same reason
- **No order placement or brokerage** — different business model entirely
- **No social feed showing other users' portfolios** — Indian market not ready; finfluencer regulations evolving
- **No dynamic auto-rebalancing** — discretionary advisory territory
- **No confetti / celebration animations on actions** — gambling-style design conflicts with serious analytics positioning
- **No day-trader features** (Greeks, intraday alerts) — conflicts with educational long-term positioning
- **No "guaranteed returns" or "predict the market" content** — SEBI minefield + erodes trust
- **No revenue share with creators** — creates bias; flat fees only
- **No selling user data** — non-starter

---

# Part VIII — Risk Register & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| SEBI clarifies that AI-generated picks require RA registration | Medium | High | Disclaimer versioning (Rec 9) + audit log + compliance review with counsel pre-launch + feature flag to geo/region disable AI picks |
| Tickertape replicates Mood Compass differentiation | High | Medium | Open-source the methodology; Track Record + multi-signal moat is harder to copy than a score |
| Creator partnerships underperform CAC targets | Medium | Medium | Limit initial commitments to 1-month flat fees; A/B test creators before annual deals |
| Indian retail churn higher than projected (>15%/month) | Medium | High | Lifetime founder pricing absorbs early churn; weekly digest + behavioural nudges target retention; downgrade-to-free path before churn |
| Hetzner CPX21 capacity insufficient at 100K MAU | Low | High | Scale to CPX31 (~₹3,200/mo); read replica already exists in v2.1; CDN absorbs anonymous load |
| Broker API access revoked (e.g., Angel One precedent) | Medium | Medium | Adapter layer (Rec 5) makes provider swap config-only; user always has manual import path |
| AI cost spikes from chat abuse | Medium | Medium | LLM gateway budget cap exists in v2.1; rate limits per tier; hard stop at ₹13,000/month |
| Competitor lawsuit on "Mood Index" trademark | Low | Low | Renamed to "Mood Compass" (Finding 4); free term |

---

# Part IX — Success Metrics (12 Months Post-Launch)

| Metric | Target | Source |
|---|---|---|
| Monthly Active Users (MAU) | 100,000 | PostHog |
| Anonymous traffic / total | 60–70% | Cloudflare + PostHog |
| Free signed-in / MAU | 30% | Database |
| Pro subscribers | 2,000 | Razorpay |
| Pro+ subscribers | 200 | Razorpay |
| Annual recurring revenue | ₹50L | Razorpay |
| Track Record published hit rate (high confidence band, 90-day) | >55% beat NIFTY | pick_outcomes table |
| Mood Compass daily WhatsApp subscribers | 25,000 | WhatsApp Business API |
| Creator-attributed signups | 25% of paid signups | UTM tracking |
| Pro tier 6-month retention | >60% | Razorpay churn |
| NPS | >40 | Quarterly survey |
| API P99 latency | <200ms | Grafana SLO dashboard |
| SLO error budget consumed | <80% | Grafana |

---

# Appendix A — Complete v2.2 Recommendation Matrix

| # | Recommendation | Priority | Phase | Effort | Source |
|---|---|---|---|---|---|
| Rec 1 | Anonymous-First Access Tier | 🔴 Critical | 1 | M | Master Blueprint |
| Rec 2 | Mood Compass Module | 🔴 Critical | 2 | L | Master Blueprint |
| Rec 3 | Source Reliability + Multi-Signal Schema | 🟠 High | 2 | S | Master Blueprint |
| Rec 4 | Portfolio Intelligence Module | 🟠 High | 5 | L | Master Blueprint |
| Rec 5 | Market Data Adapter Layer | 🟠 High | 2 | M | Earlier plan |
| Rec 6 | "Why This Ranking" Explainability Panel | 🟠 High | 3 | S | Master Blueprint |
| Rec 7 | Backtest Harness + Public Track Record | 🟠 High | 4 | M | Research-driven |
| Rec 8 | Weekly Digest Engine | 🟡 Medium | 5 | S | Master Blueprint |
| Rec 9 | Compliance Disclaimer Versioning + Audit | 🟡 Medium | 3 | S | New |
| Rec 10 | Historical Analogue Detection | 🟡 Medium | 2 | S | New |
| Rec 11 | SEO Meta + ISR for Public Pages | 🟡 Medium | 2 | S | New |
| Rec 12 | Behavioural Nudge Engine | 🟡 Medium | 4 | M | Master Blueprint ext |
| Rec 13 | Read-Only Public API Tier | 🟢 Low | 6 (Year 2) | M | Earlier plan |
| Rec 14 | Quarterly Risk-Profile Drift Nudge | 🟢 Low | 5 | XS | New |
| R15 | DhanRadar Score (5-Axis) | 🟠 High | 2 | M | Competitor parity |
| R16 | SWOT Engine | 🟠 High | 3 | S | Competitor parity |
| R17 | Earnings Call AI Summaries | 🟠 High | 3 | S | Competitor parity |
| R18 | Daily Mood Compass to WhatsApp/Telegram | 🔴 Critical | 6 | S | Acquisition |
| R19 | Portfolio Report Card Share Cards | 🟡 Medium | 6 | S | Viral |
| R20 | "Why X Moved Today" Public Pages | 🟠 High | 3 | S | SEO |
| R21 | Lifetime Founder Pricing | 🟡 Medium | 5 | XS | Launch tactic |
| R22 | Refer-3-Get-Pro-Free Variable Rewards | 🟡 Medium | 6 | S | Viral |
| R23 | Spin-the-Wheel on Signup | 🟡 Medium | 4 | S | Conversion |
| R24 | Creator Partnership Program | 🔴 Critical | 6 | M | Acquisition |

---

# Appendix B — Pricing Comparison Reference

| Platform | Free | Entry | Mid | Top | Annual Anchor |
|---|---|---|---|---|---|
| Tickertape | ✓ | ₹249/mo | — | — | ₹2,399/yr |
| Screener.in | ✓ | ₹4,999/yr | — | — | ₹4,999/yr |
| Trendlyne | ✓ | GuruQ | StratQ | Pro Plus | ~₹11,900/yr |
| ETMoney Genius | App free | ₹249/qtr | — | — | ~₹996/yr |
| Liquide | ✓ | One subscription | — | — | Variable |
| Seeking Alpha (US) | ✓ | $299/yr | $499/yr | $2,400/yr | $299/yr |
| Simply Wall St | Limited | ~$120/yr | — | — | ~$120/yr |
| Koyfin | ✓ | $180/yr | $420/yr | $840/yr | $180/yr |
| FinChat / Fiscal.ai | Limited | $348/yr | — | — | $348/yr |
| **DhanRadar (v2.2)** | ✓ Anonymous + Free | **₹1,999/yr** | **₹3,999/yr** | — | **₹1,999/yr** |

DhanRadar's annual Pro is positioned 17% below Tickertape's anchor. Pro+ at ₹3,999/yr fills the gap between Tickertape and Trendlyne — currently underserved.

---

**End of v2.2 Strategic & Architectural Update**

*Builds on v2.1 architecture. All 14 v2.1 gaps remain resolved. v2.2 adds 14 strategic recommendations + 10 competitor-research-driven enhancements + revised pricing aligned to Indian market reality + 18-week phased implementation plan.*

*Total infrastructure cost: ₹10,944/month (+₹1,200 vs v2.1) — 73% of ₹15,000 budget. Marketing budget: ₹2.5L over 6 months for creator partnerships.*

*Break-even at 73 Pro subscribers. Year 1 target: ₹50L ARR at 2,200 paid subscribers across Pro and Pro+ tiers.*

DhanRadar v2.2 — Confidential | dhanradar.in | Development Ready