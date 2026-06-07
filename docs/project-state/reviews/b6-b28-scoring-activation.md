# Review — B6/B28 two-person scoring-engine activation gate

## Gate ledger

**Tier:** C (scoring/recommendation logic + writes a compliance audit table) · **Class:** major
(a regulated control — an unvalidated/unsigned scoring model must never be treated as authoritative) ·
**Branch:** `hardening/launch-gate-blockers` · **Date:** 2026-06-07.

**Decision (user-selected):** Admin endpoint + DB registry (ADR-0026). The
`compliance.rating_engine_changelog` table is the authoritative runtime activation state; activation
is triggered by `POST /api/v1/admin/scoring/{model_version}/activate` (the admin = `approved_by`).

**Artifacts:**

- `backend/dhanradar/scoring/engine/activation.py` (new) — `assert_activatable` (pure gate),
  `is_activated` (registry read, positive-memoized), `activate_model_version` (gate → dup-guard →
  changelog write, `IntegrityError` → `AlreadyActivatedError`).
- `backend/dhanradar/scoring/engine/config.py` — `EngineConfig` gains `created_by`/`methodology_url`
  (read from `ranking_configs_v1.json`) + a `validate()` guard rejecting a UUID-shaped `created_by`.
- `backend/dhanradar/compliance/service.py` — `is_engine_version_activated` registry reader.
- `backend/dhanradar/admin/router.py` + `schemas.py` — `POST /admin/scoring/{v}/activate` +
  `GET /admin/scoring/{v}/status`, both `RequireAdmin()`.
- `backend/dhanradar/models/compliance.py` — `uq_engine_changelog_activated_per_version` partial-unique
  index on `RatingEngineChangelog`.
- `backend/alembic/versions/0009_engine_activation_unique.py` (new) — the index DDL.
- `backend/tests/unit/test_scoring_activation.py` (7), `backend/tests/integration/test_admin.py`
  (+7 scoring tests).

| Gate | Required | Verdict | Reviewer/tier |
|---|---|---|---|
| Deterministic (pytest unit + ci_guards + py_compile) | always | PASS (18 unit; 17 integration collect; ci_guards 0; compile 0) | machine |
| Architect | always | self-note (interface-only coupling; sync hot path untouched; reuses governance) | orchestrator (Opus) |
| Compliance | tier C | ACCEPT (no advisory/numeric leak; activation record append-only + reproducible; allowlist intact) | orchestrator (Opus) |
| Product | tier C | ACCEPT (activation is admin-triggered, runtime, no redeploy; v1 stays provisional until backtest) | orchestrator (Opus) |
| Security (adversarial) | tier C | **ACCEPT-WITH-CONDITIONS** (8 vectors; 3 conditions — all applied in-session) | Sonnet takeover (codex n/a) |

## Design

- **Two-step gate (fail-early):** `backtest_passed` must be asserted (the §8 pass-gates) → else 422;
  then the two-person methodology gate `approved_by != created_by` (reuses
  `governance.two_person_gate_ok`) → else 409. Admin UUID is `approved_by`; the authoring role
  (`"architecture-review"`) is `created_by`.
- **Registry-authoritative:** a version is activated iff a `rating_engine_changelog` row exists with
  `activated=True`. The engine's sync `score()` keeps reading the JSON `cfg.activated` file flag (the
  "no DB session" fallback, unchanged); surfaces with a DB session use
  `activation.is_activated(db, version)`. `GET /status` reports `file_activated`, `registry_activated`,
  `effective_activated` (file OR registry), and `provisional` (= NOT registry_activated — the GATE,
  not the file flag, governs the provisional determination).
- **Module isolation:** scoring calls only `compliance.service` functions (the changelog is
  compliance-owned); the compliance ORM model is never imported into scoring.
- **v1 stays provisional:** no backtest has run, so v1 is not activated — the mechanism is built and
  ready; actual v1 activation is a data/human gate (real §8 backtest + a human approver admin).

## Security (independent, adversarial — Sonnet takeover; codex unavailable) — ACCEPT-WITH-CONDITIONS

8-vector review (two-person bypass; backtest bypass; double-activation TOCTOU; monotonic-cache
correctness; registry-vs-file authority; model_version spoofing; module isolation; compliance/audit
integrity). **No two-person/backtest bypass, no spoofing, isolation clean, activation record
append-only + reproducible.** Conditions, **all applied this session before commit**:

1. **Two-person gate triviality** — `created_by` is a static role string; a UUID-shaped value would
   weaken the gate. → `EngineConfig.validate()` now rejects a UUID-shaped `created_by`
   (`config.py`); unit tests for reject + accept.
2. **Double-activation TOCTOU** — the SELECT-then-INSERT dup-guard races under multi-worker, risking
   two `activated=True` rows for one version (an ambiguous regulatory record). → added the
   `uq_engine_changelog_activated_per_version` partial-unique index (migration 0009 + ORM), and
   `activate_model_version` maps the losing `IntegrityError` → `AlreadyActivatedError` → 409;
   integration test proves the index rejects a second activated row.
3. **`provisional` misrepresentation** — `provisional = not effective` (file OR registry) would read
   a manual file-flip (no gate) as non-provisional. → `provisional = not registry_activated`
   (`router.py`); integration test asserts provisional=True before any registry activation.

Advisories (logged, not code now): `factors_before` is `{}` (correct for the v1 first activation; a
future v2 activation must capture the prior activated version's weights); `methodology_url` body
override is not URL-format-validated (admin-only, trusted config fallback).

## Final status

**ACCEPT** (all conditions applied in-session). Merge-eligible; not deploy-eligible. **B6/B28
mechanism is BUILT** — what remains is the production activation of v1, a data/human gate (real §8
backtest pass-gates + a human approver admin), not further code.
