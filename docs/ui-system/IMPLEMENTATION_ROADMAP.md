# DhanRadar — Implementation Roadmap

*From spec to launch. Assumes a cross-functional squad (≈2 BE, 2 FE, 1 data/AI, 1 design, 0.5 SRE, PM) scaling over time. Architecture: docs 03–06 + subsystem folders.*

## MVP Build Plan (Weeks 0–10) — "Trust the Score"
**Goal:** the core loop for the picker persona, public-launchable for a beta.
- **Wk 0–1 Foundations:** repo, CI/CD, docker-compose, tokens→Tailwind, `components/ui` from /components, OpenAPI types, auth scaffolding.
- **Wk 2–3 Backend core:** schema (contracts/schema.sql), auth (JWT+OTP+social), instruments/scores read API, Elasticsearch search, seed data.
- **Wk 3–5 Data + scoring:** ingestion contract + mock→licensed provider, score engine v1 (recommendation-engine spec), nightly recompute, corporate-action adjust + reconciliation.
- **Wk 4–6 Frontend core:** App Router, public stock page (SSR/ISR + ungated score), dashboard, search, four states, a11y.
- **Wk 5–7 AI:** AI Gateway (auth/cache/route/safety/attribution), Explainability + AI Search, governance evals, prohibited-language gate.
- **Wk 6–8 Watchlist + alerts:** watchlists, alert rules, event-driven evaluation, notifications.
- **Wk 7–9 Billing:** plans, Razorpay checkout/webhook, entitlements, paywall, GST/invoices.
- **Wk 8–10 Hardening:** observability dashboards, analytics events, compliance disclosures + audit trail, security pass, load test, beta.
- **Exit:** beta users research→explain→watchlist→alert→upgrade; SLOs green; disclosures live.

## 90-Day Plan (Weeks 0–12) — "Launch-ready"
- MVP (above) + **Portfolio** (manual add + AA sync, portfolio score, holdings), **Fair Value** (Pro gate), **screener** (full filters + save).
- **AI Assistant** (SSE) + Portfolio Insights (consent-gated).
- **Mobile PWA** (installable, offline, push) live.
- **Compliance P0s closed:** legal sign-off (G1), licenses (G2), DPDP flows, AA consent tested.
- **Ops:** on-call, runbooks, DR drill #1, pen-test, status page.
- **Confidence:** reliability-curve calibrating (band-only until ±10%).
- **Exit = public launch:** LAUNCH_CHECKLIST P0+P1 green.

## 180-Day Plan (Months 3–6) — "Scale & deepen"
- **Native iOS + Android** (React Native) with widgets, biometrics, background sync.
- **Mutual Fund + ETF** deep dives; News Center; Compare; Learn hub.
- **Premium tier:** tax optimization, curated portfolios, API access, AI deep-dive.
- **Score model v2** (backtested, canary→promote); confidence % exposed (calibrated).
- **Growth:** referral loop, SEO content engine, regional (Hindi) scaffolding.
- **Scale:** read replicas, KEDA tuning, vector-store migration trigger watch; soak/spike tests.
- **Exit:** WRI growth, Free→Pro 4–6%, D30 ≥35%, LTV:CAC >4, 99.9% availability.

## Dependencies & critical path
```
tokens+components → frontend screens
schema+auth → all APIs → frontend data
ingestion+scoring → recommendation surfaces (critical path)
AI gateway → explainability/search/assistant
billing → monetization
compliance/licensing (parallel) → public launch gate
```

## Team scaling
- MVP: 1 squad. 90-day: +1 FE, +1 data/AI. 180-day: + mobile pair, +1 SRE, +growth/analytics.
