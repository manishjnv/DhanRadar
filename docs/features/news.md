# Feature — News Module

**Status:** B56-f4 built; merge-eligible, NOT deployed · **Phase:** B56-f4 ·
**Last updated:** 2026-06-12

## Purpose & scope

Stores and serves headline metadata for market-relevant news items. Article body or excerpt text is
**NEVER** stored or served — headline + attribution + canonical link only. This design keeps the
module within copyright safety bounds and the SEBI educational boundary simultaneously.

The module owns the `news` schema and a single table (`news.news_items`, Alembic migration `0016`).
It has three distinct ingestion paths (RSS primary, admin-curated static fallback, and the new admin
CRUD workflow added by B56-f4) plus one anonymous-read public endpoint.

## Non-goals

- Does not store or serve article body, excerpt, or summary text.
- Does not produce numeric scores, labels, or advisory signals.
- Does not write to any table outside `news.*`.

## Data model

Schema: `news` (schema-per-concern, non-neg #7). Table: `news.news_items`.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK; `gen_random_uuid()` server default |
| `scope` | `text` | Default `market`; used by the public GET filter |
| `category` | `text` | E.g. `mutual_funds`, `macro`, `regulation` |
| `title` | `text` | Headline only |
| `source` | `text` | Display publisher name (e.g. `RBI`, `SEBI`, `AMFI`) |
| `canonical_url` | `text` | UNIQUE; the real item URL (link-out only) |
| `published_at` | `timestamptz` | Source publication date |
| `provenance_source` | `text` | Feed URL for RSS; `admin_curated` for admin paths |
| `fetched_at` | `timestamptz` | When the row was last written by any ingestion path |
| `is_active` | `boolean` | Publication gate; default `true` for new inserts from ingestion |
| `created_at` | `timestamptz` | Immutable insert timestamp |
| `updated_at` | `timestamptz` | ORM-managed; set explicitly by all write paths |

Indexes: `ix_news_scope_pub (scope, published_at)`, `ix_news_active (is_active)`.

Source: `backend/dhanradar/models/news.py`. Migration: `backend/alembic/versions/0016_news_items.py`.

## Public surface

### `GET /api/v1/news`

Query params: `scope` (default `market`), `limit` (`1..50`, default `20`).

Anonymous-read (no auth required). Always returns `200` — empty-source degrades to `[]`, never 404.

Response: array of `NewsItem`:

`{title, source, url, published_at, category}`

Filters: `is_active=true` rows only; recency window `NEWS_MAX_AGE_DAYS` (default 30 days).
Ordered `published_at DESC`.

Staleness observability: if the newest served item is older than `NEWS_STALENESS_WARN_HOURS`, the
service logs a `WARNING` (`news.staleness`). This is an operator-visible signal that the RSS feed
may be stale or all ingest cycles failed; it does not affect the response.

## Ingestion paths

### 1. RSS primary (`news/rss.py`)

Fetches sanctioned feeds defined in the `_FEED_REGISTRY` source registry. Feeds evaluated for
redistribution acceptability:

- **RBI press releases** (`rbi.org.in/pressreleases_rss.xml`) — enabled; government institution;
  explicitly provides RSS for syndication.
- **RBI notifications** (`rbi.org.in/notifications_rss.xml`) — enabled; regulatory announcements.
- **SEBI** — disabled; URL 404 confirmed 2026-06-10.

Each feed entry may carry an MF-relevance keyword filter (`_MF_KEYWORDS` / `_MACRO_KEYWORDS`). Items
that match neither group are silently dropped. Each accepted item's canonical URL is HEAD-checked
before storage — dead links are skipped at ingest.

Dedup: `ON CONFLICT (canonical_url) DO UPDATE`. Provenance is set to the feed URL.

### 2. Admin-curated static seed fallback (`_CURATED_ITEMS` + `upsert_curated_news`)

Three hard-coded MF-relevant reference links (AMFI SIP data, AMFI AUM data, SEBI Master Circular).
Used as a belt-and-suspenders fallback when all RSS feeds return zero items. `published_at` is set
to `now()` on each upsert so curated items always pass the 30-day recency filter.

### 3. Admin CRUD (B56-f4)

See "Admin CRUD" section below.

The Celery beat task `dhanradar.tasks.news.refresh_market_news` runs both RSS and curated-seed paths
every 30 minutes (best-effort; failure never breaks reads).

## Admin CRUD (B56-f4)

Four endpoints under `/api/v1/admin/news`, all gated by `RequireAdmin()`. Non-admins (including
authenticated non-admins) receive `404` — surface-hiding, consistent with the B26 admin pattern.

### Endpoints

**`GET /api/v1/admin/news`** — list all items for admin review.

- No recency cutoff; includes drafts (`is_active=false`) and all provenance sources.
- Query params: `scope` (optional), `is_active` (optional bool filter), `limit` (1–100, default 50),
  `offset` (default 0).
- Response: `list[AdminNewsItem]` (full row including `id`, `provenance_source`, `is_active`,
  `created_at`, `updated_at`).

**`POST /api/v1/admin/news`** — create a news item as a draft.

- Body: `CreateNewsItemRequest` (`title`, `source`, `canonical_url`, `category`, `scope`,
  `published_at?`).
- **Always lands as `is_active=false`** (the reviewer gate; publishing is a deliberate separate
  step). `provenance_source` is always `admin_curated`.
- Conflict-guarded: same `canonical_url` → `409 news_url_exists`. Idempotency-Key is deferred
  (tracked as a B56-f4 residual, same class as B26/B30).
- Advisory-verb title screen applied before insert (see "Compliance" below).
- Returns `201 AdminNewsItem` on success.

**`PATCH /api/v1/admin/news/{id}`** — partial update.

- Accepts any subset of `{title, source, canonical_url, category, scope, published_at, is_active}`.
- `is_active=true` publishes a draft; `is_active=false` withdraws a live item.
- Explicit `null` on any field → `400 null_field` (all columns are NOT NULL; passing null would
  surface as an opaque 409 without this guard).
- Empty body (no fields set) → `400 no_fields_to_update`.
- `canonical_url` collision → `409 news_url_exists`.
- Advisory-verb title screen on any `title` update → `400 advisory_title_rejected`.
- String fields are stripped of surrounding whitespace at write.
- Malformed UUID `id` → `404` (surface-hiding).
- Missing item → `404 news_item_not_found`.

**`DELETE /api/v1/admin/news/{id}`** — hard delete.

- Returns `204 No Content`.
- Malformed UUID → `404`; missing item → `404 news_item_not_found`.

All mutating endpoints (`POST`, `PATCH`, `DELETE`) fire-and-forget an admin audit record via
`dhanradar.audit.service.record_admin_action` with actions `create_news_item`, `update_news_item`,
and `delete_news_item` respectively. Audit failure must not break the handler.

### Reviewer-gate invariant (critical)

> **Ingestion upserts (RSS and curated seed) deliberately do NOT include `is_active` in their
> `ON CONFLICT DO UPDATE set_` dictionaries.** Automation can refresh content fields
> (`title`, `source`, `scope`, `category`, `published_at`, `fetched_at`, `updated_at`) but
> **can never flip the publication state of an existing row**. An admin-drafted item stays a
> draft regardless of how many ingest cycles run; an admin-deactivated item stays withdrawn.
> Only admins change `is_active` (via PATCH).

New rows still insert with `is_active=True` via `.values()` — this applies only to the conflict
update path. Two unit tests (`test_rss_upsert_never_touches_is_active` and
`test_curated_upsert_never_touches_is_active`) pin this invariant.

## Compliance

**Advisory-verb title screen.** Both `create_news_item` and `update_news_item` apply `_ADVISORY_RE`
to admin-entered titles before any write:

Core verb set (word-bounded, case-insensitive): `strong_buy`, `strong_sell`, `buy`, `sell`, `hold`,
`switch`, `avoid`, `caution`.

This mirrors the screen in `mood/service.py`. A match → `ValueError("advisory_title_rejected")` →
router `400 advisory_title_rejected`.

**Known residual.** The regex is duplicated across `mood/service.py` and `news/service.py`. Tracked
as a shared-constants move under B56-f1.

**No numeric in DOM.** The public `GET /api/v1/news` response carries only
`{title, source, url, published_at, category}` — no score, weight, or numeric signal (non-neg #2).

**No advisory labels.** Public news items are factual informational metadata from sanctioned
regulatory sources (non-neg #1).

## Operations runbook

**Publish a new item:**

1. `POST /api/v1/admin/news` with `{title, source, canonical_url, category, scope}`. Item lands as
   draft (`is_active=false`).
2. Review the item at `/admin/news` (list endpoint; draft is visible).
3. `PATCH /api/v1/admin/news/{id}` with `{"is_active": true}` to publish.

**Withdraw a live item:**

`PATCH /api/v1/admin/news/{id}` with `{"is_active": false}`.

**Fix a typo:**

`PATCH /api/v1/admin/news/{id}` with `{"title": "corrected title"}`.

**Remove an item permanently:**

`DELETE /api/v1/admin/news/{id}`.

## Known residuals

- **`updated_at` DB trigger absent.** The `updated_at` column is managed by the ORM (`onupdate`)
  and by all ingestion paths (explicit `set_` in upserts). Raw SQL edits that bypass the ORM would
  leave `updated_at` stale. A DB-level `ON UPDATE` trigger is out of scope for this slice;
  documented here for future hardening.
- **`create_news_item` is audited; B26 `create_disclaimer` is not.** More audit coverage is safer;
  the asymmetry is noted for alignment in a future hardening pass.
- **Idempotency-Key on POST deferred.** Conflict-guard on `canonical_url` provides duplicate-submit
  safety without the header; the key itself is tracked as a B56-f4 residual (same class as B26/B30).

## Files

### Backend

| Path | Purpose |
|---|---|
| `backend/dhanradar/models/news.py` | ORM model (`news.news_items`) |
| `backend/alembic/versions/0016_news_items.py` | DDL: `news` schema, table, indexes |
| `backend/dhanradar/news/schemas.py` | Pydantic schemas: `NewsItem`, `AdminNewsItem`, `CreateNewsItemRequest`, `UpdateNewsItemRequest` |
| `backend/dhanradar/news/service.py` | List, upsert, RSS ingest, admin CRUD helpers, `_ADVISORY_RE` screen |
| `backend/dhanradar/news/rss.py` | Sanctioned RSS adapter: source registry, MF-relevance filter, HEAD-check, feed fetch |
| `backend/dhanradar/news/router.py` | Public `/news` endpoint (anonymous-read) |
| `backend/dhanradar/news/admin_router.py` | Admin CRUD endpoints (RequireAdmin-gated) |
| `backend/dhanradar/tasks/news.py` | Celery beat task: 30-min RSS + curated-seed refresh |
| `backend/dhanradar/main.py` | Router mounts for both `news_router` and `news_admin_router` |

### Tests

| Path | Scope |
|---|---|
| `backend/tests/unit/test_news_service.py` | Unit: curated upsert dedup, malformed skip, fetch-failure no-write, RSS conflict-non-flip invariant |
| `backend/tests/unit/test_news_admin_service.py` | Unit: create-draft defaults, advisory screen, empty/URL validation, null-field + unknown-field guards, strip-on-update, KeyError paths, admin list filters |
| `backend/tests/integration/test_news.py` | Integration: public endpoint happy/empty/scope/limit/param-validation + refresh-failure cached-read |
| `backend/tests/integration/test_news_admin.py` | Integration: RequireAdmin gate (404 anon + non-admin), CRUD round-trip, publish/withdraw flips, conflict 409, advisory 400, malformed-UUID 404s, delete 204 |

## Changelog

- 2026-06-10 — B56 news initial build: anonymous `GET /api/v1/news`, `news.news_items` model
  (migration `0016`), admin-curated seed fallback, 30-min Celery beat refresh. Landed as part of
  the B56 dashboard pass.
- 2026-06-10 — B56-f5: RSS primary ingestion live; RBI feeds sanctioned; SEBI disabled (URL 404);
  source registry with `enabled` flag; MF-relevance filter; HEAD-check per item; provenance stamped.
  Branch `fix/b56-live-news-rss`.
- 2026-06-12 — B56-f4: Admin CRUD added: 4 RequireAdmin-gated endpoints (`/api/v1/admin/news`);
  draft-create reviewer gate (`is_active=false` on POST); advisory-verb title screen; explicit-null
  PATCH guard; ingestion `ON CONFLICT DO UPDATE set_` hardened to exclude `is_active` (reviewer-gate
  non-clobber); admin audit on all mutations; 2 pinning unit tests for the is_active invariant.
  Branch `feat/b56-f4-news-admin-crud`. Ledger `reviews/b56-f4-news-admin-crud.md`.
