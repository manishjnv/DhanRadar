# Analytics Tracking Plan

Columns: Event · When · Key properties · KPI it feeds.

## Acquisition
| Event | When | Properties | KPI |
|---|---|---|---|
| page_viewed | any page | path, referrer, utm_* | traffic, channel CAC |
| seo_instrument_view | public stock/fund page | symbol, score | SEO funnel top |
| signup_started | signup form open | source | signup funnel |
| signup_completed | account created | method | signups, CAC |
| otp_verified | OTP success | — | signup completion |

## Activation
| activation_completed | first value | via: watchlist\|ai\|sync | **activation rate** |
| onboarding_completed | finished onboarding | skipped? | onboarding completion |
| first_watchlist_add / first_ai_explain / first_broker_sync | first of each | symbol? | activation drivers |

## Engagement
| dashboard_viewed | dashboard load | — | DAU |
| stock_viewed | stock detail | symbol, score | research depth |
| tab_changed / period_changed / factor_explained | interaction | symbol, tab/period/factor | depth |
| screener_run | run screener | filters_count, results | discovery |
| compare_used | compare | n_instruments | depth |
| news_viewed / news_ticker_clicked | news | tag?, symbol? | engagement |
| learn_lesson_started/completed | learn | topic | education |

## Recommendation
| recommendation_viewed | rec card seen | symbol, signal, confidence_band | impressions |
| recommendation_clicked | card/why click | symbol, signal, target | **rec CTR** |
| recommendation_why_opened | explainability open | symbol | trust |
| recommendation_converted | add-to-watchlist/alert from rec | symbol, signal | **rec conversion** |

## AI
| ai_search | query submitted | has_answer, cached | AI adoption |
| ai_answer_viewed | answer rendered | confidence_band, sources_n | AI usage |
| ai_result_clicked | result tap | symbol | AI→research |
| assistant_asked | assistant turn | turn_index | AI depth |
| ai_feedback | 👍/👎 | rating | helpful-rate |
| ai_quota_hit | quota reached | plan | quota→upgrade |

## Search / Portfolio / Alerts
| search_opened / search_selected | ⌘K | scope, symbol? | search usage |
| portfolio_viewed / holding_added / broker_synced / analytics_gate_hit / report_downloaded | portfolio | source | portfolio usage |
| watchlist_added / watchlist_removed | watchlist | symbol | tracking |
| alert_created / alert_triggered_view / alert_toggled | alerts | type | alert adoption |

## Subscription / Referral / Retention
| pricing_viewed / plan_selected / checkout_started / checkout_succeeded / checkout_failed / subscription_canceled | billing | plan, cycle | **subscription funnel** |
| paywall_hit | gated feature | feature, plan | paywall→upgrade |
| trial_started / trial_ending_viewed | trial | — | trial conversion |
| referral_link_created / referral_signup / referral_rewarded | referral | — | **K-factor** |
| session_started / session_ended | session | duration | retention, stickiness |

## Governance
- Tracking plan is versioned; new events require PR + analytics review (no rogue events). QA: events validated in staging vs plan before release.
