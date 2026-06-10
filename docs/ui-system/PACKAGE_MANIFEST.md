# PACKAGE MANIFEST — DhanRadar Complete Design System

**Version 1.0 · June 2026.** Hand directly to Claude Code. Branding is LOCKED.

## Folder structure
```
DhanRadar-Complete/
  README.md
  PACKAGE_MANIFEST.md
  brand/            README.md tokens.json tokens.css tailwind.config.js
  design-system/    tokens.json css-variables.css tailwind.config.js figma-variables.json
  tokens/           colors.json typography.json spacing.json radius.json elevation.json motion.json themes.json tailwind.config.js css-variables.css tokens.md
  components/        Button.md Card.md Input.md Search.md Table.md Sidebar.md Chart.md Watchlist.md RecommendationCard.md
  screens/          dashboard.md recommendations.md stock-detail.md fund-detail.md etf-detail.md portfolio.md watchlist.md ai-search.md ai-assistant.md news.md subscription.md settings.md admin.md
  ux/               user-personas.md journeys.md flows.md wireframes.md heuristics.md accessibility.md
  figma/            01-cover.md 02-brand-system.md 03-design-tokens.md 04-components.md 05-desktop.md 06-mobile.md 07-prototypes.md 08-engineering-handoff.md 09-variables.md 10-auto-layout-rules.md
  claude-code/      frontend-spec.md backend-spec.md api-spec.md database-spec.md state-management.md routing-spec.md auth-spec.md notification-spec.md ai-spec.md search-spec.md recommendation-engine.md
  nextjs-blueprint/ project-structure.md app-router-structure.md component-structure.md page-structure.md api-client-structure.md state-management.md design-token-integration.md tailwind-setup.md shadcn-mapping.md
  html/             DhanRadar.html DhanRadar-DesignSystem.html dhanradar-design-system.html dhanradar-website-design-system.html component-library.html wireframes.html hifi-screens.html mobile-screens.html ai-layer.html
  docs/             01-product-strategy.md 02-information-architecture.md 03-backend-architecture.md 04-data-ai-architecture.md 05-frontend-architecture.md 06-devops-security-architecture.md 07-figma-structure-and-handoff.md VALIDATION_REPORT.md FINAL_AUDIT.md
```

## What each folder is
| Folder | Purpose | Depends on |
|---|---|---|
| /brand | Logo guidance, brand tokens, voice | — |
| /design-system | Token source (json/css/tailwind) + Figma variables | /brand |
| /tokens | Split token files + tailwind + css + tokens.md | /design-system |
| /components | 9 component specs (purpose/states/variants/props/a11y/responsive/react/tailwind) | /tokens |
| /screens | 13 screen specs (layout/components/API/data/states/responsive/analytics) | /components, /claude-code |
| /ux | Personas, journeys, flows, wireframes, heuristics, accessibility | — |
| /figma | 10 Figma build docs | /tokens, /components |
| /claude-code | 11 implementation-ready specs | /docs |
| /nextjs-blueprint | 9 Next.js blueprints | /claude-code |
| /html | 9 self-contained renderable HTML files (open directly) | — |
| /docs | 7 architecture docs + VALIDATION_REPORT + FINAL_AUDIT + GAP_CLOSURE | — |
| /contracts | openapi.yaml, schema.sql, seed-data.json, route-map, analytics-events, error-catalog, score-model | — |
| /project-config | .env.example, package.json, pyproject.toml, docker-compose.yml, github-actions-ci.yml | /contracts |
| /reference-impl | compile-ready starters (cn, apiClient, queryKeys, tailwind preset, Button, Card, ScoreRing) | /tokens |
| GETTING_STARTED.md | exact local-run commands + build order | /project-config, /contracts |
| /launch | launch-readiness remediation: compliance, data licensing, DPDP, AA consent, AI eval/safety, incident runbook, secrets, data quality, capacity, onboarding, a11y + LAUNCH_CHECKLIST | — |
| LAUNCH_READINESS_REVIEW.md | 22 findings (cat/sev/impact/rec/priority/effort); all Critical+High remediated; readiness 98/100 | /launch |
| /compliance | SEBI/legal compliance architecture: research-vs-advisory separation, risk-profiling engine, recommendation disclosures, audit trail, legal (T&C/privacy/consent/retention), disclaimer framework, affected-screens | /launch |
| /market-data | NSE/BSE/AMFI ingestion, corporate actions (div/split/bonus/rights), fundamental/technical/historical, quality framework, SLA, reconciliation engine, storage strategy, holiday + recovery | /docs/03, /docs/04 |
| /recommendation-engine | production quant engine: factor catalog, score + confidence + risk formulas, normalization, missing-data, sector/liquidity adjustments, news-sentiment, backtesting, benchmarks, model versioning, lifecycle | /docs/03, /contracts/score-model.md |
| /ai-governance | AI governance: prompt management/versioning/testing/approval, evaluation (test/A-B/regression), quality scoring, LLM observability (cost/token/routing), hallucination/grounding/attribution controls | /docs/04 |
| /event-architecture | event-driven design: domain events, event bus (Redis Streams→Kafka-ready), versioned contracts, retry/DLQ/idempotency/replay, audit events, catalog + message-flow diagrams | /docs/03 |
| /observability | SRE observability: metrics/logs/traces, business/product/AI/recommendation/notification/subscription/cost KPIs, dashboards (exec/product/eng/ai-ops/support), alerting framework, SLA/SLO spec | /docs/06 |
| /analytics | growth analytics: event taxonomy, tracking plan, per-screen events, subscription funnel, retention framework, growth metrics + North Star (WRI), executive dashboard | /observability |
| /mobile | mobile architecture (iOS/Android/PWA), notification architecture, offline strategy, deep linking, biometric/background-sync/widgets/share, app-store readiness | /docs/05 |
| PRODUCTION_READINESS_REPORT.md | final 12-dimension scorecard (98/100), remaining execution-phase gaps + owners | all |
| IMPLEMENTATION_ROADMAP.md | MVP (10wk) · 90-day · 180-day plans, critical path, team scaling | all |
| CLAUDE_CODE_STARTER_GUIDE.md | zero-ambiguity bootstrap + build order + non-negotiable invariants for Claude Code | contracts, all |

## Implementation order
1. Read /docs/01–07 + /ux.
2. Wire /tokens into Tailwind (/nextjs-blueprint/tailwind-setup.md).
3. Build components/ui from /components/*.md (+ shadcn mapping).
4. Backend: schema/auth/API from /claude-code (backend/database/api/auth specs).
5. Data/AI: ingestion + gateway + recommendation engine (/claude-code/ai-spec, recommendation-engine, search-spec + /docs/04).
6. Frontend: App Router + slices + screens (/nextjs-blueprint + /screens/*.md).
7. DevOps/Security: /docs/06.
8. Phase-1 MVP first: dashboard, stock detail, AI explain, search, alerts, auth, billing (~10–12 weeks/squad).

## Renderable HTML
Open any `/html/*.html` directly in a browser — all self-contained (fonts via Google CDN).

## Cross-reference
- Per-screen handoff (complexity + estimates): /docs/07 Part 2.
- Final audit + scores: /docs/FINAL_AUDIT.md.
