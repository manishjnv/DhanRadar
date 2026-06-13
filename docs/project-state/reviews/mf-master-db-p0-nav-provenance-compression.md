# Review ledger — MF master-data platform P0: NAV provenance + compression

Change-id: `mf-master-db-p0-nav-provenance-compression`
Date: 2026-06-13
Builder: Claude (Fable 5, main session)
Scope: harden the existing `mf.mf_nav_history` master NAV store — add ingestion
provenance + enable TimescaleDB native columnar compression. Part of the
"local MF master DB" P0 (foundation) work. Does **not** add any new data source.

## What changed

- `backend/alembic/versions/0019_mf_nav_ingested_at.py` — add `ingested_at`
  (timestamptz, nullable, no column-default → existing ~2M backfilled rows stay
  honestly NULL) then `SET DEFAULT now()` for future rows. Satisfies the
  data-platform six-question provenance ("when received").
- `backend/alembic/versions/0020_mf_nav_compression.py` — native columnar
  compression (`segmentby=isin`, `orderby=nav_date DESC`, `compress_after=5 years`),
  guarded on the timescaledb extension, transaction-atomic.
- `backend/dhanradar/models/mf.py` — `MfNavHistory.ingested_at` column.
- `backend/dhanradar/tasks/mf.py` — daily + backfill upsert `set_` now stamps
  `ingested_at = func.now()` on conflict (last-ingested semantics); pure mapping
  helpers still exclude it (server-side stamp only — no client clock in provenance).
- Tests: provenance contract unit tests (`tests/unit/test_nav_ingestion.py`) +
  server-default integration test (`tests/integration/test_mf_nav_scoring.py`).

## Tier classification

Load-bearing path (Alembic migrations + the NAV ingestion path that feeds scoring).
Per the overlay, full inline adversarial review is required **in the same session it
lands** — not deferred to the phase audit. Not Tier-C (no scoring-logic change) and
not Tier-B (no auth/billing/AI surface); reviewed as a data-platform/infra change
with Security + Architect lenses.

## Deterministic gates

- ruff: only pre-existing house-style advisories (`Optional[...]`, `Union[...]`),
  no new error categories introduced; CI ruff is advisory/continue-on-error.
- pytest (DB-free): `tests/unit/test_nav_ingestion.py` 28 passed (incl. 2 new
  provenance tests); related suites `test_mf_module` / `test_celery_task_registration`
  / `test_market_data` 50 passed.
- alembic: single linear head `0020`; chain `0018→0019→0020`.
- secrets scan + anti-pattern/IGNORE-list grep on the diff: clean.
- Migration-apply + integration tests run in CI (no local Postgres) — the gate of
  record; verified `gh pr checks` before merge.

## Adversarial review (Security + Architect) — Sonnet takeover

codex:rescue is unavailable on this account → Sonnet adversarial takeover (per the
approved fallback). Verdict: **ACCEPT-WITH-CONDITIONS**, 2 blockers.

1. **Backfill-into-compressed (blocker).** `ON CONFLICT DO UPDATE` into a compressed
   chunk hard-errors on TimescaleDB 2.x (auto-decompress covers plain INSERT only).
   At the original `compress_after=365 days`, already-backfilled 1–3yr data would
   compress and a re-run of `nav_backfill(years=3)` would error.
   **Resolved:** horizon moved to **5 years** — nothing inside 5y ever compresses,
   so every routine backfill (default 3y, safe to 5y) and the daily current-day
   write stay in uncompressed chunks. Compression acts only on the deep >5y tail
   (where the win matters); deep re-backfills decompress first (documented).
2. **Partial-apply non-re-runnability (blocker).** The `COMMIT`-first pattern (copied
   from the continuous-aggregate migration) meant a failure after COMMIT left
   compression enabled with no policy, and re-running upgrade errored on the
   already-enabled `ALTER`.
   **Resolved:** removed the `COMMIT` — compression DDL + `add_compression_policy`
   are transaction-safe (unlike `CREATE MATERIALIZED VIEW WITH (continuous)`), so the
   migration is now atomic: a failed apply rolls back fully and re-runs cleanly.

Nits (no change required): integration test re-fetches with a fresh SELECT after
commit, so it observes the server default without `db.refresh()`.

## Status

- [x] Deterministic gates green (local; CI is the gate of record)
- [x] Adversarial review ACCEPT-WITH-CONDITIONS → both conditions resolved in 0020
- [ ] CI green on PR (pending)
- [ ] Deploy gate: separate human approval + `alembic upgrade head` on KVM4 +
      verify TS `extversion` and `compression_enabled` (pending)

Merge-eligible once CI is green. Deploy-eligible per the standing KVM4 gate.
