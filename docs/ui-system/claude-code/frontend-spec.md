# Frontend Implementation Spec (Claude Code)

**Stack:** Next.js 14 (App Router) · TypeScript · Tailwind · TanStack Query · PWA. Full architecture: /docs/05-frontend-architecture.md.

## Build order
1. Tokens pipeline (Style Dictionary → /tokens) + `components/ui` primitives (see /components/*.md).
2. App Router skeleton: root providers (Query, theme, session), route groups `(marketing)`/`(app)`/`(admin)`, AppShell.
3. API client + query-key factory + OpenAPI types + auth guard.
4. Instrument slice: public SSR/ISR stock page (proves SEO + tokens + four-state components).
5. App surfaces (dashboard, portfolio, watchlist, screener) with prefetch/hydrate.
6. AI slice (assistant SSE) + PWA (service worker, manifest, offline, persisted cache).
7. CI budgets (CWV, bundle, a11y) before scaling.

## Rules
- RSC by default; `"use client"` only for interactivity.
- Every data component ships loading/empty/error/success (lint-enforced).
- Tokens only — no raw hex/px (ESLint no-magic). Theme = class on <html>.
- Forms: react-hook-form + Zod. Charts: in-house SVG primitives (see /components/Chart.md).
