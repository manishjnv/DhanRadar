# DhanRadar — Product Strategy Document

*Investment intelligence for Indian retail investors. Branding, type, color and logo are locked — this doc covers strategy only.*

**Prepared by:** Product · UX Research · Fintech Strategy · Advisory Product · Growth
**Date:** June 2026 · **Status:** v1 for review

---

## 0. Executive summary

India has ~110M demat accounts but the overwhelming majority of retail investors **transact without research**. Brokers (Groww, Zerodha) have nailed *execution*; data terminals (Tickertape, MoneyControl) have nailed *information*. Almost nobody has nailed the **decision** — the layer between "I have ₹10,000" and "I should buy this, and here's why, in plain English."

DhanRadar's wedge is the **DhanRadar Score**: a 0–100 composite that compresses valuation, growth, quality, momentum and risk into one trustworthy, explained number — plus an AI layer that answers *"why"* and *"what should I do"* in plain Hindi/English.

We win not by having more data, but by **turning data into a defensible decision** faster and more honestly than anyone else.

---

## 1. Target audience

### Primary market
Indian retail investors, age 25–45, urban + tier-2, ₹3L–₹25L annual income, who already have a demat account and invest directly in stocks and/or mutual funds but feel **under-equipped to research**.

### Market sizing (directional)
| Layer | Size | DhanRadar relevance |
|---|---|---|
| Demat accounts (India) | ~110M | Total addressable |
| Active direct-equity investors | ~35M | Serviceable |
| Research-seeking, willing to pay | ~6–9M | Target |
| Realistic 3-yr reachable | ~1.5–2M | Beachhead |

### Who we are NOT for (explicitly)
- **Intraday/F&O traders** chasing tick-level signals → TradingView owns this.
- **Pure passive SIP-only** investors who never want to look → Groww/Coin auto-pilot owns this.
- **HNI/PMS clients** who want a human advisor → out of scope.

Saying no to these keeps the product focused on the *researching long-term-ish retail investor*.

---

## 2. User personas

### Persona matrix (5 personas across 2 axes: confidence × involvement)

| | Low involvement | High involvement |
|---|---|---|
| **Low confidence** | **Anjali** (Beginner SIP investor) | **Rohan** (Aspiring stock picker) |
| **High confidence** | **Meera** (Time-poor professional) | **Vikram** (Self-directed value investor) |
| **Cross-cutting** | | **Suresh** (Learner / finance student) |

---

#### P1 — Anjali, 28 · "The cautious starter"
- **Context:** Marketing exec, Pune. Started SIPs on Groww 1 yr ago. ₹8K/month across 3 funds she picked from a "top funds" list.
- **Goal:** Not lose money; understand if her funds are actually good.
- **Frustration:** Every app shows past returns; none tell her if a fund is *right* or *risky*.
- **DhanRadar value:** Fund Score + plain-English "why" + risk flag. "Your small-cap fund is high-risk — here's what that means for you."
- **Willingness to pay:** Low initially; converts after one "aha" moment.

#### P2 — Rohan, 31 · "The aspiring picker"
- **Context:** IT engineer, Bengaluru. Wants to pick individual stocks, watches finfluencers, burned once on a hype stock.
- **Goal:** Pick stocks with conviction, stop relying on Telegram tips.
- **Frustration:** Doesn't know how to read a balance sheet; screeners overwhelm him.
- **DhanRadar value:** Stock Score + factor breakdown + SWOT + "explain this metric." Screener presets so he doesn't start from a blank slate.
- **WTP:** Medium-high. **This is our sweet-spot Pro convert.**

#### P3 — Meera, 38 · "The time-poor professional"
- **Context:** Doctor, Delhi. Decent portfolio (₹15L), no time to track it. Checks once a month.
- **Goal:** Confidence her portfolio is healthy without spending hours.
- **Frustration:** Portfolio sync is fragmented; no single "is everything OK?" view.
- **DhanRadar value:** Portfolio Score + monthly health report + alerts only when something matters.
- **WTP:** High — values time over money. **Premium convert.**

#### P4 — Vikram, 44 · "The self-directed value investor"
- **Context:** Business owner, Surat. 12 yrs investing, reads annual reports, uses Screener.in + Tickertape.
- **Goal:** Faster fundamental research; multi-model fair value; peer comparison.
- **Frustration:** Tools are either too shallow (broker apps) or too manual (Screener.in queries).
- **DhanRadar value:** Fair Value (DCF + relative + EPV), deep financials, custom screeners, compare. Will stress-test our numbers.
- **WTP:** High but demanding — churns if data quality slips. **Power user / credibility anchor.**

#### P5 — Suresh, 22 · "The learner"
- **Context:** Final-year commerce student, Indore. Small portfolio (₹40K), high curiosity.
- **Goal:** Learn investing properly; build a track record.
- **Frustration:** Zerodha Varsity is great but disconnected from a live portfolio.
- **DhanRadar value:** Learn hub tied to live data; "explain every metric"; gamified streaks.
- **WTP:** Low now, **high LTV later** — acquire cheap, grow with them.

---

## 3. Jobs To Be Done

Framed as `When ___, I want to ___, so I can ___.`

### Core JTBD (must win)
1. **Evaluate a single instrument** — *When I hear about a stock/fund, I want to know quickly if it's good and why, so I can decide without spreadsheet work.* → **DhanRadar Score + AI explain**
2. **Decide buy/hold/avoid** — *When I'm about to invest, I want a clear signal with reasoning, so I act with conviction instead of FOMO.* → **Signal + Fair Value**
3. **Monitor what I own** — *When time passes, I want to know if my holdings still hold up, so I'm not blindsided.* → **Portfolio Score + alerts**

### Supporting JTBD
4. **Compare options** — *When choosing between 2–3 instruments, I want them side by side, so I pick the better one.*
5. **Screen for ideas** — *When I have cash to deploy, I want a filtered shortlist, so I don't stare at 4,000 stocks.*
6. **Understand a concept** — *When I hit a term I don't know, I want it explained in context, so I learn while doing.*
7. **Plan systematically** — *When building wealth long-term, I want SIP/goal tools, so I stay disciplined.*

### Emotional JTBD (the real differentiator)
8. **Feel in control** — *I want to feel like a competent investor, not a gambler.*
9. **Trust the source** — *I want data I can rely on, free of influencer hype and hidden agendas.*

> **Strategic read:** Brokers serve JTBD #7 and execution. Terminals serve #4–5. **Nobody owns #1, #2, #8, #9 well.** That's our territory.

---

## 4. Customer pain points

| # | Pain | Today's reality | DhanRadar fix |
|---|---|---|---|
| 1 | **Data overload** | 80+ metrics, no synthesis | One score + AI summary |
| 2 | **No "so what?"** | Numbers without interpretation | Plain-English reasoning on every metric |
| 3 | **Hype & noise** | Telegram tips, finfluencer pumps | Honest, factor-based, agenda-free signals |
| 4 | **Jargon wall** | "ROCE", "Sharpe" with no explanation | Inline "explain this" everywhere |
| 5 | **Fragmented portfolio** | Holdings across 3 brokers, no unified health view | Aggregated Portfolio Score |
| 6 | **Fund selection by past returns** | "Top performers" lists = recency bias | Risk-adjusted, forward-aware fund scoring |
| 7 | **No timely nudges** | Either notification spam or silence | Alerts only when score/price/risk moves materially |
| 8 | **Research is slow** | Tab-hopping across 5 tools | One surface: score → reasoning → action |
| 9 | **Trust deficit** | "Is this app trying to sell me something?" | Transparent methodology, research-not-advice positioning |

---

## 5. Market positioning

### Positioning statement
> *For Indian retail investors who want to research before they invest, DhanRadar is the investment-intelligence platform that turns complex market data into one trustworthy score and a plain-English answer — unlike brokers that only help you transact or terminals that bury you in data.*

### Competitive landscape (2×2: Execution ↔ Intelligence, Beginner ↔ Expert)

```
                    INTELLIGENCE / RESEARCH
                            ▲
         Seeking Alpha •    │    • TradingView
              MoneyControl •│  • Screener.in
                            │ ★ DhanRadar
         Tickertape •       │
                            │      • Value Research
   ─────────────────────────┼─────────────────────────▶
   BEGINNER                 │                  EXPERT
                            │
              Groww •       │   • Zerodha (Kite/Coin)
                ET Money •  │
                            │
                            ▼
                     EXECUTION / TRANSACT
```

**The gap we own:** *Intelligence + accessible to beginners-through-intermediate*. Tickertape is closest but skews data-display over decision-guidance and lacks a strong AI-explanation layer. Seeking Alpha is US-only and analyst-opinion-led, not scored.

### Benchmark teardown

| Competitor | Strength | Weakness we exploit |
|---|---|---|
| **Tickertape** | Clean data depth, scorecards | Display > decision; AI/explanation thin; weak portfolio intelligence |
| **Groww** | Mass simplicity, UX, execution | Almost no research depth; "top funds" recency bias |
| **ET Money** | Fund analytics, SIP tools | Equity research shallow; push toward own products |
| **Zerodha Coin** | Direct funds, trust, ecosystem | Deliberately minimal research; expects DIY |
| **TradingView** | Charts, technicals, global | Trader-first, intimidating for beginners; weak fundamentals/India fund data |
| **MoneyControl** | News breadth, mass reach | Cluttered, ad-heavy, low trust, no synthesis |
| **Seeking Alpha** | Quant ratings + analyst depth | US-only; opinion-heavy; not India-localized |

### Differentiation pillars (the moat)
1. **The Score** — proprietary, explained, sector-normalized, trusted.
2. **AI reasoning layer** — every score/metric answerable in natural language ("why is this 86?").
3. **Honest by design** — research not advice; no order-flow conflict; methodology published.
4. **India-native** — ₹ conventions, SEBI context, Indian instruments, Hindi/English.
5. **Decision-complete** — score → reasoning → fair value → action, on one surface.

---

## 6. Product differentiation (defensibility)

| Layer | What | Defensibility |
|---|---|---|
| **Data** | Aggregated fundamentals, prices, fund data | Low (commodity) — table stakes |
| **Score model** | Multi-factor composite, sector-normalized | Medium — methodology + tuning |
| **AI explanation** | RAG over our data + reasoning, in plain language | Medium-high — UX + data integration |
| **Trust brand** | "The honest, no-hype score" | High — compounds over time |
| **Engagement loop** | Watchlist → alert → re-score → re-decide | High — switching cost via habit + portfolio history |

> **Strategic note:** Data is not our moat — *interpretation + trust + habit* is. Invest there.

---

## 7. Subscription model

Three tiers (branding already supports Free / Pro / Premium).

| | **Free** | **Pro — ₹399/mo** | **Premium — ₹899/mo** |
|---|---|---|---|
| **Who** | Anjali, Suresh | Rohan, Meera | Vikram, Meera |
| Stock/fund lookups | 20/mo | Unlimited | Unlimited |
| DhanRadar Score | Basic | Full + factor breakdown | Full + history |
| AI explain | 5 queries/mo | Unlimited | Unlimited + deep dives |
| Fair Value estimate | — | ✓ | ✓ + scenarios |
| Screeners | 10 basic filters | 50+ filters, save/share | 50+ + custom formulas |
| Watchlists / alerts | 1 / basic | 10 / smart alerts | Unlimited / priority |
| Portfolio analytics | Basic value | Full + risk report | Full + tax optimization |
| Compare | 2 instruments | 3 instruments | 3 + export |
| Support | Community | Email 24h | Priority 4h |

**Pricing rationale**
- ₹399 sits below the psychological ₹500 threshold and roughly matches a "one coffee/week" frame.
- Annual plans at ~20% off (₹3,830/yr Pro) to lift LTV and cut churn.
- 14-day Pro trial, **no card required** (reduces signup friction; trust-consistent).
- Student plan (Suresh): Pro at ₹149/mo with .edu/college verification — cheap acquisition of high-LTV cohort.

---

## 8. Monetization model

### Primary: subscriptions (target ~75% of revenue)
Recurring, predictable, aligns incentives with user success (we win when they keep researching, not when they trade).

### Secondary (carefully chosen to protect trust)
| Stream | Description | Trust risk | Verdict |
|---|---|---|---|
| **Subscriptions** | Free/Pro/Premium | None | **Core** |
| **Annual upsell** | 20% off yearly | None | **Core** |
| **B2B2C / API** | License Score to brokers, advisors, fintechs | Low | **High-potential — Phase 3** |
| **White-label research** | Co-branded reports for wealth platforms | Low | Phase 3 |
| **Affiliate (broker signup)** | Refer to demat partners | Medium | OK if clearly labelled, never tied to a Score |
| **Sponsored / ads** | Display ads | **High** | **Avoid** — kills "no-hype" positioning |
| **Selling user data** | — | Fatal | **Never** |

> **Hard rule:** No monetization stream may ever influence a Score or a buy/sell signal. The moment users suspect the number is for sale, the product is dead. This constraint is the product.

### Unit-economics targets (directional, year 2)
- Free → Pro conversion: **4–6%**
- Blended ARPU (paying): **~₹430/mo**
- Target CAC: **< ₹600** (content + SEO led, not paid-heavy)
- Target LTV:CAC: **> 4:1**
- Gross margin: **>80%** (software + data licensing)

---

## 9. Feature prioritization

### RICE-scored backlog (Reach × Impact × Confidence ÷ Effort)

| Feature | Reach | Impact | Conf. | Effort | RICE | Phase |
|---|---|---|---|---|---|---|
| DhanRadar Score (stock + fund) | 5 | 5 | 5 | 4 | **31** | Now |
| AI "explain this" layer | 5 | 5 | 4 | 3 | **33** | Now |
| Search + instrument pages | 5 | 4 | 5 | 3 | **33** | Now |
| Portfolio Score + sync | 4 | 5 | 4 | 4 | **20** | Now |
| Smart alerts (score/price/risk) | 4 | 4 | 4 | 2 | **32** | Now |
| Fair Value estimate | 3 | 5 | 4 | 4 | **15** | Next |
| Screeners + presets | 4 | 4 | 4 | 3 | **21** | Next |
| Compare (2–3) | 3 | 3 | 5 | 2 | **22** | Next |
| Learn hub (live-data linked) | 4 | 3 | 4 | 3 | **16** | Next |
| Mutual fund deep dive | 4 | 4 | 4 | 3 | **21** | Next |
| SIP / goal planner | 3 | 3 | 4 | 3 | **12** | Later |
| Score API (B2B) | 2 | 5 | 3 | 4 | **8** | Later |
| Tax optimization | 2 | 4 | 3 | 4 | **6** | Later |
| Community / social | 3 | 2 | 2 | 4 | **3** | Parked |

### Prioritization matrix (Impact × Effort)

```
   HIGH IMPACT
        ▲
        │  AI Explain        │  Portfolio Score
        │  DhanRadar Score   │  Fair Value
   QUICK│  Smart Alerts      │  Fund deep dive
   WINS │  Compare           │  MF screeners
   ─────┼────────────────────┼──────────────── EFFORT ▶
        │  Learn hub         │  SIP planner
   FILL │                    │  Score API
   -INS │                    │  Tax optimization
        │                    │  Community
        ▼
   LOW IMPACT
```

**Do first:** top-left (high impact, low effort) — AI Explain, Score, Alerts, Compare.
**Schedule:** top-right — Portfolio Score, Fair Value, Fund deep dive.
**Backlog / validate:** bottom-right — only after core loop proven.

---

## 10. User journey map (primary persona: Rohan, aspiring picker)

| Stage | User action | Thinking | Feeling | Touchpoint | Opportunity |
|---|---|---|---|---|---|
| **Trigger** | Hears "Reliance is a buy" from a friend | "Is it actually?" | Curious, skeptical | — | SEO: "Reliance share analysis" lands on us |
| **Discover** | Googles, lands on stock page | "Whoa, one score" | Intrigued | Public stock page | Show Score + 1-line reason ungated |
| **Aha** | Taps "why 86?" | "It explains it!" | Relief, trust | AI explain | The conversion moment — make it instant |
| **Activate** | Signs up (no card) for trial | "Let me check my other stocks" | Engaged | Onboarding | Pre-fill watchlist from a paste of holdings |
| **Habit** | Adds watchlist, gets first alert | "It told me before I noticed" | Reliant | Alerts | Alert → re-score → re-decide loop |
| **Convert** | Hits free limit / wants Fair Value | "Worth ₹399" | Justified | Paywall | Paywall at moment of demonstrated value, not arbitrary |
| **Expand** | Syncs full portfolio | "Now it sees everything" | Confident | Portfolio | Upsell Premium via portfolio risk insight |
| **Advocate** | Shares a score with friends | "You should check this" | Proud | Share card | Shareable Score cards = viral loop |

**Friction to kill:** gated first value (never), card-required trial (never), notification spam (calibrate hard), jargon without explanation (never).

---

## 11. Product roadmap

### Phase 1 — "Trust the Score" (Q3 2026, ~0–4 mo)
*Goal: nail the core decision loop for one persona (Rohan).*
- Stock + Fund DhanRadar Score (live, sector-normalized)
- Public, SEO-optimized instrument pages (ungated score + 1-line reason)
- AI "explain this" layer (score + every metric)
- Search + autosuggest
- Smart alerts (score/price/risk)
- Free/Pro tiers live, no-card trial
- **Success metric:** Free→Pro 4%+, D30 retention 25%+, "score is trustworthy" survey >70%

### Phase 2 — "See everything" (Q4 2026, ~4–8 mo)
*Goal: own monitoring + broaden personas (Meera, Vikram, Anjali).*
- Portfolio sync + Portfolio Score + monthly health report
- Fair Value estimate (DCF + relative + EPV)
- Screeners + presets, Compare
- Mutual fund deep dive (rolling returns, risk-adjusted)
- Premium tier live
- Learn hub linked to live data
- **Success metric:** ARPU ₹400+, Premium mix 15%+, portfolio-synced users 40%+

### Phase 3 — "Scale the intelligence" (2027, 8–18 mo)
*Goal: distribution + new revenue, defend the moat.*
- Score API / B2B2C licensing
- SIP & goal planning
- Tax optimization (Premium)
- Advanced AI (portfolio-level recommendations, scenario analysis)
- Regional language expansion (Hindi-first, then Tamil/Telugu/Marathi)
- **Success metric:** B2B pipeline, LTV:CAC >4:1, 1M+ MAU

### Guardrails across all phases
- Data quality SLA before breadth (Vikram churns on a wrong number).
- Methodology transparency published and versioned.
- No monetization stream touches a Score — ever.

---

## 12. Open questions for next prompts
1. Score methodology weighting — fixed vs persona-adaptive?
2. AI layer — build on our data only (RAG) vs allow open-ended market Q&A?
3. Portfolio sync — account aggregator (RBI AA framework) vs broker APIs vs manual?
4. Regulatory posture — how far can "signals" go before it's advice under SEBI RA rules? (legal review)
5. Acquisition — SEO/content-led (slow, cheap, defensible) vs paid (fast, dilutive)?

---

*Next: persona deep-dives, score methodology spec, or information architecture — say the word. No screens until you call for them.*
