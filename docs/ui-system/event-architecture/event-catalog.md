# Event Catalog

Topics: `market.* reco.* news.* portfolio.* alert.* billing.* notify.* audit.*`. All events share an envelope (see contracts).

| Event | Topic | Producer | Consumers | Trigger |
|---|---|---|---|---|
| **MarketDataUpdated** | market.data.updated | ingestion | scoring, screener-indexer, cache-invalidator, alert-evaluator | EOD/intraday price or NAV load |
| **CorporateActionApplied** | market.ca.applied | ingestion | scoring, portfolio, audit | CA adjustment applied |
| **RecommendationGenerated** | reco.generated | scoring engine | cache-invalidator, alert-evaluator, ai-explainer, audit, recommendation-audit | nightly recompute / score change |
| **NewsProcessed** | news.processed | news pipeline | sentiment-factor, feed-cache, alert-evaluator, ai-summarizer | news ingested+tagged+embedded |
| **PortfolioUpdated** | portfolio.updated | portfolio svc | analytics, portfolio-score, insights, audit | holding add/sync/CA adjust |
| **AlertTriggered** | alert.triggered | alert-evaluator | notification, audit | rule condition met |
| **SubscriptionActivated** | billing.subscription.activated | billing (webhook) | entitlements, notification, audit | payment success / renewal |
| **SubscriptionLapsed** | billing.subscription.lapsed | billing (dunning) | entitlements, notification, audit | grace expired |
| **NotificationSent** | notify.sent | notification svc | audit, analytics | push/email/in-app delivered |
| **AIOutputGenerated** | audit.ai.output | AI gateway | recommendation-audit, ai-ops-metrics | any AI answer served |
| **UserConsentChanged** | audit.consent.changed | users/settings | consent-ledger, audit | consent grant/withdraw |

## Fan-out example (price → user)
```
MarketDataUpdated → scoring → RecommendationGenerated → alert-evaluator
  → AlertTriggered → notification → NotificationSent → audit
(each hop: idempotent, retried, audited)
```
