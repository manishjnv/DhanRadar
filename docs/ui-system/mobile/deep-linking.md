# Deep Linking

## Scheme
- **Universal Links (iOS)** + **App Links (Android)** + standard web URLs (PWA) → one URL space, app opens if installed, web fallback otherwise.
- Custom scheme `dhanradar://` for internal/push payloads.

## Route map (shared)
| Link | Opens |
|---|---|
| /stocks/{sym} | Stock Detail |
| /funds/{sym} · /etfs/{sym} | Fund/ETF Detail |
| /portfolio · /watchlist · /alerts | respective |
| /assistant?q=... | AI Assistant (prefilled) |
| /recommendations?signal=strong_buy | filtered hub |
| /subscription | paywall/plans |
| /share/score/{sym} | shared score card (public preview) |
| /referral/{code} | signup w/ referral attribution |

## Handling
- App registers domains (apple-app-site-association / assetlinks.json).
- Cold start: route after auth (deferred deep link if login needed).
- Push notifications carry `route` → open exact screen.
- Marketing/SEO/share links are the same URLs → seamless web↔app continuity + referral attribution.

## Attribution
- utm_* + referral code captured on first open → analytics (acquisition, K-factor).
