# Message Flow Diagrams

## A. Market data → score → alert → notify
```
[ingestion] --MarketDataUpdated--> (market.data.updated)
   ├─> [scoring] recompute --RecommendationGenerated--> (reco.generated)
   │      ├─> [cache-invalidator] drop score:{sym}
   │      ├─> [ai-explainer] pre-gen explanation
   │      ├─> [recommendation-audit] persist (immutable, disclosures)
   │      └─> [alert-evaluator] score-crossed? --AlertTriggered--> (alert.triggered)
   │                 └─> [notification] send --NotificationSent--> (notify.sent) --> [audit]
   ├─> [screener-indexer] update ES
   └─> [alert-evaluator] price-crossed? --AlertTriggered--> ...
```

## B. News → sentiment + summary + alert
```
[news-pipeline] --NewsProcessed--> (news.processed)
   ├─> [sentiment-factor] update instrument sentiment (feeds next score)
   ├─> [ai-summarizer] pre-gen summary (cached)
   ├─> [feed-cache] invalidate
   └─> [alert-evaluator] holding/watchlist match? --AlertTriggered--> notify
```

## C. Subscription lifecycle
```
[razorpay webhook] -> [billing] verify+idempotent
   --SubscriptionActivated--> (billing.subscription.activated)
   ├─> [entitlements] invalidate ent:{user}; unlock features
   ├─> [notification] receipt --NotificationSent-->
   └─> [audit]
(dunning) payment.failed -> retry schedule -> grace expiry --SubscriptionLapsed--> downgrade+notify+audit
```

## D. Portfolio sync (AA) + CA adjust
```
[portfolio] broker sync --PortfolioUpdated--> (portfolio.updated)
   ├─> [portfolio-score] recompute
   ├─> [analytics] refresh
   └─> [insights] regenerate (consent-gated)
[ingestion] --CorporateActionApplied--> [portfolio] adjust holdings --PortfolioUpdated--> ...
```

## Failure handling (all flows)
```
consumer fail -> retry(backoff,jitter,max N) -> {topic}.dlq -> ops inspect -> replay|discard
duplicate event -> deduped by event_id (no double side effect)
```
