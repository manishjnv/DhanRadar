# DhanRadar — Information Architecture

*Built on the approved Product Strategy (v1). Defines the complete structure of the product before any UI design.*

**Prepared by:** UX Architecture · Product Architecture · Information Architecture
**Date:** June 2026 · **Status:** v1 for review

---

## 0. How to read this document

- **§1 Sitemap** — the full tree across all five categories.
- **§2 Navigation hierarchy** — what appears where (public nav, app shell, mobile, contextual).
- **§3 User flows** — the critical paths through the product.
- **§4 Screen inventory** — every screen, with Purpose / Primary CTA / Data requirements / User actions.

**Category legend**
🟢 Public · 🔵 Authenticated · 🟣 Premium · 🔴 Admin · 🟠 AI Operations

**Naming convention:** `CATEGORY / Section / Screen` — IDs like `PUB-01`, `AUTH-12`, `PREM-03`, `ADM-04`, `AIO-02`.

---

## 1. Sitemap

```
DhanRadar
│
├── 🟢 PUBLIC (unauthenticated, SEO-indexed where noted)
│   ├── Home / Landing
│   ├── Stocks
│   │   ├── Stock Detail (public preview)        [SEO]
│   │   └── Stocks Directory / A–Z               [SEO]
│   ├── Mutual Funds
│   │   ├── Fund Detail (public preview)         [SEO]
│   │   └── Funds Directory                       [SEO]
│   ├── Screeners (preview/teaser)
│   ├── Compare (preview, 2 items)
│   ├── Learn
│   │   ├── Learn Hub
│   │   ├── Topic Page
│   │   ├── Lesson (public sample)               [SEO]
│   │   └── Glossary / Term Page                 [SEO]
│   ├── Pricing
│   ├── Blog
│   │   ├── Blog Listing                          [SEO]
│   │   └── Blog Article                          [SEO]
│   ├── Company
│   │   ├── About
│   │   ├── Methodology (how the Score works)    [SEO, trust-critical]
│   │   ├── Careers
│   │   ├── Contact
│   │   └── Press
│   └── Legal
│       ├── Terms · Privacy · Disclosures · SEBI notice · Refund
│
├── 🔵 AUTHENTICATED (free + paid)
│   ├── Auth
│   │   ├── Sign Up · Login · OTP · Forgot · Reset · Onboarding
│   ├── Dashboard (market + personalized)
│   ├── Stock Detail (full)
│   ├── Fund Detail (full)
│   ├── Screeners (full)
│   │   ├── Stock Screener · Fund Screener · Saved Screens
│   ├── Compare (full, up to 3)
│   ├── Watchlists
│   │   ├── Watchlist List · Watchlist Detail
│   ├── Portfolio
│   │   ├── Portfolio Overview · Holdings · Add/Sync · Transactions
│   ├── Alerts Center
│   ├── AI Assistant (chat / explain)
│   ├── Learn (progress-tracked)
│   ├── Account
│   │   ├── Profile · Settings · Notifications · Connected Brokers · Security
│   └── Subscription (Free state, manage)
│
├── 🟣 PREMIUM (Pro / Premium gated)
│   ├── Fair Value Detail (multi-model)
│   ├── Portfolio Analytics (risk, attribution)
│   ├── Portfolio Health Report
│   ├── Advanced Screener (custom formulas)        [Premium]
│   ├── Tax Optimization                            [Premium]
│   ├── Curated Portfolios / Model Portfolios       [Premium]
│   ├── SIP & Goal Planner
│   ├── AI Deep Dive (scenario analysis)            [Premium]
│   └── Export Center (CSV / PDF / API keys)        [Premium]
│
├── 🔴 ADMIN (internal, role-gated)
│   ├── Admin Dashboard
│   ├── User Management
│   ├── Subscription & Billing Ops
│   ├── Content CMS (blog, learn, glossary)
│   ├── Score Model Management
│   ├── Data Source Monitor
│   ├── Alert & Notification Console
│   ├── Support / Tickets
│   ├── Feature Flags / Config
│   └── Analytics & Reporting
│
└── 🟠 AI OPERATIONS (internal, ML/ops-gated)
    ├── AI Ops Dashboard
    ├── Score Model Versioning & Backtest
    ├── Prompt & RAG Management
    ├── AI Quality / Eval Console
    ├── Hallucination & Safety Monitor
    ├── Explanation Feedback Review
    └── Cost & Usage Monitor
```

---

## 2. Navigation hierarchy

### 2.1 Public top nav (marketing)
**Primary:** Stocks · Mutual Funds · Screeners · Compare · Learn · Pricing
**Right:** Search · Log in · **Get started (free)** [primary CTA]
**Footer:** Product / Learn / Company (incl. **Methodology**) / Legal / Social

### 2.2 Authenticated app shell (desktop — left sidebar)
**Workspace (primary):**
- Dashboard
- Stocks (→ search/detail)
- Mutual Funds
- Screeners
- Portfolio

**Discover (secondary):**
- Compare
- Watchlists `(badge: count)`
- Alerts `(badge: unread)`
- AI Assistant
- Learn

**Footer of sidebar:**
- Upgrade card (Free/Pro state-aware)
- Settings
- Theme toggle · Profile menu

**Top bar:** global search (⌘K) · market indices ticker · notifications · theme · avatar/menu

### 2.3 Mobile (bottom tab bar — 5 max)
`Markets (Dashboard) · Discover (Screener/Search) · AI (Assistant) · Portfolio · Profile`
Everything else reached via in-screen nav, search, or profile menu.

### 2.4 Contextual / utility nav
- **Instrument page tabs:** Overview · Financials · Peers · SWOT · Valuation `(🟣)`
- **Portfolio tabs:** Overview · Holdings · Analytics `(🟣)` · Transactions
- **Account tabs:** Profile · Settings · Notifications · Brokers · Security · Subscription
- **Breadcrumbs:** on all detail and admin screens
- **Paywall interstitials:** triggered contextually (at value moment), never as a hard wall on first view

### 2.5 Admin / AI Ops nav (separate shell, role-gated)
Left sidebar, distinct visual treatment (red/orange accent), no public chrome. Section switcher between **Admin** and **AI Ops** for users with both roles.

---

## 3. User flows

### Flow A — Public → Activation (acquisition, primary)
```
SEO landing (Stock Detail preview)
  → sees Score + 1-line reason (ungated)
  → taps "Why 86?" → AI explain teaser (1 free)
  → hits "see full analysis" → Sign Up (no card)
  → OTP verify
  → Onboarding (goals, paste/sync holdings, pick interests)
  → Dashboard (pre-populated watchlist)
  ✦ Activation = added 1 watchlist item OR ran 1 AI explain
```

### Flow B — Free → Paid (conversion)
```
Authenticated user researching
  → hits gated feature (Fair Value / unlimited AI / screener save)
  → contextual paywall (shows the value they're reaching for)
  → Pricing / Plan select
  → Razorpay checkout (UPI/card/netbanking)
  → confirmation → feature unlocked inline
  ✦ Conversion at demonstrated-value moment, not arbitrary limit
```

### Flow C — Research a stock (core JTBD #1–2)
```
Search (⌘K) or Dashboard tile
  → Stock Detail
  → read Score + factor breakdown
  → tap "explain" on any metric → AI inline answer
  → check Fair Value (🟣 gate if Free)
  → Compare with peer (add 2nd, 3rd)
  → Decide → Add to Watchlist / Set Alert / (broker handoff)
```

### Flow D — Monitor portfolio (core JTBD #3)
```
Connect broker (AA framework) OR manual add
  → Portfolio Overview (value + Portfolio Score)
  → review Holdings (per-holding scores)
  → Analytics (🟣: risk, sector exposure, attribution)
  → receive monthly Health Report (🟣)
  → Alert fires on material change → re-evaluate holding
```

### Flow E — Set up an alert
```
Stock/Fund/Portfolio context
  → "Set alert" → choose type (price / score / risk / earnings)
  → set threshold → confirm
  → Alerts Center (manage)
  → trigger → push/email → deep link back to instrument
```

### Flow F — Learn while doing
```
Hit unknown term anywhere → "explain" tooltip → Glossary term
  → related Lesson → Topic → Learn Hub
  → progress tracked → streak → resume card on Dashboard
```

### Flow G — Admin: publish content
```
Admin login → Content CMS → new article/lesson
  → draft → preview → SEO meta → schedule/publish → live on Public
```

### Flow H — AI Ops: ship a score model version
```
AI Ops → Score Model Versioning
  → new version → backtest vs benchmark → eval gates
  → canary % rollout → monitor (drift, complaints) → full rollout / rollback
```

---

## 4. Screen inventory

> Format per screen: **Purpose · Primary CTA · Data requirements · User actions**

### 🟢 PUBLIC

**PUB-01 · Home / Landing**
- **Purpose:** Convert visitors; communicate value prop; live search entry.
- **Primary CTA:** Get started — free
- **Data:** Live indices, sample Score showcase, social proof stats, testimonials, pricing teaser.
- **Actions:** Search instrument, start trial, sign in, navigate sections, expand FAQ.

**PUB-02 · Stock Detail (public preview)** [SEO]
- **Purpose:** Rank for "<stock> analysis"; show ungated Score + teaser to drive signup.
- **Primary CTA:** See full analysis (→ signup)
- **Data:** Score, 1-line reason, price, basic stats; gated: factors, Fair Value, financials.
- **Actions:** View score, 1 free AI explain, attempt gated action → signup, share.

**PUB-03 · Stocks Directory (A–Z)** [SEO]
- **Purpose:** SEO surface + browse entry to all stocks.
- **Primary CTA:** Open stock
- **Data:** Paginated stock list (name, ticker, sector, score, price).
- **Actions:** Filter by sector/letter, search, open detail.

**PUB-04 · Fund Detail (public preview)** [SEO]
- **Purpose:** Rank for "<fund> review"; ungated fund Score teaser.
- **Primary CTA:** See full analysis (→ signup)
- **Data:** Fund Score, NAV, category, basic returns; gated: rolling returns, risk metrics, holdings.
- **Actions:** View score, share, signup for depth.

**PUB-05 · Funds Directory** [SEO] — *as PUB-03 for funds.*

**PUB-06 · Screeners (teaser)**
- **Purpose:** Show screener power; convert.
- **Primary CTA:** Unlock full screener (→ signup)
- **Data:** Preset list, limited result preview.
- **Actions:** Try 1 preset, view limited rows, signup.

**PUB-07 · Compare (preview, 2 items)**
- **Purpose:** Demonstrate side-by-side value.
- **Primary CTA:** Compare 3 + unlock (→ signup)
- **Data:** 2 instruments, headline metrics + scores.
- **Actions:** Swap instruments, signup for full.

**PUB-08 · Learn Hub**
- **Purpose:** Education entry; SEO; brand trust.
- **Primary CTA:** Start learning
- **Data:** Topics, lesson counts, featured lesson.
- **Actions:** Browse topics, open lesson, signup to track progress.

**PUB-09 · Topic Page** — topic intro + lesson list. **CTA:** Start topic.
**PUB-10 · Lesson (public sample)** [SEO] — single lesson content. **CTA:** Next lesson (→ signup to continue).
**PUB-11 · Glossary / Term** [SEO] — definition + linked lessons + live example. **CTA:** See on a real stock.

**PUB-12 · Pricing**
- **Purpose:** Communicate tiers; drive trial.
- **Primary CTA:** Start 14-day Pro trial
- **Data:** Plan matrix, feature comparison, FAQ.
- **Actions:** Toggle monthly/yearly, compare, start trial, contact sales.

**PUB-13 · Blog Listing** [SEO] · **PUB-14 · Blog Article** [SEO]
- **Purpose:** Content marketing, SEO, authority.
- **Primary CTA:** Subscribe / Start free
- **Data:** Articles (category, author, read time, body, related).
- **Actions:** Filter, read, share, subscribe newsletter.

**PUB-15 · Methodology** [SEO, trust-critical]
- **Purpose:** Publish how the Score works — the trust anchor.
- **Primary CTA:** See it on a stock
- **Data:** Factor definitions, weights, normalization, update cadence, versioning.
- **Actions:** Read, expand factor details, navigate to example.

**PUB-16 · About · PUB-17 · Careers · PUB-18 · Contact · PUB-19 · Press**
- Standard company pages. **CTAs:** Contact / Apply / Get started.

**PUB-20 · Legal (Terms/Privacy/Disclosures/SEBI/Refund)**
- **Purpose:** Compliance. **CTA:** n/a. **Data:** Legal copy, version dates. **Actions:** Read, download.

---

### 🔵 AUTHENTICATED

**AUTH-01 · Sign Up**
- **Purpose:** Create account, low friction.
- **Primary CTA:** Create account
- **Data:** Name, email, phone, password; marketing opt-in (off by default).
- **Actions:** Fill form, social auth, accept terms, → OTP.

**AUTH-02 · Login** — **CTA:** Sign in. Email/pass + social + forgot link.
**AUTH-03 · OTP Verification** — **CTA:** Verify. 6-digit, resend timer.
**AUTH-04 · Forgot Password** — **CTA:** Send reset link.
**AUTH-05 · Reset Password** — **CTA:** Set new password.

**AUTH-06 · Onboarding**
- **Purpose:** Personalize; reach activation fast.
- **Primary CTA:** Go to dashboard
- **Data:** Goals, experience level, interests/sectors, optional holdings paste/sync.
- **Actions:** Select goals, paste/sync holdings, pick interests, skip.

**AUTH-07 · Dashboard**
- **Purpose:** Daily home; market + personalized signal.
- **Primary CTA:** (contextual — open top-scored / resume lesson)
- **Data:** Indices, watchlist movers, top-scored, news, sector heatmap, portfolio snapshot, learning streak.
- **Actions:** Search, open instrument, customize widgets, navigate.

**AUTH-08 · Stock Detail (full)**
- **Purpose:** Complete research surface.
- **Primary CTA:** Add to Watchlist
- **Data:** Score + factors, price/chart, financials, peers, SWOT, signals; Fair Value 🟣.
- **Actions:** Switch tabs, AI explain (limited on Free), set alert, compare, watchlist, broker handoff.

**AUTH-09 · Fund Detail (full)**
- **Purpose:** Complete fund research.
- **Primary CTA:** Add to Watchlist / Start SIP
- **Data:** Score, NAV chart, rolling returns, expense, risk metrics, holdings, manager.
- **Actions:** Period switch, AI explain, alert, compare, SIP setup (🟣 planner).

**AUTH-10 · Stock Screener**
- **Purpose:** Generate idea shortlists.
- **Primary CTA:** Save screen (🟣 gate beyond N)
- **Data:** Filter definitions, live result set, presets.
- **Actions:** Adjust filters, sort, save, export (🟣), open result.

**AUTH-11 · Fund Screener** — as AUTH-10 for funds.

**AUTH-12 · Saved Screens** — list of saved screens. **CTA:** Run screen. Actions: rename, delete, share, run.

**AUTH-13 · Compare (full)**
- **Purpose:** Side-by-side decision.
- **Primary CTA:** Add to Watchlist (winner)
- **Data:** Up to 3 instruments × 80+ data points + scores + radar.
- **Actions:** Add/remove instruments, scroll metrics, export (🟣).

**AUTH-14 · Watchlist List** — all watchlists. **CTA:** New watchlist. Actions: create, rename, reorder, delete, open.
**AUTH-15 · Watchlist Detail**
- **Purpose:** Track a set; spot moves.
- **Primary CTA:** Add instrument
- **Data:** Per-item price, change, score, sparkline, alert state.
- **Actions:** Add/remove, sort, set alert, open detail.

**AUTH-16 · Portfolio Overview**
- **Purpose:** "Is everything OK?" at a glance.
- **Primary CTA:** Add holding / Sync broker
- **Data:** Total value, P&L, XIRR, Portfolio Score, allocation donut, vs-benchmark.
- **Actions:** Switch period, drill to holdings, sync, download report (🟣).

**AUTH-17 · Holdings** — sortable holdings table. **CTA:** Add holding. Actions: sort, open detail, edit, remove.
**AUTH-18 · Add / Sync Holdings**
- **Purpose:** Get data in with minimal friction.
- **Primary CTA:** Connect broker
- **Data:** AA framework / broker list, manual entry form.
- **Actions:** Connect (consent flow), manual add, import CSV.

**AUTH-19 · Transactions** — history list. **CTA:** Add transaction. Actions: filter, sort, edit.

**AUTH-20 · Alerts Center**
- **Purpose:** Manage all alerts; review triggered.
- **Primary CTA:** New alert
- **Data:** Triggered (today/recent), active rules, alert types.
- **Actions:** Create, edit threshold, mute, delete, filter by type.

**AUTH-21 · AI Assistant**
- **Purpose:** Natural-language research + explanation.
- **Primary CTA:** Ask (send)
- **Data:** Chat history, RAG over user's data + market data, suggested prompts, query quota (Free).
- **Actions:** Ask, follow-up, deep-link to instrument, save answer, upgrade on quota.

**AUTH-22 · Learn (tracked)** — Hub/Topic/Lesson with progress, streaks, resume. **CTA:** Resume lesson.

**AUTH-23 · Profile** — **CTA:** Save changes. Data: name, email, phone, avatar, plan badge, achievements.
**AUTH-24 · Settings** — appearance, language, defaults. **CTA:** Save.
**AUTH-25 · Notifications Settings** — per-channel toggles. **CTA:** Save preferences.
**AUTH-26 · Connected Brokers** — list + consent status. **CTA:** Connect broker. Actions: add, revoke, re-sync.
**AUTH-27 · Security** — password, 2FA, sessions, trusted devices. **CTA:** Enable 2FA.
**AUTH-28 · Subscription (manage)** — current plan, usage, billing history. **CTA:** Upgrade. Actions: upgrade, downgrade, cancel, update payment.

---

### 🟣 PREMIUM (Pro / Premium gated)

**PREM-01 · Fair Value Detail**
- **Purpose:** Multi-model intrinsic value with reasoning.
- **Primary CTA:** Set price alert at target
- **Data:** DCF, relative, EPV models + weights, assumptions, sensitivity, upside/downside.
- **Actions:** Adjust assumptions (Premium), view scenarios, set alert, export.
- **Gate:** Pro+ (scenarios Premium-only).

**PREM-02 · Portfolio Analytics**
- **Purpose:** Risk, exposure, attribution.
- **Primary CTA:** Download report
- **Data:** Risk metrics (beta, Sharpe, drawdown), sector/cap exposure, concentration, return attribution.
- **Actions:** Drill by dimension, period switch, export.
- **Gate:** Pro+.

**PREM-03 · Portfolio Health Report**
- **Purpose:** Monthly synthesized "how's my portfolio."
- **Primary CTA:** View full report / Download PDF
- **Data:** Portfolio score trend, flags, top movers, suggested watch-items.
- **Actions:** Read, download, share, drill to holding.
- **Gate:** Pro+.

**PREM-04 · Advanced Screener**
- **Purpose:** Custom formula/ratio screening.
- **Primary CTA:** Save / Run custom screen
- **Data:** Formula builder, full universe, derived metrics.
- **Actions:** Build formula, save, share, export.
- **Gate:** Premium.

**PREM-05 · Tax Optimization**
- **Purpose:** Capital-gains harvesting, tax-aware suggestions.
- **Primary CTA:** View suggestions
- **Data:** Realized/unrealized gains, LTCG/STCG split, harvesting opportunities.
- **Actions:** Review, simulate, export for filing.
- **Gate:** Premium.

**PREM-06 · Curated / Model Portfolios**
- **Purpose:** Analyst-curated baskets.
- **Primary CTA:** Track this portfolio
- **Data:** Model holdings, rationale, performance, rebalance history.
- **Actions:** Track, compare to own, get rebalance alerts.
- **Gate:** Premium.

**PREM-07 · SIP & Goal Planner**
- **Purpose:** Systematic planning.
- **Primary CTA:** Start SIP / Create goal
- **Data:** Goal inputs, projected corpus, fund suggestions, SIP schedule.
- **Actions:** Set goal, simulate, schedule SIP, track.
- **Gate:** Pro+ (advanced scenarios Premium).

**PREM-08 · AI Deep Dive**
- **Purpose:** Portfolio-level + scenario AI analysis.
- **Primary CTA:** Run analysis
- **Data:** Full portfolio context, scenario inputs, model outputs.
- **Actions:** Ask portfolio-level Qs, run what-ifs, save report.
- **Gate:** Premium.

**PREM-09 · Export Center**
- **Purpose:** Data portability + API.
- **Primary CTA:** Generate export / API key
- **Data:** Export jobs, API keys, usage, rate limits.
- **Actions:** Export CSV/PDF, manage API keys, view usage.
- **Gate:** Premium.

---

### 🔴 ADMIN (role-gated internal)

**ADM-01 · Admin Dashboard** — Purpose: ops at-a-glance. CTA: (contextual). Data: signups, MRR, active users, system health, alerts. Actions: drill into any metric.

**ADM-02 · User Management** — Purpose: manage accounts. CTA: Edit user. Data: user list, plan, status, activity, flags. Actions: search, view, suspend, refund, impersonate (audited), reset.

**ADM-03 · Subscription & Billing Ops** — CTA: Process refund. Data: subscriptions, invoices, failed payments, dunning. Actions: refund, comp, retry, adjust plan.

**ADM-04 · Content CMS** — CTA: Publish. Data: blog/learn/glossary entries, SEO meta, schedule. Actions: create, edit, preview, schedule, publish, unpublish.

**ADM-05 · Score Model Management** — CTA: Request version change. Data: active model version, factor weights, coverage, overrides. Actions: view config, request change (→ AI Ops), view audit log.

**ADM-06 · Data Source Monitor** — CTA: Acknowledge incident. Data: feed health, freshness, gaps, error rates per source. Actions: ack, trigger re-fetch, flag instrument.

**ADM-07 · Alert & Notification Console** — CTA: Send broadcast. Data: notification templates, delivery rates, scheduled sends. Actions: edit templates, schedule, broadcast, throttle.

**ADM-08 · Support / Tickets** — CTA: Reply. Data: tickets, user context, SLA timers. Actions: reply, escalate, close, link to user.

**ADM-09 · Feature Flags / Config** — CTA: Toggle flag. Data: flags, rollout %, targeting rules. Actions: toggle, set %, target cohort.

**ADM-10 · Analytics & Reporting** — CTA: Build report. Data: funnels, retention, conversion, cohort, revenue. Actions: filter, segment, export, schedule.

---

### 🟠 AI OPERATIONS (ML/ops-gated internal)

**AIO-01 · AI Ops Dashboard** — Purpose: AI system health. CTA: (contextual). Data: model versions live, query volume, latency, eval scores, cost. Actions: drill into subsystem.

**AIO-02 · Score Model Versioning & Backtest** — CTA: Promote / Rollback. Data: versions, backtest vs benchmark, factor stability, drift. Actions: create version, run backtest, canary %, promote, rollback.

**AIO-03 · Prompt & RAG Management** — CTA: Deploy prompt. Data: prompt templates, RAG sources, retrieval config, versions. Actions: edit, A/B test, version, deploy.

**AIO-04 · AI Quality / Eval Console** — CTA: Run eval. Data: eval suites, accuracy/groundedness scores, regression diffs. Actions: run suite, compare versions, gate release.

**AIO-05 · Hallucination & Safety Monitor** — CTA: Flag / Block. Data: flagged outputs, groundedness alerts, unsafe-content detections, advice-boundary breaches. Actions: review, block pattern, retrain queue, escalate.

**AIO-06 · Explanation Feedback Review** — CTA: Action feedback. Data: user thumbs up/down on AI explains, low-rated answers, themes. Actions: triage, route to prompt/data fix, label for training.

**AIO-07 · Cost & Usage Monitor** — CTA: Set budget alert. Data: token/inference cost by feature, per-user heavy usage, trends. Actions: set caps, alert, optimize routing.

---

## 5. Cross-cutting IA rules

1. **Public previews are real, not fake** — the ungated Score on PUB-02/04 is the actual number. Trust depends on it.
2. **Gates are contextual, not structural** — a Free user *navigates into* PREM screens and hits an inline paywall at the value moment; Premium screens are not hidden from the map.
3. **Methodology is always one click from any Score** — every Score surface links to PUB-15.
4. **AI explain is ambient** — reachable from any metric on any instrument screen, not just the Assistant.
5. **Admin & AI Ops are a separate shell** — different chrome, role-gated, audited; never reachable from the user app nav.
6. **Search (⌘K) is global** in the authenticated shell — instruments, screens, learn, settings.
7. **Mobile parity** — every authenticated screen has a mobile layout; admin/AI-ops are desktop-first.

---

## 6. Screen count summary

| Category | Screens |
|---|---|
| 🟢 Public | 20 |
| 🔵 Authenticated | 28 |
| 🟣 Premium | 9 |
| 🔴 Admin | 10 |
| 🟠 AI Operations | 7 |
| **Total** | **74** |

---

*Next: pick a category or flow to take into UI design, or request wireframes for the core authenticated loop (Dashboard → Stock Detail → AI explain → Watchlist/Alert). No UI until you call for it.*
