# DhanRadar — Mobile Architecture

*Mobile Architect. Three surfaces: native iOS, native Android, and PWA. Shares the same API + design tokens; native patterns per platform (not shrunk desktop).*

## 1. Strategy
| Surface | Tech | When |
|---|---|---|
| **PWA** | Next.js installable + service worker | day-1 reach, web parity, cheap |
| **iOS** | Swift / SwiftUI (or React Native if one codebase preferred) | App Store presence, widgets, biometrics |
| **Android** | Kotlin / Jetpack Compose (or React Native) | Play Store, widgets, biometrics |

**Recommendation:** ship **PWA first** (fastest, installable), then native iOS+Android via **React Native** (shared business logic + the existing design tokens) unless platform-specific performance demands fully native. Native gives: home-screen **widgets**, richer **push**, **biometric** keychain, background tasks, App/Play store distribution.

## 2. Shared layers
- **API client** — same `/v1` REST + SSE (assistant). OpenAPI-generated types (RN/TS) or codegen (Swift/Kotlin).
- **Design tokens** — `/tokens` → platform themes (Compose theme / SwiftUI tokens / Tailwind for PWA). Branding locked.
- **Auth** — RS256 JWT (15m) + rotating refresh; refresh stored in secure storage (Keychain/Keystore), access in memory.
- **State** — server cache (RN: TanStack Query; native: repository + cache); offline store (below).

## 3. Navigation
- iOS: tab bar (Markets/Discover/AI/Portfolio/Profile) + push nav + sheets.
- Android: bottom nav (Material 3) + FAB + back-stack.
- PWA: bottom tab + standalone display.
- All driven by a shared route map (see deep-linking.md).

## 4. Performance
- Lazy-load heavy screens (assistant); virtualize long lists (holdings/screener).
- Image/chart: lightweight SVG/canvas; cache rendered charts.
- Cold-start budget < 2s to first meaningful paint; prefetch dashboard data on launch.

## 5. Platform features (covered in detail)
Offline (offline-strategy) · Push (notification-architecture) · Biometric login · Background sync · Widgets · Deep linking (deep-linking) · Share flows · Store readiness (app-store-readiness).

### Biometric login
- Face ID / Touch ID (iOS LocalAuthentication) · BiometricPrompt (Android) · WebAuthn/passkeys (PWA).
- Flow: first login with credentials → offer "enable biometric" → store refresh token in Keychain/Keystore gated by biometric → subsequent launches unlock via biometric → silent token refresh.
- Fallback to passcode/password; never store the password itself; step-up biometric for sensitive actions (payment, broker link).

### Background sync
- iOS: BGAppRefreshTask / BGProcessingTask. Android: WorkManager (periodic + constraints: network, charging optional). PWA: Background Sync API + Periodic Sync (where supported).
- Tasks: refresh portfolio/watchlist scores, deliver queued mutations, prefetch dashboard, update widgets. Respect battery/network; coalesce; honor OS budgets.

### Portfolio widgets
- iOS WidgetKit (small/medium/large): portfolio value + day change + top mover + a watchlist score. Timeline refresh via background + push.
- Android App Widget / Glance: same content; update via WorkManager + push.
- PWA: no home widgets (OS limit) — use notifications + install shortcut.
- Widget data via a lightweight `/widget/summary` endpoint; cached; respects auth (signed-in only).

### Share flows
- Share a **Score card** (stock/fund) as an image + deep link; share watchlist/portfolio snapshot (privacy-aware: no holdings amounts unless opted).
- iOS Share Sheet / Android Intent / Web Share API. Shared links are deep links (below) → drive viral acquisition (referral attribution).
