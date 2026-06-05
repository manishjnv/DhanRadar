# Launch Checklist (Go/No-Go)

## P0 — Critical (hard gates for public launch; parallelizable with build)
- [ ] **Compliance:** legal sign-off on signal-vs-advice copy + SEBI RA applicability (launch/compliance-policy.md)
- [ ] **Data licensing:** signed market-data + news licenses; vendor abstraction live (launch/data-licensing…)
- [ ] **DPDP:** consent records, export/erasure, data map, DPAs, grievance officer (launch/dpdp…)
- [ ] **AA consent:** sandbox→prod tested; revocation + purge; no creds stored (launch/account-aggregator…)
- [ ] **AI safety:** eval gates green; safety monitor blocking; cost caps (launch/ai-eval…)
- [ ] **Incident:** on-call rota, runbooks tested, dashboards + status page (launch/incident…)
- [ ] **Secrets:** keys in Vault, JWKS, rotation tested, gitleaks clean (launch/secrets…)

## P1 — High
- [ ] CA reconciliation + news linking precision (launch/data-quality…)
- [ ] Capacity: recompute <30m, replica routing, soak/spike passed (launch/capacity…)
- [ ] Onboarding + cold-start live; activation instrumented (launch/onboarding…)
- [ ] A11y CI budgets + manual SR pass (launch/accessibility…)
- [ ] AI confidence calibrated before exposing % (launch/ai-eval…)

## P2 — Medium (pre/at launch)
- [ ] Pen-test booked; bug bounty planned (F15)
- [ ] Pricing locked: annual %, student, trial length (F16)
- [ ] Backup restore drill on calendar (F14)
- [ ] GST/refund flows verified (F12)
- [ ] Observability dashboards provisioned (F20)

## P3 — Low (fast-follow)
- [ ] Support intake + status page comms (F22)
- [ ] i18n Hindi rollout (F19)

**Go/No-Go owner:** CTO + Legal. Engineering build may start immediately (no P0 blocks code); P0s gate **public launch**, not development.
