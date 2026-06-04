# State Management

Five owners: server cache → TanStack Query; URL state → searchParams; global UI → Zustand; forms → RHF+Zod; ephemeral → useState. Query-key factory hierarchical+typed. Optimistic updates for watchlist/alerts. SSE channel invalidates score/alert queries. Persist query client to IndexedDB for offline (PWA). Full: /docs/05-frontend-architecture.md §2–3.
