# DhanRadar — Frontend Architecture

*Implementation-ready architecture for the DhanRadar web/PWA frontend. Stack: Next.js (App Router) · TypeScript · Tailwind · TanStack Query (React Query) · PWA. Consumes the backend (doc 03) and renders the approved design system.*

**Prepared by:** Staff Frontend Architecture · **Date:** June 2026 · **Status:** v1 for build

---

## 0. Principles

1. **Server-first, hydrate-light** — render on the server (RSC) wherever data is public/SEO-relevant; ship JS only for true interactivity.
2. **One source of design truth** — every color/space/type comes from the design tokens; no ad-hoc values.
3. **Server cache ≠ client cache** — Next's data cache handles SSR/ISR; React Query owns client/session state. They never fight.
4. **Feature-sliced** — code is organized by feature, not by file type. A feature owns its UI, hooks, and types.
5. **Accessible & fast by default** — a11y and Core Web Vitals are gates in CI, not afterthoughts.

---

## 1. Folder structure (Next.js App Router, feature-sliced)

```
src/
├── app/                          # App Router — routing + RSC
│   ├── (marketing)/              # public, SEO-indexed group
│   │   ├── page.tsx              # home
│   │   ├── pricing/page.tsx
│   │   ├── stocks/[symbol]/page.tsx   # SSR/ISR, public score preview
│   │   ├── funds/[symbol]/page.tsx
│   │   ├── blog/[slug]/page.tsx
│   │   └── layout.tsx            # marketing chrome
│   ├── (app)/                    # authenticated app group
│   │   ├── dashboard/page.tsx
│   │   ├── portfolio/page.tsx
│   │   ├── watchlist/page.tsx
│   │   ├── screener/page.tsx
│   │   ├── assistant/page.tsx
│   │   ├── settings/…/page.tsx
│   │   └── layout.tsx            # app shell (sidebar+topbar), auth guard
│   ├── (admin)/                  # role-gated ops shell (separate chrome)
│   ├── api/                      # route handlers (BFF: cookies, webhooks proxy)
│   ├── layout.tsx                # root: html, providers, fonts, theme
│   ├── manifest.ts               # PWA manifest
│   ├── sitemap.ts · robots.ts
│   └── not-found.tsx · error.tsx · global-error.tsx
├── features/                     # FEATURE SLICES (the bulk of the app)
│   ├── instrument/
│   │   ├── components/           # StockHeader, ScoreRing, FactorBars…
│   │   ├── hooks/                # useInstrument, useScore (React Query)
│   │   ├── api/                  # typed fetchers (client of backend)
│   │   ├── types.ts
│   │   └── index.ts              # public surface of the slice
│   ├── portfolio/ · watchlist/ · screener/ · ai/ · billing/ · auth/ · news/
├── components/                   # SHARED design-system primitives
│   ├── ui/                       # Button, Card, Table, Input, Badge, Tabs…
│   ├── charts/                   # ScoreRing, AreaChart, Sparkline, Donut
│   ├── feedback/                 # Toast, Skeleton, EmptyState, ErrorState
│   └── layout/                   # AppShell, Sidebar, TopBar, Container
├── lib/
│   ├── api/                      # base client (fetch wrapper, auth, retry)
│   ├── query/                    # QueryClient config, keys factory
│   ├── auth/                     # session helpers, guards
│   ├── format/                   # money/number/date (INR, tnum)
│   └── analytics/ · seo/ · pwa/
├── styles/
│   ├── globals.css               # Tailwind layers + token CSS vars
│   └── tokens.css                # generated from design tokens
├── hooks/                        # cross-feature (useMediaQuery, useTheme)
├── types/                        # global/shared types, API contract types
├── config/                       # env, feature flags, routes map
└── test/                         # setup, utils, msw handlers
```

**Rules:** a feature may import from `components/`, `lib/`, `hooks/`, `types/` — **never** from another feature's internals (only its `index.ts`). Enforced by ESLint `import/no-restricted-paths` (boundaries).

---

## 2. State management

Five clearly separated kinds of state — each with one owner:

| State kind | Owner | Example |
|---|---|---|
| **Server cache state** | TanStack Query | instrument, score, portfolio, screener results |
| **URL state** | Next router / `searchParams` | screener filters, active tab, pagination, theme deep-link |
| **Global UI state** | Zustand (tiny) | sidebar open, command palette, toast queue, theme |
| **Form state** | React Hook Form + Zod | auth, settings, alert rules, SIP setup |
| **Ephemeral local** | `useState` | hovers, dropdown open, optimistic toggles |

**Why not Redux:** server state is the majority and React Query handles it (cache, dedupe, refetch, invalidation). Global UI is small → Zustand. Forms → RHF. This keeps the bundle light and the mental model simple.

**Patterns**
- **URL as state for shareable views** — screener filters live in `searchParams` so a screen is linkable and SSR-able.
- **Optimistic updates** for watchlist add/remove and alert toggles (instant UI → reconcile on settle/rollback on error).
- **Server actions** (Next) for mutations that benefit from progressive enhancement (settings save); React Query `useMutation` for app-shell interactions needing optimistic UX.
- **Auth/session** read from an HttpOnly cookie on the server; client gets a minimal `useSession()` (user, plan, roles) hydrated once and kept in React Query with long stale time.

---

## 3. Caching

**Two-layer model — keep them in their lanes.**

### 3.1 Server (Next.js Data Cache)
| Surface | Strategy | Rationale |
|---|---|---|
| Marketing pages | **Static / ISR** (`revalidate`) | SEO, edge-cached, fast TTFB |
| Public stock/fund pages | **ISR** (e.g., `revalidate: 300`) + on-demand revalidate on score recompute | indexable + fresh |
| Blog/learn/glossary | Static, on-demand revalidate from CMS webhook | content-driven |
| Authenticated pages | **Dynamic** (no cache) or per-request | user-specific |

On-demand revalidation: backend emits a webhook → `revalidatePath`/`revalidateTag` when a score or content changes.

### 3.2 Client (TanStack Query)
- **Query key factory** (`lib/query/keys.ts`) — typed, hierarchical: `['instrument', symbol]`, `['score', symbol]`, `['portfolio']`, `['screener', filtersHash]`.
- **Stale times by volatility:** price 10–15s · score until next recompute (long) · portfolio 30s · static refs 1h.
- **Invalidation:** mutations invalidate by key prefix; a lightweight SSE/websocket channel pushes score-change + alert events → `queryClient.invalidateQueries`.
- **Prefetch & hydration:** server prefetches into a `dehydrate`d cache → `<HydrationBoundary>` so the first paint has data with no client waterfall.
- **Persistence (PWA):** `persistQueryClient` to IndexedDB for offline reads of last-synced portfolio/watchlist; max-age + busting on app version.

```
RSC server fetch ─▶ dehydrate ─▶ HydrationBoundary ─▶ client useQuery (warm)
                                                   ▲
                       SSE score/alert events ─────┘ invalidate
```

---

## 4. Component architecture

**Three tiers:**
1. **Primitives** (`components/ui`) — Button, Card, Input, Badge, Tabs, Table. Stateless, token-driven, fully a11y, variant API via `cva` (class-variance-authority). The implementation of the approved design system.
2. **Composites / charts** (`components/charts`, feedback) — ScoreRing, AreaChart, Skeleton, EmptyState, ErrorState, Toast. Reusable, data-shaped props, no business logic.
3. **Feature components** (`features/*/components`) — StockHeader, RecommendationCard, PortfolioTable. Compose primitives + hooks; own the feature's UX and states.

**Conventions**
- **Server Components by default**; add `"use client"` only for interactivity (charts with hover, forms, the assistant). Keeps JS minimal.
- **Every data component ships four states** — loading (Skeleton), empty (EmptyState), error (ErrorState + retry), success — wired to React Query's `isLoading/isError/data`. This is a lint-enforced pattern, mirroring the hi-fi spec.
- **Variants via `cva` + `tailwind-merge`** — typed, conflict-free class composition.
- **Polymorphism** via `asChild` (Radix Slot) for semantic correctness (`<Button asChild><Link/>`).
- **No prop-drilling** — feature hooks colocate data; context only for genuinely cross-cutting (theme, session).
- **Headless where it pays** — Radix primitives under the hood for Dialog, Popover, Tabs, Tooltip (a11y for free), styled with tokens.

---

## 5. Design token integration

Single pipeline from the design system to the app:

```
design-tokens (tokens.json — source of truth)
      │  Style Dictionary build (CI)
      ├─▶ styles/tokens.css      (CSS vars: --dr-blue, --surface, … per theme)
      └─▶ tailwind.config.ts     (preset: colors/space/radius/shadow/type → CSS vars)
```

- **Tailwind reads CSS vars**, not hardcoded hex — so `bg-surface`, `text-ink-muted`, `rounded-xl` resolve to `var(--surface)` etc., and **theme switching is a class on `<html>`** (`theme-light`/`theme-dark`) with zero re-render cost.
- **Fonts:** `next/font` self-hosts Manrope (display), Inter (body), JetBrains Mono (numbers) → no layout shift, no external request; exposed as `--font-display/body/mono`.
- **Theme:** SSR-safe — read `prefers-color-scheme` + cookie on the server, set the class before paint (no flash); user toggle persists to cookie + localStorage.
- **No magic numbers** — ESLint rule bans raw hex/px in `className`/`style`; everything routes through tokens. The design system stays the single source of truth.

---

## 6. SEO

- **App Router metadata API** — per-route `generateMetadata()` for title/description/canonical/OG, driven by instrument data (e.g., "Reliance share analysis & DhanRadar Score").
- **Server-rendered public surfaces** — stock/fund pages, blog, learn render fully on the server (RSC/ISR) so crawlers see real content + the ungated Score.
- **Structured data (JSON-LD)** — `FinancialProduct`/`Article`/`BreadcrumbList`/`FAQPage` injected server-side; rich results for instrument and learn pages.
- **`sitemap.ts` + `robots.ts`** — generated from the instrument/content catalog; app/admin routes disallowed.
- **Canonicalization** — one canonical per instrument (NSE+BSE dedupe), trailing-slash + locale normalized.
- **Performance = SEO** — Core Web Vitals (below) directly affect ranking; ISR keeps TTFB low at the edge.
- **i18n-ready** — `lang` + `hreflang` scaffolding for the planned Hindi-first regional expansion.

---

## 7. Accessibility (WCAG 2.1 AA — a CI gate)

- **Semantic HTML + landmarks** — `<nav> <main> <header>`, one `<h1>`/page, ordered headings; `<button>` for actions, `<a>` for navigation.
- **Radix primitives** for Dialog/Popover/Tabs/Menu → focus trap, ARIA, keyboard built-in.
- **Focus management** — visible `:focus-visible` ring (token-driven, never stripped); focus restored on route/dialog close; **skip-to-content** link first in tab order.
- **Color is never the only signal** — gain/loss pairs color with ▲▼ + sign; score bands pair color with label.
- **Forms** — labels tied to inputs, `aria-describedby` for errors, errors announced via live region; ≥16px inputs (no iOS zoom).
- **Targets & motion** — ≥44×44 touch targets; honor `prefers-reduced-motion` (disable non-essential animation).
- **Testing in CI** — `eslint-plugin-jsx-a11y` (lint) + `axe-core`/Playwright (automated audits) + Lighthouse a11y budget; manual screen-reader pass on critical flows each release.

---

## 8. Performance optimization

**Targets (CI budgets):** LCP < 2.0s · INP < 200ms · CLS < 0.1 · initial JS < ~120KB gz per route.

| Lever | How |
|---|---|
| **Less JS** | RSC by default; `"use client"` only where needed; tree-shake; route-level code-split |
| **Charts** | lightweight SVG primitives (our own) over heavy chart libs; lazy-load the assistant/heavy widgets with `next/dynamic` |
| **Images** | `next/image` (AVIF/WebP, responsive, lazy); OG images via `@vercel/og` |
| **Fonts** | `next/font` self-host + `font-display: swap`; preconnect none (no external) |
| **Data** | server prefetch + hydrate (no client waterfall); React Query dedupe; SSE for live deltas instead of polling |
| **Caching** | ISR + edge for public; persisted client cache for instant repeat/offline |
| **CLS** | reserved skeleton dimensions, no layout-shifting ads, sized media |
| **INP** | keep main thread free — defer non-critical work, virtualize long tables (`@tanstack/virtual`), debounce screener inputs |
| **Bundle hygiene** | `@next/bundle-analyzer` in CI; per-route size budget fails the build on regression |

**PWA specifics** — `next-pwa`/Workbox service worker: app-shell precache, runtime cache for instrument/score (stale-while-revalidate), offline fallback page, background sync for queued mutations; installable via `manifest.ts`; offline banner driven by `navigator.onLine` + SW state.

---

## 9. Cross-cutting

- **Type safety end-to-end** — generate TS types from the backend OpenAPI (`openapi-typescript`) so API contracts are compile-checked; Zod validates at runtime boundaries.
- **Error handling** — route `error.tsx` boundaries per segment; global error boundary; React Query ret/backoff; RFC7807 problem+json mapped to friendly UI.
- **Auth guard** — `(app)` and `(admin)` layouts verify the session cookie server-side and redirect; client never holds long-lived secrets (access token in memory, refresh in HttpOnly cookie).
- **Feature flags** — `config/flags` (server-evaluated) gate canary UI (e.g., new AI model, redesigns).
- **Testing pyramid** — Vitest + RTL (unit/component), MSW (API mocking), Playwright (e2e critical flows: signup→activate, research→watchlist, upgrade), visual regression on the design-system primitives.
- **CI gates** — typecheck, lint (incl. a11y + import boundaries + no-magic-tokens), unit/e2e, Lighthouse (perf/a11y/SEO budgets), bundle-size budget. Red on any breach.

---

## Appendix — build order

1. Tokens pipeline (Style Dictionary → tokens.css + tailwind preset) + `components/ui` primitives.
2. App Router skeleton: root providers (Query, theme, session), `(marketing)`/`(app)` groups, app shell.
3. API client + query keys + OpenAPI types + auth guard.
4. Instrument slice (public SSR/ISR stock page) — proves SEO + tokens + four-state components.
5. App surfaces (dashboard, portfolio, watchlist, screener) with prefetch/hydrate.
6. AI slice (assistant streaming via SSE) + PWA (SW, manifest, offline, persisted cache).
7. CI budgets (CWV, bundle, a11y) wired before scaling features.

*Pairs with the design system, hi-fi screens, and mobile/PWA patterns already delivered. Next artifacts: the `components/ui` API spec, the query-keys factory, and the Style Dictionary config.*
