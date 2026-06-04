# DhanRadar — Figma Structure & Engineering Handoff

*The capstone: a complete Figma file blueprint, per-screen engineering handoff, and final design review across the whole program. Synthesizes docs 01–06, the design system, hi-fi screens, mobile patterns, and the AI layer.*

**Prepared by:** Design Systems Lead · Staff Eng · **Date:** June 2026 · **Status:** v1 — production-ready package

---

# PART 1 — COMPLETE FIGMA STRUCTURE

## 1.1 File & page organization

A single **DhanRadar — Product** Figma file (plus a separate **DhanRadar — Brand** file for marketing assets). Pages, in order:

```
📄 00 · Cover & Changelog       — file purpose, version, owners, what changed
📄 01 · Foundations             — color, type, grid, spacing, motion, a11y, iconography
📄 02 · Design Tokens           — token tables + Figma Variables (Light/Dark modes)
📄 03 · Components — Core        — buttons, inputs, cards, tables, badges, chips, tabs
📄 04 · Components — Data Viz    — ScoreRing, AreaChart, Sparkline, Donut, FactorBars, gauges
📄 05 · Components — Patterns    — alerts, toasts, notifications, watchlist row, rec card, empty/loading/error
📄 06 · Components — AI Layer    — search, assistant, explainability, confidence, bull/bear, sources, transparency
📄 07 · Desktop — Marketing      — home, pricing, blog, methodology
📄 08 · Desktop — App            — dashboard, recommendations, stock/fund/etf, portfolio, watchlist, screener, news, settings, subscription, profile
📄 09 · Desktop — Admin / AI Ops — admin dashboard, AI operations dashboard
📄 10 · Mobile — iOS             — 8 screens, native patterns
📄 11 · Mobile — Android         — 8 screens, Material 3
📄 12 · Mobile — PWA             — 8 screens, install/offline patterns
📄 13 · Prototypes               — wired flows (interactive)
📄 14 · Engineering Handoff      — annotations, redlines, specs (this doc, mirrored)
📄 15 · Archive                  — deprecated explorations
```

## 1.2 Foundations page (01)
- **Color** — brand (Navy #0B1F3A, Electric Blue #2563EB, Emerald #10B981), semantic (success/warn/error/info), full neutral scales × Light/Dark. Each as a Figma Variable bound to styles.
- **Typography** — Manrope (display), Inter (body), JetBrains Mono (numeric). Type scale as text styles (Display/H1–H4/Body/Small/Caption/Numeric/Eyebrow).
- **Grid & layout** — 12/8/4-col responsive grids as layout-grid styles; 1200px max container.
- **Spacing** — 4px base; tokens 1–16 as number variables.
- **Motion** — durations (fast/base/slow/stage) + easings documented; Smart Animate presets.
- **Iconography** — line-icon set (1.6px stroke); component set with size variants.
- **Accessibility** — contrast pairs, focus-ring spec, target sizes, do/don't.

## 1.3 Components pages (03–06) — build rules
- **Variants + properties** — every component uses Figma variant properties (`size`, `variant`, `state`, `theme`) so a button is one component, not twelve.
- **Boolean + instance-swap props** — icon on/off, leading/trailing slots.
- **Auto-layout everywhere** — components reflow; nothing hand-positioned.
- **States as variants** — `default / hover / focus / active / disabled / loading / error / success`.
- **Token-bound** — fills/strokes/text bound to Variables so theme + retheme is automatic.
- **The four data-states** (loading skeleton / empty / error / success) are first-class component variants for every data surface.

## 1.4 Prototypes page (13) — wired flows
| Flow | Screens | Purpose |
|---|---|---|
| Activation | SEO stock page → signup → OTP → onboarding → dashboard | conversion proof |
| Research → act | search → stock detail → AI explain → set alert / watchlist | core loop |
| Free → Pro | gated feature → paywall → checkout → unlock | monetization |
| Portfolio | connect broker → overview → analytics (gated) | retention |
| AI assistant | ask → grounded answer → drill to instrument | AI trust |
| Mobile parity | iOS/Android/PWA tab flows | platform validation |

Interactions: Smart Animate transitions, real overlay sheets/modals, variant-driven state changes, scroll + fixed headers.

## 1.5 Design Tokens (page 02) → code
Figma Variables (Light/Dark collections) are the design source; exported via Style Dictionary to `tokens.json`, `css-variables.css`, `tailwind.config.ts` (delivered in `/design-system`). One pipeline, three consumers — Figma, CSS, Tailwind never drift.

---

# PART 2 — PER-SCREEN ENGINEERING HANDOFF

> For each screen: **Components · API dependencies · State · Events · Analytics · DB entities · Complexity · Estimate** (est. = frontend dev-days for one engineer; backend tracked separately where noted).

### S1 · Dashboard
- **Components:** AppShell, IndexKPI(×4), TopScoredTable, NewsList, SectorHeatmap, PortfolioSnapshot, Skeleton/Empty/Error.
- **API:** `GET /indices`, `GET /instruments/top-scored`, `GET /news?scope=market`, `GET /portfolio/summary`, `GET /sectors/heatmap`.
- **State:** React Query (per widget, independent stale times); SSE for index/price deltas.
- **Events:** `dashboard_view`, `top_scored_click`, `widget_customize`.
- **Analytics:** activation funnel entry, DAU, widget engagement.
- **DB:** instruments, scores, instrument_prices, news, holdings.
- **Complexity:** Medium · **Est:** 4d.

### S2 · Recommendation Hub
- **Components:** FilterChips, RecommendationCard (header+reason+confidence+actions), Pagination, Empty/Loading.
- **API:** `GET /recommendations?signal=&sector=`, `POST /watchlists/{id}/items`, `GET /ai/explain/{sym}`.
- **State:** Query for list; optimistic watchlist add; filter state in URL.
- **Events:** `rec_view`, `rec_filter`, `rec_add_watchlist`, `rec_why_click`.
- **Analytics:** signal CTR, add-rate, filter usage.
- **DB:** scores, instruments, watchlist_items, ai_messages.
- **Complexity:** Medium · **Est:** 4d.

### S3 · Stock Detail
- **Components:** StockHeader, PriceChart+PeriodSwitch, ScorePanel(ring+FactorBars), Tabs(Overview/Financials/Peers/SWOT/Valuation), ProsCons, FairValueGauge(gated), AI-explain affordances.
- **API:** `GET /stocks/{sym}`, `/score`, `/score/history`, `/financials`, `/peers`, `/fair-value`(pro), `GET /ai/explain/{sym}`, `POST /alerts`.
- **State:** Query (instrument long-stale, price SSE); tab in URL; gated fields by plan.
- **Events:** `stock_view`, `period_change`, `tab_change`, `factor_explain`, `alert_create`, `fairvalue_gate_hit`.
- **Analytics:** research depth, paywall hit-rate, alert conversion.
- **DB:** instruments, scores, instrument_prices, corporate_actions, alert_rules.
- **Complexity:** High · **Est:** 7d.

### S4 · Mutual Fund Detail
- **Components:** FundHeader, NAVChart, ScorePanel, RollingReturnsTable, FundDetails, SIP CTA.
- **API:** `GET /funds/{sym}`, `/nav-history`, `/rolling-returns`, `/score`, `POST /sip` (premium planner).
- **State:** Query; period switch; SIP modal form (RHF+Zod).
- **Events:** `fund_view`, `rolling_return_period`, `sip_start`.
- **Analytics:** fund research, SIP conversion.
- **DB:** instruments(type=fund), instrument_prices(NAV), scores.
- **Complexity:** Medium-High · **Est:** 5d.

### S5 · ETF Detail
- **Components:** ETFHeader, Price/iNAV overlay chart, ScorePanel, ETF-KPIs(tracking error/expense/spread/AUM), IndexBreakdown, Holdings.
- **API:** `GET /etfs/{sym}`, `/inav`, `/holdings`, `/index-breakdown`, `/score`.
- **State:** Query; chart overlay toggle.
- **Events:** `etf_view`, `inav_toggle`, `holding_drill`.
- **Analytics:** ETF research depth.
- **DB:** instruments(type=etf), instrument_prices, scores, holdings(constituents).
- **Complexity:** Medium-High · **Est:** 5d.

### S6 · Portfolio Tracker
- **Components:** ValueCard+chart, KPI(XIRR/benchmark/score), AllocationDonut, Tabs(Holdings/Analytics/Transactions), HoldingsTable, Add/Sync flow, Report(async).
- **API:** `GET /portfolio`, `/holdings`, `/analytics`(pro), `/transactions`, `POST /holdings`, `/sync`, `GET /portfolio/report`(async→S3).
- **State:** Query; optimistic add; broker consent flow; report polling.
- **Events:** `portfolio_view`, `holding_add`, `broker_sync`, `analytics_gate_hit`, `report_download`.
- **Analytics:** sync rate, premium analytics conversion.
- **DB:** holdings, transactions, broker_links, instruments, scores.
- **Complexity:** High · **Est:** 8d (+ backend AA integration).

### S7 · Watchlist
- **Components:** ListSwitcher, WatchlistTable(row: logo/spark/price/score/alert-toggle), Add, swipe actions (mobile), Empty/Loading.
- **API:** `GET /watchlists`, `/{id}/items`, `POST/DELETE items`, `POST /alerts`.
- **State:** Query; optimistic add/remove + alert toggle.
- **Events:** `watchlist_view`, `watchlist_add/remove`, `alert_toggle`.
- **Analytics:** tracking habit, alert adoption.
- **DB:** watchlists, watchlist_items, alert_rules, instruments, scores.
- **Complexity:** Medium · **Est:** 4d.

### S8 · AI Search
- **Components:** SearchInput, AIAnswerCard(answer+confidence+sources), ResultList.
- **API:** `POST /ai/search` (quota-gated), `GET /instruments/search`.
- **State:** Query/mutation; quota state; debounced input.
- **Events:** `ai_search`, `ai_answer_view`, `ai_result_click`, `ai_quota_hit`.
- **Analytics:** AI adoption, cache-hit (server), quota→upgrade.
- **DB:** ai_conversations, ai_messages; vector store (retrieval).
- **Complexity:** High · **Est:** 6d (depends on AI gateway).

### S9 · AI Assistant
- **Components:** ChatTranscript, MessageBubble(+sources/confidence/feedback), Composer(SSE stream), SuggestedPrompts.
- **API:** `POST /ai/assistant` (SSE), `POST /ai/messages/{id}/feedback`.
- **State:** streaming state machine; conversation in Query; quota.
- **Events:** `assistant_open`, `assistant_ask`, `assistant_feedback`, `assistant_drill`.
- **Analytics:** turns/session, helpfulness rate, drill-through.
- **DB:** ai_conversations, ai_messages.
- **Complexity:** High · **Est:** 7d.

### S10 · News Center
- **Components:** TagFilter, NewsCard(+linked ticker), TrendingRail, EconCalendar.
- **API:** `GET /news?tag=&scope=`, `GET /news/trending`, `GET /calendar`.
- **State:** Query; tag filter in URL; "my holdings" scope.
- **Events:** `news_view`, `news_filter`, `news_ticker_click`.
- **Analytics:** news engagement, personalization usage.
- **DB:** news, instruments, holdings.
- **Complexity:** Medium · **Est:** 3d.

### S11 · Subscription
- **Components:** CurrentPlanBanner, BillingToggle, PlanCards(×3), ComparisonTable, Checkout, Success/Error states.
- **API:** `GET /billing/plans`, `/subscription`, `POST /billing/checkout`, webhook (backend).
- **State:** Query; checkout flow (Razorpay); idempotency.
- **Events:** `pricing_view`, `plan_select`, `checkout_start`, `checkout_success/fail`, `cancel`.
- **Analytics:** conversion funnel, MRR, churn.
- **DB:** plans, subscriptions, invoices, usage_counters.
- **Complexity:** High · **Est:** 6d (+ payment backend).

### S12 · User Profile
- **Components:** ProfileHeader, StatTiles, ConnectedBrokers, Achievements.
- **API:** `GET /users/me`, `/brokers`, `PATCH /users/me`.
- **State:** Query; edit form.
- **Events:** `profile_view`, `profile_edit`, `broker_manage`.
- **Analytics:** profile completion, broker connections.
- **DB:** users, broker_links, subscriptions.
- **Complexity:** Low-Medium · **Est:** 3d.

### S13 · Settings
- **Components:** SectionNav, grouped controls (toggles/selects/fields), Save, Security panel.
- **API:** `GET/PATCH /users/me/settings`, `/notifications`, `/security` (2FA).
- **State:** form (RHF+Zod); optimistic toggles.
- **Events:** `settings_view`, `setting_change`, `2fa_enable`.
- **Analytics:** notification opt-rates, 2FA adoption.
- **DB:** users, user preferences, sessions.
- **Complexity:** Medium · **Est:** 4d.

### S14 · Admin Dashboard
- **Components:** Admin shell, Ops KPIs, UserMgmtTable, DataSourceMonitor, ScoreModelPanel.
- **API:** `GET /admin/metrics`, `/admin/users`, `/admin/data-sources`, `/admin/score-model`.
- **State:** Query; role-gated; audited mutations.
- **Events:** `admin_action_*` (all audited).
- **Analytics:** ops efficiency, internal only.
- **DB:** users, subscriptions, ingest_runs, scores, audit_log.
- **Complexity:** Medium-High · **Est:** 6d.

### S15 · AI Operations Dashboard
- **Components:** AI-Ops shell, AI KPIs, ModelVersioning, SafetyMonitor, FeedbackReview, CostMonitor.
- **API:** `GET /aiops/models`, `POST /promote`, `GET /evals`, `/safety`, `/feedback`, `/cost`.
- **State:** Query; canary controls (role ml_ops).
- **Events:** `aiops_*` (audited).
- **Analytics:** model quality/cost/safety, internal.
- **DB:** scores(versions), ai_messages(feedback), audit_log.
- **Complexity:** High · **Est:** 7d.

### Handoff totals (frontend, indicative)
| Tier | Screens | Dev-days |
|---|---|---|
| Marketing (home/pricing/blog/methodology) | 4 | ~10 |
| Core app (S1–S13) | 13 | ~63 |
| Admin/AI-Ops (S14–S15) | 2 | ~13 |
| Mobile (iOS/Android/PWA shared via responsive) | — | ~18 |
| Design system foundation (components, tokens) | — | ~15 |
| **Total frontend** | | **~119 dev-days (~6 dev-months for 1 eng; ~10 weeks for a squad of 3)** |

> Backend, data/AI, and infra tracked separately (docs 03–06). End-to-end MVP (Phase 1 "Trust the Score": dashboard, stock detail, AI explain, search, alerts, auth, billing) ≈ **10–12 weeks** for a cross-functional squad.

---

# PART 3 — FINAL DESIGN REVIEW

## 3.1 Scorecard (0–100)

| Dimension | Score | Verdict |
|---|---|---|
| **UX** | 88 | Clear core loop (research → understand → act). Honest, non-prescriptive. Minor: onboarding-to-activation could be tighter. |
| **UI** | 90 | Disciplined token system, premium-calm aesthetic, consistent across 15 desktop + 24 mobile surfaces. |
| **Accessibility** | 84 | AA contrast, focus rings, semantic structure, color-never-alone. Gap: live-region announcements and screen-reader testing on charts not yet proven. |
| **Scalability** | 89 | Feature-sliced FE, modular-monolith BE, versioned scoring, cache layers. Gap: vector store will need a dedicated DB at scale. |
| **AI Experience** | 91 | Strongest pillar — answer→reasoning→confidence→sources contract, explainability, bull/bear balance, transparency page. |
| **Mobile Experience** | 86 | Genuinely native per-platform (not shrunk). Gap: offline depth and gesture richness still conceptual. |
| **Engineering Feasibility** | 87 | Stack is conventional and proven; estimates realistic. Gap: AA broker integration + live-data SLA are the real risks. |
| **Overall** | **88** | Production-ready foundation; ship Phase 1, harden the gaps below. |

## 3.2 Weaknesses identified
1. **Chart accessibility** — SVG charts lack text alternatives / data tables for screen readers (A11y 84).
2. **Activation friction** — the SEO-page → signup → first-value path has 4 steps; each adds drop-off.
3. **Confidence calibration is asserted, not proven** — needs a reliability-curve validation loop before users trust the % .
4. **Offline (PWA) is shallow** — "last synced" is shown but write-queue/sync-conflict UX is undefined.
5. **Empty-first experience** — a brand-new user with no holdings/watchlist sees many empty states at once; cold-start needs a guided path.
6. **Notification fatigue risk** — alert defaults aren't tuned; too many could erode trust.
7. **Vector store at scale** — pgvector is fine to start but a migration trigger/plan must be explicit.
8. **Regulatory edge** — "signals" vs "advice" line needs legal sign-off before launch copy is frozen.

## 3.3 Improvements applied / specified
1. **Chart a11y** — every chart ships a visually-hidden `<table>` of its data + `<figcaption>` takeaway; ScoreRing exposes `aria-label="Score 86 of 100, Strong Buy"`. → A11y target 90.
2. **Compress activation** — make the public Score page do more pre-signup (one free AI explain), defer profile questions to post-activation, and pre-fill watchlist from a paste. → fewer steps to first value.
3. **Confidence loop** — ship the reliability-curve in AI-Ops day one; show confidence only once calibrated, with a "how we measure confidence" link.
4. **Offline contract** — define a write-queue with optimistic UI + conflict resolution ("synced / pending / failed" per item) in the PWA spec.
5. **Cold-start path** — a single "Get started in 60s" guided card on an empty dashboard (sync OR add 3 stocks OR run a preset) instead of scattered empty states.
6. **Alert defaults** — ship conservative defaults (material moves only), a digest option, and a one-tap "too many?" calibrator.
7. **Scale trigger** — documented: migrate pgvector → dedicated vector DB when p95 retrieval > 150ms or corpus > ~5M chunks.
8. **Compliance gate** — legal review of signal language added to the Phase-1 launch checklist; disclaimers already pervasive.

---

# PART 4 — PRODUCTION-READY PACKAGE (manifest)

**Strategy & architecture (`/strategy`)**
- `01-product-strategy.md` — audience, personas, JTBD, positioning, monetization, prioritization
- `02-information-architecture.md` — sitemap, nav, flows, 74-screen inventory
- `03-backend-architecture.md` — HLD/LLD, schema, ER, API catalog, auth/z, billing, audit, security
- `04-data-ai-architecture.md` — ingestion, AI gateway, routing, RAG, confidence, cost, monitoring
- `05-frontend-architecture.md` — Next.js structure, state, caching, tokens, SEO, a11y, perf
- `06-devops-security-architecture.md` — Docker, CI/CD, monitoring, DR, secrets, RBAC, MFA, OWASP

**Design system & assets (`/design-system`, `/dhanradar-design-system`, `/dhanradar-website-design-system`, `/brand`)**
- Tokens: `tokens.json`, `css-variables.css`, `tailwind.config.js`, `figma-variables.json`
- `component-library.html` — 11 components × responsive variants
- `wireframes.html` — 13 lo-fi screens
- `hifi-screens.html` — 15 hi-fi desktop screens × 4 states
- `mobile-screens.html` — 8 screens × iOS/Android/PWA
- `ai-layer.html` — 12 AI UX patterns
- Brand kit — logos, favicons, OG, README

**This document (`/strategy/07`)** — Figma structure, per-screen handoff, final review.

## 4.1 Definition of done (Phase 1 launch)
- [ ] Figma file built to §1 structure; tokens synced to code
- [ ] Phase-1 screens implemented to handoff specs with all 4 states
- [ ] A11y improvements (chart alternatives, ARIA) shipped; axe + SR pass
- [ ] Confidence calibration loop live in AI-Ops
- [ ] Activation flow compressed; cold-start guided card
- [ ] Alert defaults conservative; notification preferences live
- [ ] Backend/data/infra per docs 03–06; OWASP controls verified; pen-test booked
- [ ] Legal sign-off on signal vs advice language
- [ ] CWV + a11y + bundle budgets green in CI

---

*Final verdict: an investor-grade, AI-native research platform — strategy through production — scoring **88/100** overall, with the eight weaknesses turned into a concrete hardening checklist. Ship Phase 1, measure activation and confidence-calibration, iterate.*
