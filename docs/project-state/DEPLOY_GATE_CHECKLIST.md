# DhanRadar — Deploy Gate Checklist

**Created:** 2026-06-07 · Single source for the path from the current branch to a **legitimate
KVM4 production deploy.** Sourced from the `CLAUDE.md` Deploy gate + the open `BLOCKERS.md` items.
Production is **main-branch-gated**; this branch must reach `main` via PR first.

Owner tags: **[CC]** Claude Code can build/drive · **[human]** needs a person/decision ·
**[data]** data seeding · **[infra]** on-box / infra verification · **[audit]** governance review.

> Nothing here authorizes a deploy. Even with owner consent, every gate below must be satisfied —
> several are legal (DPDP), integrity gates (two-person), or facts to verify, not skip.

## Gate 0 — Structural (the rule itself)

- [x] Phase-7 §5 adversarial gate logged (ACCEPT-WITH-CONDITIONS, no BLOCKER)
- [ ] **No open Security/Compliance BLOCKER** — i.e. every item in Gates 1–4 cleared
- [ ] Batched pre-deploy governance audit run + ledger signed **[audit]**
- [ ] Branch merged to `main` via PR (production is main-gated) **[CC opens PR · human merges]**
- [ ] Explicit human deploy approval — PC5 standing gate **[human]**

## Gate 1 — CRITICAL infra/ops (no automation exists yet)

- [x] **B36** CODE DONE (`7035400`, `71a3ed2`): `scripts/deploy.sh` + `scripts/rollback.sh` + `docs/ops/deploy-runbook.md`; duplicate-0008 alembic branch fixed (single head 0009). Residual: live up/down run + first real deploy **[infra runs]**
- [x] **B37** CODE DONE (`c93e387`, `71a3ed2`): `scripts/backup.sh` + `scripts/restore.sh` + `docs/ops/backup-restore-runbook.md` (nightly `pg_dump`→India R2, checksum-verified restore). Residual: R2 bucket `"jurisdiction":"in"` + 7-yr lifecycle + cron schedule **[infra]**
- [x] **B38** monitoring CODE DONE (`efc6556`): `init_sentry()` (DPDP-safe scrubber, adversarial-reviewed) + Prometheus `/metrics` (bounded labels, network-isolated). Residual: alert rules + Prometheus scrape config **[infra]**

## Gate 2 — CI / gate reliability

- [x] **B40** DONE (`ddc3f98`): TimescaleDB image + new migrations job (alembic up→down→up on real image) + ruff/mypy invoked. **Caveat:** ruff/mypy are ADVISORY (`continue-on-error`) pending a lint-cleanup before they can block; migrations job validated on first CI run **[CC]**
- [x] **B39** DONE (`a152b2b`): `--passWithNoTests` dropped; vitest + 17 component/MSW/api-client tests, 17/17 green locally **[CC]**
- [x] **B45** CODE DONE (`a152b2b`, `ddc3f98`): mocks-off CI build (`NEXT_PUBLIC_API_MOCKING=disabled`) + Playwright smoke test. Residual: run the smoke test against a real backend+frontend staging deploy **[infra]**

## Gate 3 — Compliance / DPDP (legal — blocks the relevant routes)

- [ ] **B44 / B3** consent-capture UI + Consent grant/revoke writer (without it, data routes are not legal) **[CC]**
- [ ] **B34** verify the R2 archival bucket is **India-resident** before enabling archival **[infra / human]** — procedure: `docs/ops/b25-b34-infra-verification.md`
- [ ] **B20 / B31** enforce cross-border consent at the AI + notify **call sites** **[CC · with the AI-consumer slice]**
- [ ] **B26 / B21 / B22** wire the audit + low-confidence writers **[CC · with consumer/scoring slices]**

## Gate 4 — Scoring & data activation (un-bypassable by one actor)

- [ ] **B6 / B28** real §8 backtest passes **and** an independent human approver activates (`approved_by ≠ created_by`) **[data + human]**
- [ ] **B2 / B7 / B8** seed real Razorpay plan data from the dashboard **[data / human]**
- [ ] **B29** build the MF data pipeline (AMFI NAV + scheme metadata + continuous aggregate) or reports stay `insufficient_data` **[CC / data]**
- [ ] **B25** internal numeric endpoint network policy / mTLS **[infra]** — procedure: `docs/ops/b25-b34-infra-verification.md`

## Gate 5 — Product readiness (HIGH, from the independent audit)

- [ ] **B42** mobile-responsive `AppShell` (currently desktop-only) **[CC]**
- [ ] **B43** onboarding / risk-profile UI (sole writer of `risk_profile`) **[CC]**
- [ ] **B46** surface CAS job `status: error` (currently an infinite spinner) **[CC]**

## Gate 6 — Live-stack runtime proofs (deploy-time)

- [ ] E2E flow against the real stack; NTP; R2 archival; measured box memory ≤ 3072M **[infra]**

## Shortest legitimate path

1. Clear Gates 1–4 (CC builds the code/ops parts; human/data/infra clear the rest).
2. Run the Gate-0 governance audit → sign the ledger.
3. CC opens the PR → human merges to `main`.
4. Seed data (Razorpay) + activate scoring (backtest + independent approver).
5. Verify infra (R2 residency, mTLS, backups) + ship the consent-capture UI + Gate-6 proofs.
6. Human gives explicit PC5 deploy approval → deploy to KVM4.

## Lane note (concurrent session active)

The other session owns the **frontend** (auth/mood/settings/notifications screens), `ci.yml`, the
**AI-consumer** slice, and **B29** (MF pipeline, foundation already committed). To avoid collision,
Claude Code's safe immediate lane is the **net-new infra/ops** gates: **B36 → B37 → B38**.
