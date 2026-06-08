# Phase-7 §5 Pre-Deploy Governance Panel — DhanRadar

- **Change-id:** `phase7-predeploy-panel`
- **Branch:** `hardening/launch-gate-blockers` (PR #28 → main)
- **Date:** 2026-06-08
- **Scope:** the full launch candidate after merging `origin/main` (PRs #22–27) into the branch —
  the batched, deferred end-of-phase audit (AI_GOVERNANCE_MODEL §3.2 / §5).
- **Reviewers:** independent agents, none the builder. Security = Sonnet takeover (codex:rescue
  unavailable — ChatGPT-account entitlement); Compliance = independent Opus; UI = Sonnet; Product =
  Sonnet.

## Overall gate result

| Reviewer | Verdict | Deploy-blocker? |
|---|---|---|
| Security | ACCEPT-WITH-CONDITIONS | **No** |
| Compliance | ACCEPT-WITH-CONDITIONS | **No** |
| UI | ACCEPT-WITH-CONDITIONS | No |
| Product (MVP) | ACCEPT-WITH-CONDITIONS | 3 launch-blockers — **2 operational, 1 code (now fixed)** |

**Formal deploy-gate condition (CLAUDE.md): no open Security/Compliance BLOCKER → SATISFIED.**
No reviewer returned REJECT. The ledger is **MERGE-eligible**. It is **NOT deploy-eligible** until
the operational punch-list closes + separate explicit human approval (production env is main-gated).

## Disposition of findings

### Fixed in this gate (`2033b9a`)

- **Product F3 (code, blocker-for-MVP):** `GET /market/why-today` returned 404 when no snapshot
  exists — inconsistent with `/mood`'s structured 200. Fixed → `why_today_unavailable()` 200 body;
  test added.
- **UI F3 (code):** AppShell "Settings" linked to non-existent `/settings/notifications` → fixed to
  `/settings/privacy`.

### Should-fix — punch-listed (pre-launch, code; not deploy-blocking)

- **Security F2:** `ratelimit.py` check-then-INCR TOCTOU allows ~1 request past the cap under
  concurrency (login brute-force guard). Fix: atomic INCR-then-compare. *Load-bearing security
  primitive — fix + re-run an adversarial pass in a dedicated session, do not rush in the gate.*
- **Security F1:** add a regression test asserting the B48 boot guard raises on
  `ENV=production` + `DPDP_CONSENT_ENFORCED=false`.
- **Security F3:** confirm `channels.deliver_telegram` sends only the intended part with
  `parse_mode=HTML`; `_esc` already escapes, verify no double-path.
- **Compliance F1:** label-change delivery writes one audit row per channel (telegram+email) with
  `model=None` — inflates churn-review universe. Dedup per (user,isin,day) or document as intended.
- **UI F1/F2:** `ScoreRing.tsx` + `AllocationDonut.tsx` use hardcoded brand hex instead of `--dr-*`
  tokens (correct colours, wrong source — a token-discipline polish item, NOT a numeric/advisory
  violation). Convert to `var(--dr-*)`.
- **Product F4 (code):** empty-portfolio CAS (valid PDF, zero active holdings) runs to a silent
  `status=done` with `funds=[]`. Guard in `_run_pipeline` → `empty_portfolio` state + FE message.
- **Product F8:** `docs/ui-system/contracts/*` (B41) carry advisory verbs + numeric + bearer with no
  deprecation banner — misbuild risk. Add the one-line DEPRECATED header.
- **Product F9:** `GET /market/mood/embed` is uncached — add `Cache-Control: public, max-age=300`.

### Nits — logged

Security F4/F5 (template structural nit; pre-enqueue consent pre-check), Compliance F2/F4
(Idempotency-Key dedup on `POST /mf/portfolios`; advisory-taxonomy expansion sign-off),
UI F5/F6 (mood disclosure null-guard; redundant `aria-hidden`), Product F10/F11.

### Operational launch-blockers (infra/human — the deploy punch-list, NOT code)

- **Product F1 / B29:** NAV data unpopulated → every fund `insufficient_data` until the operator
  runs `nav_backfill(years=3)` + a `nav_daily_fetch` on the live TimescaleDB. **The wedge cannot
  produce labelled reports without this.**
- **Product F2 / B48:** re-enforce DPDP consent — set `ENV=production` AND
  `DPDP_CONSENT_ENFORCED=true` (or delete the dev line); verify a gated route 403s without a grant.
  Legal blocker; the boot guard fails closed if `ENV=production`.
- **Product F5/F6:** admin module inert until `ADMIN_USER_IDS` is seeded (≥2 operator UUIDs) and the
  scoring engine v1 is activated via the two-person gate (else all reports stay `provisional_model`).
- **Product F7:** AI commentary is inert until `cross_border_ai` is grantable in the UI + a live
  `OPENROUTER_API_KEY`; verify the privacy settings expose the `cross_border_ai` grant end-to-end.

## Evidence (clean areas confirmed by the panel)

Auth (RS256 `__Host-` cookies, atomic GETDEL refresh rotation, no bearer), IDOR (own-resource
filters + 404), tier-gate 402 + portfolio cap, the four DPDP gates (B20/B31/B48 fail-closed + boot
guard), no hardcoded secrets, AI budget governor (atomic), Razorpay verify-before-parse + dedup +
B7/B8 503 inert, parameterized ORM (no f-string SQL), notification `_esc` escaping, the merge seams
(CompletionResult/model_used, the four-gate commentary order). Compliance: all 10 non-negotiables
hold on every shipping surface; the surviving merged AI-commentary implementation
(`surface="mf_commentary"`) is clean (no advisory/numeric leak). Scoring↔risk separation test
passes. UI: no numeric score in any component DOM; disclosure rendered on every label/AI surface.

## Status

The governance **panel passed** (no Security/Compliance blocker) and the two panel code findings
were fixed. **However the branch is NOT merge-ready: GitHub CI is RED** — the panel's "merge-eligible"
read was based on LOCAL unit tests; the CI integration suite + migrations job (the real gate, with a
live Postgres) fail. Merge-blockers: **B54** (`test_consent_writer` `jsonb_set`, B44 bug — needs a
live DB), **B55** (`migrations` `pg_partman` CI-image drift), and the `lint` advisory backlog
(B40-followup). The 3 `test_notifications` RequireTier regressions are FIXED (`ee059db`). PR #28 is
back to **draft** until CI is green. See SESSION_STATE "CI status" for the authoritative state.
**Deploy remains human-gated** regardless — the operational punch-list + parked infra gates
(B25/B34/B36/B37/B38/B40-followup) must close and a human must explicitly approve the KVM4 deploy.
