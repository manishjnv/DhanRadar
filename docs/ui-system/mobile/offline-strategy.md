# Offline Strategy

## Principle
Read-first offline: the app is **useful without signal** (view last-synced portfolio/watchlist/scores); writes queue and sync.

## Cache layers
| Data | Store | Policy |
|---|---|---|
| App shell / assets | service worker (PWA) / bundle (native) | precache; versioned |
| Instrument/score (recent) | local DB (IndexedDB / SQLite / Room/CoreData) | stale-while-revalidate; show "as of" |
| Portfolio/watchlist | local DB | last-synced snapshot; offline banner |
| AI answers | local cache | last answers viewable; new requires online |
| Queued mutations | outbox table | replay on reconnect |

## Sync engine
```
online → fetch fresh → update local + UI; flush outbox (queued adds/alerts) with idempotency keys
offline → serve local snapshot + "Offline — as of HH:MM" banner; queue writes to outbox
reconnect (Background Sync / WorkManager) → replay outbox → resolve conflicts → refresh
```

## Conflict resolution
- Mutations idempotent (server dedupes by idempotency_key). Last-writer-wins for preferences; server-authoritative for holdings/scores. Per-item status: synced / pending / failed (shown in UI).

## Freshness honesty
- Always show data age when offline/stale; never imply live. Scores/prices marked "as of" — consistent with the market-data confidence principle.

## Limits
- Cap local cache size (LRU eviction); encrypt sensitive local data (holdings) at rest; clear on logout.
