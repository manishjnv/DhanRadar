# Review ledger — B44 DPDP consent grant/revoke writer + capture UI

- **Change-id:** b44-consent-writer
- **Date:** 2026-06-08
- **Branch:** `hardening/launch-gate-blockers` (PR #28, draft)
- **Commits:** `927f64f` (backend writer + audit log), `4b40f83` (frontend capture UI), `725e3eb` (B42, separate slice — own ledger not required, Tier-A)
- **Governance tier:** **Tier-B** (load-bearing DPDP/consent path). Required reviews: Builder + Architect + **Security** + **Compliance**. Inline in-session (load-bearing exception — not deferred to the phase audit).

## What landed

The fail-closed `RequireConsent` gate (B3) existed but had **no writer** — so consent could never be captured and every consent-gated route (MF upload, AI, cross-border notify) was permanently blocked. This change adds the writer + the capture UI.

- **Backend** (`backend/dhanradar/consent/`): `POST /api/v1/consent/grant`, `POST /api/v1/consent/revoke`, `GET /api/v1/consent`. Authed; anonymous → 401 in-body first (no `RequireTier`, avoids the 402-before-401 leak). Per-purpose atomic `jsonb_set` (no sibling clobber / lost update). Single commit (all-or-nothing) with one `consent.consent_audit_log` row per purpose. Action-scoped `Idempotency-Key` (Redis `SET NX`). New `consent` schema + append-only audit table (migration `0010`, no FK so it survives DPDP erasure, `action` CHECK in DDL **and** ORM).
- **Write format** matches the reader (`deps._consent_granted`): `{"granted": bool, "ts", "version"}`. **Revoke writes `granted: false`** — never a separate `revoked` key (the reader ignores `revoked` → would fail OPEN; deps.py revoke contract).
- **Frontend** (`frontend/src/features/consent/`): point-of-use `ConsentModal` (gates MF upload on `mf_analytics`) + a `settings/privacy` panel managing all 7 canonical purposes. Educational copy only.

## Builder + Architect

Builder = Sonnet drafts (backend writer; FE core) + Opus completion of the FE remainder (upload wiring, settings panel, tests). Architect = Opus line-by-line diff review. **Opus review caught and fixed a real fail-open before any commit:** the Idempotency-Key Redis namespace was shared across grant+revoke, so a key reused for a grant then a revoke would have had the **revoke silently skipped** (consent stays granted, caller gets 200). Fixed by scoping the key per action (`consent:idem:{grant|revoke}:{uid}:{key}`) + regression test (g2). Also fixed a string-literal syntax error in the FE purpose copy (unescaped apostrophe) before it reached a gate.

## Security — **ACCEPT-WITH-CONDITIONS** (all conditions applied in-session)

Codex was unavailable (ChatGPT-account entitlement error on every model). Per the sanctioned fallback ladder, an **independent Sonnet adversarial takeover** ran with a self-contained threat-model prompt (authenticated-user attacker; goal = fail-open / cross-user / format-disagreement / 500 / audit-skip). Verdict **ACCEPT-WITH-CONDITIONS**, 3 findings — all applied this session:

1. **(med) 0-row UPDATE wrote a false audit row** when the user row was deleted mid-session (DPDP-erasure race) — the `UPDATE … WHERE id=uid` matched 0 rows but the audit row still committed. Fix: check `result.rowcount`; on 0 → `rollback()` + 401 `user_not_found` (matches `/auth/me`). Regression test (j).
2. **(low) ORM lacked the `action` CheckConstraint** the migration DDL had → `create_all()` test schemas would skip it. Fix: added `CheckConstraint("action IN ('grant','revoke')")` to the model.
3. **(low) Redis outage on the idempotency path → unhandled 500**, denying consent capture during a cache blip. Fix: catch `RedisError`, degrade gracefully (proceed with the write; consent state is idempotent on the column, only replay-dedup is lost).

Vector-by-vector the reviewer confirmed CLEAN: revoke fail-open, jsonb_set sibling clobber, cross-user write (user_id is JWT-only), reader/writer format agreement, audit completeness, await-on-sync misuse.

## Compliance (Opus) — **ACCEPT**

- **Non-neg #1 (no advisory verbs):** consent copy + audit `action` values (`grant`/`revoke`) carry no advisory vocabulary; `ci_guards.py` advisory sweep exit 0 over the new files.
- **Non-neg #2 (no numeric in DOM):** the consent UI renders disclosure prose + toggles only; no score/band numerics.
- **Non-neg #5 (auth):** cookie-only; no bearer; anonymous → 401.
- **Non-neg #6 (`/api/v1`, RFC7807, Idempotency-Key on mutating routes):** all satisfied.
- **Non-neg #7 (module isolation):** the consent module writes only `auth.users.dpdp_consents` (sanctioned — the model designates the Consent module as the manager of those columns) + its own `consent` schema; no cross-module JOIN/INSERT.
- **Non-neg #10 (DPDP consent):** this **is** the capture mechanism; per-purpose grants (no bundling, ADR-0024), append-only audit trail, version-stamped (`DPDP_CONSENT_VERSION`).

## Deterministic gates (all green)

- Backend: ruff (new files clean; pre-existing repo findings only — advisory per B40-followup), `alembic heads` = single `0010`, `ci_guards.py` + `anti_pattern_sweep.py` exit 0, **34 unit pass**, **14 integration collect** (run in CI — no local Postgres, B1).
- Frontend: `tsc --noEmit` 0 errors, `npm run lint` clean, **vitest 37/37 pass**, `check:tokens` in sync.

## Status

**Merge-eligible** (gates green + Tier-B reviews pass + conditions applied). **NOT deploy-eligible** until **B48** is re-enforced at launch (`DPDP_CONSENT_ENFORCED=true` / `ENV=production`) so a real grant is required, and the Phase-7 §5 pre-deploy gate clears. No merge/deploy performed this session (human-gated).
