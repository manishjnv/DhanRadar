# DhanRadar — Project Progress Audit (2026-06-09)

**Auditor:** DhanRadar-Project-Progress-Auditor (evidence-based; computed fresh, no inflation).
**Method:** planned scope ingested from `SESSION_STATE.md` + `BLOCKERS.md`; reality verified by
reading code/tests/CI/live site across 11 areas (6 parallel evidence agents). Every number cites
its evidence. Classifications round **down** under uncertainty. This is a snapshot of `main` HEAD
`0290feb`; re-run fresh next time — do not trust this number later.

## Honest headline

The platform is **deployed and live**, but it is **not yet a true MVP** — its core differentiator
currently produces degenerate output.

- **Labels do not differentiate.** Every fund a user uploads scores **`on_track` or
  `insufficient_data` and nothing else.** The category-relative label signals
  (`outperform_1y/3y`, `underperform_12m`) are hardcoded `False` because no cohort-benchmark query
  exists yet, so the rule table can never emit `in_form`, `off_track`, or `out_of_form`
  (`backend/dhanradar/scoring/engine/signals.py:26-27`; `scoring/engine/labels.py:22-41`). The
  pitch is "explainable, differentiated labels" — the labels presently carry no discriminating
  information. Filed as **B58**.
- **The home dashboard is broken in production.** All four widgets call backend endpoints that do
  not exist — `/indices`, `/instruments/top-scored`, `/news`, `/portfolio/summary` (zero backend
  routers; `frontend/src/features/dashboard/api.ts:47-71`). It renders four error cards. (B56, open.)
- The skeleton is strong and real; the plumbing works end-to-end. "All dev COMPLETE / wedge
  functional / Plus set done" (SESSION_STATE) is **drift**: the code exists and runs, but the value
  it produces is currently inert.

**Live site verified this session:** `https://dhanradar.com` → 200; `/api/v1/health` →
`{db:ok, redis:ok}`; `/api/v1/market/mood` → 200. CI green on `main` (last 5 runs `success`).

## Real completion: ~65% (computed, rounded down from ~69%)

Computed from the fixed model (functionality, never task counts):

| Dimension | Weight | Score | Evidence |
|---|---|---|---|
| Feature | 40% | 68% | Most modules real + wired (12 routers, `main.py:110-124`); core labels degenerate, dashboard broken, mood always degraded |
| Integration | 20% | 75% | FE↔BE wired for auth/MF/consent/mood/onboarding; dashboard 4-endpoint gap (B56) |
| Testing | 15% | 70% | 683 backend tests, blocking CI green; FE ~57 vitest (thin); e2e written-but-never-run |
| Documentation | 10% | 80% | 28 ADRs + RCA log + feature docs; no feature doc for billing/subscriptions/onboarding/admin/audit |
| Deployment | 10% | 65% | Live + scripts exist; backup/rollback never run live; R2 residency + NAV populate unconfirmed |
| Monitoring/Ops | 5% | 35% | Sentry hook + `/metrics` exist but no DSN, no scrape/alerts/dashboards |

**Weighted ≈ 69% → reported 65%** (rounded down: the two highest-value surfaces — differentiated
labels + dashboard — are not delivering, which the dimension scores partly mask).

## MVP-ready? **NO** (binary gate — any failed core item fails it)

Failing core items:

- **Analytics output** — labels degenerate (B58); engine is `activated:false` so every result is
  tagged `provisional_model` (`ranking_configs_v1.json`; `engine.py:122`).
- **Home dashboard** — 4/4 widgets 404 (B56).
- **Data quality** — live NAV backfill not confirmed run (B29); mood runs in `degraded` mode (only
  6 of 11 signals have a working provider; NSE geo-blocked from the VPS) (`mood/compute.py:103`;
  `market_data/providers/yahoo.py`).
- **Monitoring** — no alerting wired (B38).

Passing: auth, CAS import, signup→onboarding→upload→report journey, error handling (RFC7807 + CAS
error card), AI commentary path, consent.

## Launch-ready? **NO** (~60% of the launch checklist)

Open launch blockers (cited in `BLOCKERS.md`, verified in code):

- Scoring activation pending two-person gate + backtest (B6/B28) — results stay provisional.
- Live NAV populate on TimescaleDB (B29) — code present, run unconfirmed.
- Monitoring scrape/alerts not wired; `SENTRY_DSN` unset (B38).
- Backups + rollback never exercised live; R2 India-residency unverified (B37/B34).
- Billing needs real Razorpay plan seeding (data-only — code fail-safes correct: unseeded plan →
  503, unmapped plan → free; `billing/service.py:114`; `subscriptions/service.py:44-78`).

## Solidly built (COMPLETE — evidence-backed)

- **Auth** — RS256 JWT in `__Host-` HttpOnly cookies, no bearer auth, atomic-GETDEL refresh-reuse
  detection (`auth/security.py:62`; `auth/service.py:219-236`).
- **MF CAS pipeline** — upload→parse→XIRR/allocation/overlap→rating bridge→no-numeric report +
  disclosure; dedup with report-cache check (`tasks/mf.py:161`). Wired end-to-end; only the label
  *signals* are thin (B58).
- **AI gateway + consumer** — all 4 gates wired (consent-before-payload, audit, `<0.30` floor,
  advisory reject) (`mf/commentary.py:206/254/274`).
- **Consent** — fail-closed gate + writer + UI + boot-guard that crashes if disabled outside dev
  (`deps.py:287`; `config.py:254`).
- **Onboarding, Notifications, Admin, Compliance-audit, Plus features** (history, multi-portfolio,
  monthly re-score, label-change alerts) — present and wired.
- **Migrations** — single linear head `0001→0014`, CI runs up→down→up (blocking).
- **Security non-negotiables** — all present in code (402 tier gate; CF-Connecting-IP rate limit;
  `X-Internal-Token` on the numeric endpoint; secrets hygiene clean).

## Technical debt (named + scored)

- **HIGH** — Degenerate labels: no cohort-benchmark signal (`signals.py:26-27`). This is the
  product, not polish. (B58)
- **HIGH** — Dashboard 4 missing endpoints (B56) — broken home screen.
- **MED** — NAV refresh ambiguity: a real `nav_daily_fetch` (`tasks/mf.py`) coexists with a **stub**
  `nav_ingestion` beat task (`tasks/batch.py:19` → "stub — not yet implemented"). Confirm which one
  the beat schedule actually runs, or daily NAV silently never refreshes.
- **MED** — TOTP secret stored plaintext at rest (`auth/service.py:307` TODO).
- **MED-HIGH (ops)** — Monitoring inert (no DSN, no scrape/alerts) (B38).
- **LOW-MED** — 345 ruff violations, lint advisory; mypy never enforced (B40); 6/8 market-data
  providers are stubs (most deferred); e2e smoke never executed; two overlapping backup scripts;
  feature docs missing for billing/subscriptions/onboarding/admin/audit.

## Drift (docs vs reality)

- "Wedge functional / Plus set COMPLETE" — **code TRUE, value DRIFT**: docs do not disclose that
  every fund currently scores `on_track`. (B58)
- **Internal doc contradiction**: the post-launch backlog says NAV "backfill (one-off, 2.1M rows)"
  done; the same `BLOCKERS.md` (line 24) says "first live NAV backfill not yet run." Cannot resolve
  from the repo — reconcile on the box.
- B56 dashboard drift — TRUE, still open.

## Next 30 days — top 10 (in order)

1. **Make labels differentiate** — implement the cohort-benchmark query so `outperform/underperform`
   signals are real (B58). Highest-value fix.
2. **Confirm NAV data is live** on the box (resolve `nav_daily_fetch` vs the `nav_ingestion` stub) —
   without it everything is `insufficient_data` (B29).
3. **Fix the dashboard** — build the 4 missing endpoints or remove the widgets (B56).
4. **Activate scoring v1** via the two-person + backtest gate (B6/B28) so results stop being
   `provisional_model`.
5. **Wire monitoring** — set `SENTRY_DSN`, add Prometheus scrape + alert rules (B38).
6. **Run backup + rollback live once**; verify R2 India-residency (B37/B34).
7. **Encrypt the TOTP secret at rest.**
8. **Promote ruff/mypy to blocking** after a lint cleanup (B40).
9. **Execute the e2e smoke test** against a real staging stack.
10. **Seed Razorpay plans** when the dashboard exists (data-only; unblocks billing).

## Self-audit (red-team)

- Every classification cites file:line or a verified command/run. ✅
- Completion computed from the fixed weighted model, not task counts; rounded down. ✅
- PARTIAL / MISSING / BLOCKED / DEFERRED kept distinct; blockers cited. ✅
- MVP + launch gates run as binary; failures make the verdict NO. ✅
- Technical debt named + scored; docs/code drift flagged. ✅
- No uncited number; no optimistic rounding. ✅
