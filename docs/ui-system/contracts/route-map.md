# Route Map (URL ↔ page ↔ API ↔ auth)

> ⛔ **DO NOT ADOPT — HARVEST-NOT-ADOPT REFERENCE ONLY (B41).**
> Part of the `docs/ui-system` kit, which **conflicts with the binding
> architecture** and is **not** a source of truth. Do not implement from it.
> Authority: `docs/DhanRadar_Architecture_Final.md`; apply only per
> `docs/project-state/MIGRATION_STRATEGY_FINAL.md` (KEEP/MERGE/REPLACE/IGNORE).

| Route | Page component | Primary API | Group | Auth | Render |
|---|---|---|---|---|---|
| / | MarketingHome | /billing/plans | (marketing) | public | static |
| /pricing | Pricing | /billing/plans | (marketing) | public | static |
| /stocks/[symbol] | StockDetail | /stocks/{sym} | (marketing) | public* | ISR 300s |
| /funds/[symbol] | FundDetail | /funds/{sym} | (marketing) | public* | ISR 300s |
| /etfs/[symbol] | ETFDetail | /etfs/{sym} | (marketing) | public* | ISR 300s |
| /blog/[slug] | BlogArticle | CMS | (marketing) | public | ISR |
| /login /signup | Auth | /auth/* | (marketing) | public | dynamic |
| /dashboard | Dashboard | /indices,/instruments/top-scored,/news,/portfolio/summary | (app) | user | dynamic |
| /recommendations | RecommendationHub | /recommendations | (app) | user | dynamic |
| /screener | Screener | /screener/stocks | (app) | user | dynamic |
| /portfolio | Portfolio | /portfolio,/holdings | (app) | user | dynamic |
| /watchlist | Watchlist | /watchlists | (app) | user | dynamic |
| /assistant | AIAssistant | /ai/assistant (SSE) | (app) | user | dynamic |
| /news | NewsCenter | /news | (app) | user | dynamic |
| /alerts | AlertsCenter | /alerts | (app) | user | dynamic |
| /settings | Settings | /users/me/settings | (app) | user | dynamic |
| /subscription | Subscription | /billing/* | (app) | user | dynamic |
| /admin | AdminDashboard | /admin/* | (admin) | admin | dynamic |
| /aiops | AIOpsDashboard | /aiops/* | (admin) | ml_ops | dynamic |

*public = score ungated; premium fields (fair value, analytics) gated server-side.
