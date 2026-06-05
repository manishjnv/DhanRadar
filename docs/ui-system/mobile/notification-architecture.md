# Notification Architecture

## Channels
- **iOS:** APNs (via FCM or direct). **Android:** FCM. **PWA:** Web Push (VAPID) + service worker.
- **In-app:** notification center (from event bus); **email** fallback (SES) for important misses.

## Flow
```
AlertTriggered / SubscriptionActivated / digest (event bus)
  → notification service: resolve user devices + preferences + quiet hours
  → render template (versioned) + NOT_ADVICE disclaimer
  → push via APNs/FCM/WebPush (idempotent, dedupe by event_id)
  → NotificationSent event → audit + analytics
  → deep link payload → opens the right screen
```

## Token management
- Register device token on login/permission grant → `device_tokens(user_id, platform, token, last_seen)`.
- Refresh on rotation; prune stale; unregister on logout.

## Preferences & anti-fatigue
- Per-category toggles (price/score/risk/earnings/SIP/digest) + **quiet hours** + frequency caps.
- Conservative defaults (material moves only); digest option; one-tap "too many?" calibrator.
- Compliance: every notification carries NOT_ADVICE; no "act now" urgency.

## Reliability
- Delivery tracked (sent/delivered/opened); bounce handling; retry on transient APNs/FCM errors.
- Critical alerts (price/score) prioritized; marketing throttled. Idempotent (no double-send).

## Payload (deep-link)
```json
{ "type":"price_alert","symbol":"TCS","route":"/stocks/TCS","alert_id":"...","disclaimer":"NOT_ADVICE" }
```
