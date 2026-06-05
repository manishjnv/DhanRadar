# Per-Screen Analytics (screen → events)

| Screen | Events fired |
|---|---|
| Public stock/fund page | seo_instrument_view, recommendation_viewed, ai_answer_viewed(1 free), signup_started |
| Signup/OTP | signup_started, signup_completed, otp_verified |
| Onboarding | onboarding_completed, first_* , activation_completed, consent props |
| Dashboard | dashboard_viewed, top_scored→recommendation_clicked, news_viewed |
| Recommendation Hub | recommendation_viewed/clicked/why_opened/converted, rec_filter |
| Stock/Fund/ETF Detail | stock_viewed, tab_changed, period_changed, factor_explained, fairvalue paywall_hit, alert_created, watchlist_added |
| Screener | screener_run, compare_used |
| Portfolio | portfolio_viewed, holding_added, broker_synced, analytics_gate_hit, report_downloaded |
| Watchlist | watchlist_added/removed, alert_toggled |
| AI Search | ai_search, ai_answer_viewed, ai_result_clicked, ai_quota_hit |
| AI Assistant | assistant_asked, ai_feedback, assistant_drill |
| News | news_viewed, news_filter, news_ticker_clicked |
| Subscription | pricing_viewed, plan_selected, checkout_*, subscription_canceled |
| Settings | setting_change, 2fa_enable, consent_changed |
| All | page_viewed, session_started/ended, paywall_hit |

Implementation: a typed `track(event, props)` wrapper (auto-attaches super-properties + request_id); events colocated in feature hooks; validated against the tracking plan in CI.
