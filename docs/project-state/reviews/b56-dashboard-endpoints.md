# Review — B56 dashboard backend endpoints (broken home screen fixed)

**Change-id:** b56-dashboard-endpoints
**Date:** 2026-06-09
**Branch:** `feat/b56-dashboard-endpoints`
**Tier:** A (standard feature) + Compliance check (surfaces MF labels). Not load-bearing
(the only infra touch is a 2-line `main.py` router mount).
**Decision driver:** B56 — the post-login home screen's four widgets called backend
endpoints that did not exist (404; MSW-mock-only). Build the real backend, wire the FE.

## What changed

- NEW `backend/dhanradar/dashboard/` (`schemas.py`, `service.py`, `indices.py`, `router.py`)
  — router mounted at `/api/v1` in `main.py`. Reads ONLY the `mf` schema + shared
  Yahoo/Redis; no scoring-engine/billing reach-in; no writes; no migration.
  - `GET /portfolio/summary` — authed; richer rollup (`current_value`/`xirr_pct` =
    user's own money, `fund_count`, `last_updated`, per-fund `funds[]` label+band,
    disclosure bundle). **RFC7807 404** on cold-start (no portfolio/holdings).
  - `GET /indices` — authed; reuses the Yahoo provider helpers (NSE geo-blocked on
    KVM4), Redis-cached 60s; degrades to `[]` on a Yahoo outage.
  - `GET /instruments/top-scored?type=fund` — authed; read-only consumer of persisted
    `mf.user_fund_scores`, USER-SCOPED, label+band only, ranked by label severity, in a
    disclosure envelope. `type!=fund` → 200 empty.
  - `/news` DEFERRED (no source).
- FE: extended `PortfolioSummary` type + `TopScoredResponse` envelope; the summary and
  top-scored widgets render `LabelChip` + `DisclosureBundle`+NOT_ADVICE; MSW updated to
  the real shapes (dev-only); vitest specs for the contract shapes.
- Tests: `tests/unit/test_dashboard.py` (indices/ranking/no-numeric, 9) +
  `tests/integration/test_dashboard.py` (3 endpoints, happy+guard+no-leak, 8).

The public payload is label + confidence band only — `mf.user_fund_scores.unified_score`
is never SELECTed into a payload (explicit allowlist Pydantic models, never expose-all).

## Deterministic gates

ruff clean (touched files); **566 backend unit pass + 1 xfail**; `ci_guards.py`
(anti-pattern + secrets) pass; FE `tsc --noEmit` clean, eslint clean, **70 vitest pass**;
8 integration tests collect (run on CI Postgres). mypy advisory in CI.

## Tier-A review panel (independent agents)

### Compliance (Opus) — ACCEPT-WITH-CONDITIONS → **condition fixed inline**

PASS on no-numeric-leak (verified: `unified_score` in no SELECT, explicit allowlist
schemas, integration test seeds a real `unified_score` then asserts it is absent from the
body), no advisory verbs, user-scoped top-scored (not a platform leaderboard — inside the
educational boundary), cookie-only auth.

- **Concern 1 (BLOCKER-class, FIXED):** the top-scored label table rendered with NO
  adjacent disclosure — the generic AppShell footer disclaimer is not version-tied and is
  insufficient per non-neg #9 (and the codebase's own `DisclosureBundle` rule). **Fix
  landed inline:** `/instruments/top-scored` now returns a `TopScoredResponse` envelope
  carrying `disclosure`/`not_advice`/`disclaimer_version` (same constants as portfolio
  summary + mood), and the widget renders `<DisclosureBundle>` adjacent to the table.
  Verified: BE payload + FE render (`page.tsx:144`) + integration assertion.

### Architect (Sonnet) — ACCEPT-WITH-CONDITIONS

Module isolation PASS (mf schema only, no cross-module JOIN/INSERT, no scoring recompute,
zero writes); router paths don't collide (mf router is under `/mf`); dedup ORDER BY
correct; 401 is RFC7807 (the global `http_exception_handler` wraps all `HTTPException`).

- **#6 (FIXED inline):** `max(...).isoformat()` could 500 on a null `scored_at` — guarded
  (falls back to snapshot date / None).
- **#1 → B56-f1 (DEFERRED):** disclosure constants imported from `scoring/engine/schemas`;
  move to a shared module. Blocked — the move edits `scoring/engine/*` (concurrent-session
  lane); coordinate. (mood already imports them the same way — existing pattern.)
- **#2 → B56-f2 (DEFERRED):** promote the reused `_quote_meta`/`_signal_value` Yahoo
  helpers to a public interface instead of importing privates.
- **#3 → B56-f3 (DEFERRED):** composite index `(user_id, isin, scored_at DESC)` +
  migration before real load; optional `asyncio.gather` for the 4 Yahoo fetches.
- #4/#5/#7 informational — no action (#5 confirmed RFC7807).

## Ledger

| Gate | Status |
|---|---|
| Deterministic (unit · ruff · ci_guards · FE tsc/eslint/vitest) | ✅ green |
| Compliance (Opus) | ✅ ACCEPT — condition 1 fixed inline |
| Architect | ✅ ACCEPT-WITH-CONDITIONS — #6 fixed; f1–f3 logged |
| **Merge-eligible** | ✅ yes (pending CI green on PR) |
| **Deploy-eligible** | needs the Phase-7 §5 batched pre-deploy pass + human approval |

Deferred follow-ups B56-f1..f3 in `BLOCKERS.md`; none merge-blocking, all latent/perf or
lane-coordination. **Lane honored:** no edits to `scoring/engine/*`, `mf/signals.py`,
`mf/scoring_bridge.py` (concurrent B58 session).
