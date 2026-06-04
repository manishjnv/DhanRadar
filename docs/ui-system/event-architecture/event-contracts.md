# Event Contracts (versioned)

## Envelope (all events)
```json
{
  "event_id": "uuid",
  "type": "RecommendationGenerated",
  "version": 1,
  "topic": "reco.generated",
  "occurred_at": "ISO-8601",
  "producer": "scoring-worker",
  "key": "RELIANCE",                 // partition/order key
  "trace_id": "uuid",                // OpenTelemetry correlation
  "idempotency_key": "RELIANCE:2026-06-05:v2.4",
  "data": { /* event-specific, below */ }
}
```
Rules: additive evolution only; new required field → new `version`; consumers tolerate unknown fields.

## data payloads
```json
// MarketDataUpdated
{ "instrument_id":"uuid","symbol":"RELIANCE","kind":"price|nav","as_of":"date",
  "close":2841.30,"volume":8420000,"source":"vendorA","adjusted":true }

// RecommendationGenerated
{ "instrument_id":"uuid","symbol":"RELIANCE","as_of":"date","model_version":"v2.4",
  "score":86,"signal":"strong_buy","prev_score":85,"factors":{...},
  "fair_value":3120,"confidence":80,"coverage":0.98 }

// NewsProcessed
{ "news_id":"uuid","headline":"...","tag":"earnings","instruments":["RELIANCE"],
  "sentiment":0.42,"published_at":"ISO","source":"publisherX" }

// PortfolioUpdated
{ "user_id":"uuid","change":"add|sync|ca_adjust","instrument_id":"uuid",
  "qty":38,"avg_price":2412,"source":"broker|manual" }

// AlertTriggered
{ "rule_id":"uuid","user_id":"uuid","instrument_id":"uuid","type":"price|score|risk|earnings",
  "condition":">4100","observed":4102.10,"triggered_at":"ISO" }

// SubscriptionActivated
{ "user_id":"uuid","subscription_id":"uuid","plan":"pro","status":"active",
  "period_end":"ISO","gateway_payment_id":"pay_...","amount_inr":399 }

// NotificationSent
{ "user_id":"uuid","channel":"push|email|inapp","template":"price_alert",
  "ref_event_id":"uuid","delivered":true,"sent_at":"ISO" }
```

## Compliance note
Events carrying recommendations (RecommendationGenerated, AIOutputGenerated) are mirrored to the immutable recommendation_audit with disclosures rendered — satisfying evidence retention.
