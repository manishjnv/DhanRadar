# Analytics Event Catalog

> ⛔ **DO NOT ADOPT — HARVEST-NOT-ADOPT REFERENCE ONLY (B41).**
> Part of the `docs/ui-system` kit, which **conflicts with the binding
> architecture** and is **not** a source of truth. Do not implement from it.
> Authority: `docs/DhanRadar_Architecture_Final.md`; apply only per
> `docs/project-state/MIGRATION_STRATEGY_FINAL.md` (KEEP/MERGE/REPLACE/IGNORE).

Convention: snake_case verb_noun; properties typed. Sink: PostHog. PII-free.

| Event | Properties | Where |
|---|---|---|
| signup_start / signup_complete | {method} | auth |
| otp_verify | {success} | auth |
| activation_complete | {via: watchlist|ai|sync} | onboarding |
| dashboard_view | — | dashboard |
| top_scored_click | {symbol} | dashboard |
| stock_view | {symbol, score} | stock |
| period_change | {symbol, period} | stock/fund/etf |
| tab_change | {symbol, tab} | stock |
| factor_explain | {symbol, factor} | stock |
| fairvalue_gate_hit | {symbol} | stock |
| rec_view / rec_filter / rec_add_watchlist / rec_why_click | {symbol?, signal?, sector?} | recommendations |
| watchlist_add / watchlist_remove / alert_toggle | {symbol} | watchlist |
| alert_create | {symbol, type} | stock/alerts |
| portfolio_view / holding_add / broker_sync / analytics_gate_hit / report_download | {} | portfolio |
| ai_search / ai_answer_view / ai_result_click / ai_quota_hit | {has_answer, cached?} | ai search |
| assistant_open / assistant_ask / assistant_feedback / assistant_drill | {rating?, symbol?} | assistant |
| news_view / news_filter / news_ticker_click | {tag?, symbol?} | news |
| pricing_view / plan_select / checkout_start / checkout_success / checkout_fail / subscription_cancel | {plan} | billing |
| setting_change / 2fa_enable | {key} | settings |
