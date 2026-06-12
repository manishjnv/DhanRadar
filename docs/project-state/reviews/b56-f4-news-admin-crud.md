# Review — B56-f4 admin news CRUD

## Gate ledger

**Change-id:** b56-f4-news-admin-crud · **Date:** 2026-06-12 ·
**Branch:** `feat/b56-f4-news-admin-crud` · **Tier:** A (standard feature behind existing
`RequireAdmin`; no load-bearing path; no auth-code change; no migration).

**Artifacts:**

- `backend/dhanradar/news/admin_router.py` — new; 4 `RequireAdmin`-gated endpoints under
  `/api/v1/admin/news`.
- `backend/dhanradar/news/service.py` — Admin CRUD helpers appended (`create_news_item`,
  `update_news_item`, `delete_news_item`, `admin_list_news`, `_ADVISORY_RE`, `_validate_fields`,
  `_UPDATABLE_FIELDS`); ingestion upserts hardened (`is_active` removed from both
  `ON CONFLICT DO UPDATE set_` dicts).
- `backend/dhanradar/news/schemas.py` — `AdminNewsItem`, `CreateNewsItemRequest`,
  `UpdateNewsItemRequest` added.
- `backend/dhanradar/main.py` — `news_admin_router` mounted at `/api/v1`.
- `backend/tests/unit/test_news_admin_service.py` — new; unit coverage for admin CRUD helpers.
- `backend/tests/unit/test_news_service.py` — extended; 2 pinning tests for the `is_active`
  reviewer-gate non-clobber invariant.
- `backend/tests/integration/test_news_admin.py` — new; integration coverage for all 4 endpoints.

| Gate | Status |
|---|---|
| Unit suite (touched modules) | PASS |
| ruff (touched files) | PASS (2 pre-existing `main.py` findings on `HEAD`; lint advisory) |
| `ci_guards.py` | PASS |
| `anti_pattern_sweep.py` | PASS |
| Secrets scan (diff) | PASS |
| Architect review | REVISE → **ACCEPT** on independent re-review (all conditions verified) |
| **Merge-eligible** | yes (pending CI green on PR) |
| **Deploy-eligible** | needs Phase-7 §5 batched pre-deploy pass + human approval |

Final CI confirmation: GitHub Actions on the PR (no local Postgres; integration tests and the
Alembic migrations job run in CI only, per the standing `CI is the gate` memory entry).

## Tier classification

**Tier A.** The change sits entirely behind the existing `RequireAdmin()` gate, which was itself
reviewed at Tier B (B26). No auth code changed, no load-bearing path touched, no migration added.
Cross-dimension compliance is handled in-design (advisory-verb screen + unchanged public surface
shape). Full panel review (Security/Compliance/UI/Product) is deferred to the end-of-phase batched
audit per `AI_GOVERNANCE_MODEL.md §3.2`.

## Builder

Sonnet subagent. Opus corrections applied (reworked: Y):

- Explicit-null `PATCH` path was initially raising `409` via an unguarded `IntegrityError` path
  rather than the explicit `400 null_field` guard — service-level null check added before the ORM
  write.
- Service-level `_UPDATABLE_FIELDS` whitelist was absent; unknown keys reached `setattr` silently —
  whitelist + `ValueError("unknown_field")` added.
- `scope` was not validated for non-empty in the admin create/update paths — added to the
  `_validate_fields` call set (the public `list_news` path was untouched).
- String fields in `update_news_item` were not stripped before `setattr` (inconsistent with
  `create_news_item`) — `_STRING_FIELDS` set + conditional strip added.

## Architect review (independent Sonnet) — REVISE, then ACCEPT on re-review

10 findings; initial verdict REVISE. A second independent re-review verified every fix with
file:line evidence and returned **ACCEPT** (deferred items tracked in `BLOCKERS.md` are not
verdict conditions).

**BLOCKER #1 (FIXED):** Both ingestion upserts (`upsert_curated_news` and `fetch_and_upsert_rss_news`)
included `is_active` in their `ON CONFLICT DO UPDATE set_` dictionaries. This meant any ingest
cycle could flip `is_active=true` on an admin draft, bypassing the reviewer gate and publishing
unreviewed content. Fix: `is_active` removed from both `set_` dicts. New rows still insert with
`is_active=True` via `.values()` — this affects only the conflict-update path. Two pinning unit
tests added (`test_rss_upsert_never_touches_is_active`,
`test_curated_upsert_never_touches_is_active`).

**MAJOR #2 (FIXED):** `docs/features/news.md` was missing. Created this session.

**MAJOR #3 — `_ADVISORY_RE` duplication (DEFERRED):** the advisory regex is duplicated verbatim
across `mood/service.py` and `news/service.py`. Folded into the B56-f1 shared-constants move
(disclosure constants + advisory regex into a shared `compliance`/`shared` module). Non-blocking;
the screen is correct in both locations.

**MAJOR #4 (FIXED):** `TRUNCATE news.news_items` in the test fixtures was missing `CASCADE` — could
fail if a FK is added in future. `CASCADE` added.

**MAJOR #5 — `updated_at` staleness on non-ORM paths (PARTIALLY FIXED):** both ingestion upserts
now explicitly set `updated_at` in their `set_` dicts (in-lane fix). A DB-level `ON UPDATE` trigger
is out of scope; documented in the feature doc as a known residual.

**MINOR #6 — `create_news_item` audit vs B26:** `create_disclaimer` in B26 is not audited while
`create_news_item` is. More audit coverage is safer; the asymmetry is noted in the feature doc for
a future hardening pass. No action taken (keeping the audit is the right call).

**MINOR #7 (FIXED):** DELETE was untested against a malformed UUID. A malformed-UUID DELETE → 404
assertion was added to the integration lifecycle test.

**MINOR #8 (FIXED):** No test exercised the publish/withdraw `is_active` flip lifecycle via PATCH.
Publish → withdraw (gone from public `/news`) → re-publish steps added to
`test_news_admin_full_lifecycle`.

**NITs #9/#10:** subsumed into existing findings above.

## Final status

**ACCEPT (independent re-review).** All blocking conditions resolved in-session and independently
verified. Two deferred items tracked
in `BLOCKERS.md` (B56-f1: advisory-regex shared constants; B56-f4 residual: Idempotency-Key on
POST). Merge-eligible; not deploy-eligible until the Phase-7 §5 batched pre-deploy pass clears and
the founder approves.

Sign-off: pending human (founder) merge approval.
