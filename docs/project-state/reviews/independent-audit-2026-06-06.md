# DhanRadar — Independent Audit (2026-06-06)

**Stance:** Principal Engineer / QA Lead / Product Architect / Security Reviewer / UAT Lead /
Technical Investor. Evidence-based, skeptical. **Basis:** actual code on branch
`frontend/auth-screens`, not docs. **Method:** load-bearing seams (auth, consent, billing,
budget, CI, entry point) verified by Opus directly; breadth gathered by four independent agents
(frontend/UAT, tests, CI/infra, scoring/compliance/docs) and corroborated.

## Verdict

A disciplined, well-secured **prototype** with an empty engine and no operational layer. The
safety rails and compliance spine are genuinely strong; the product muscle (real data, real
reports, deploy, monitoring) is absent. **~40% of an MVP.** **NO-GO** for production/launch;
**GO** for continued build.

The overriding fact: **the product is functionally inert.** All market-data providers are stubs
(`market_data/providers/stubs.py`), so a real CAS upload labels every fund `insufficient_data`.
The frontend (`providers.tsx`) runs entirely on MSW mocks and has never hit the real backend. The
impressive demo is a mock talking to a stub.

## Top findings (ranked)

1. Core product produces no real output — all data providers stubbed (B29/B35).
2. Frontend never touched the real backend — entirely MSW mocks (B45).
3. No deploy automation, no rollback (B36).
4. No DB backup / PITR — disk loss destroys data + the 7-yr SEBI audit trail (B37).
5. No monitoring/metrics/alerting; Sentry installed but `sentry_sdk.init` never called (B38).
6. Frontend has zero tests; `vitest run --passWithNoTests` = vacuous green CI (B39).
7. `docs/ui-system/contracts/*` define SEBI-banned advisory verbs, bearer auth, public numeric
   score + fair_value, Elasticsearch — no in-file warning (B41).
8. CI runs neither ruff nor mypy (B40).
9. CI uses `postgres:16`, not TimescaleDB — extensions + `01_init.sql` never exercised (B40).
10. Alembic migrations never tested — CI uses `create_all`, bypassing them (B40).
11. AI budget hard-cap is a TOCTOU race (B18, confirmed in `budget.py:135-148`).
12. AI advisory filter is "core set only" — descriptive advice + Hindi pass (B23).
13. Compliance audit writes are fire-and-forget, no dead-letter, no backup (B26/B34 residual).
14. No onboarding / risk-profile UI — sole risk-profile writer missing (B43).
15. No DPDP consent UI (B44).
16. Authenticated app is desktop-only — no responsive nav (B42).
17. CAS job failure shows an infinite spinner (B46).
18. No dependency lockfile enforcement (backend `>=` floors; FE `npm install` not `npm ci`).
19. Internal numeric-score endpoint relies on a comment, not a tested control (B25).
20. Large missing surface — billing UI, password reset, email verify, 2FA, account, stocks/ETF,
    watchlist, portfolio (six `.gitkeep`-only feature folders).

## What is genuinely strong (verified)

- Auth: `__Host-` HttpOnly cookies, RS256-only with alg whitelist, Argon2id, generic auth errors,
  atomic `GETDEL` refresh rotation. (`auth/security.py`, `deps.py`)
- `RequireConsent` fail-closed: fresh read (instant revoke), anonymous → 401 before 403, malformed
  subject fails closed. (`deps.py`)
- Billing checkout: catalog-controlled amount, double-charge NX lock with TTL > call timeout,
  503 fail-safe on unseeded plans, secret never returned. (`billing/service.py`)
- Scoring compliance invariants hold at the type level: label from rule table (not score),
  confidence < 0.30 → refuse, risk-profile excluded, five-label enum (no advisory verbs).
- Backend unit tests (~212) are real and decent quality (HS256 forgery, real HMAC webhook sigs).

## Scorecard

| Dimension | Score |
|---|---|
| Product Vision | 8/10 |
| Architecture | 8/10 |
| Code Quality | 7/10 |
| Security | 7/10 |
| UX | 3/10 |
| Scalability | 4/10 |
| Documentation | 6/10 |
| Test Coverage | 4/10 |
| Production Readiness | 2/10 |
| Investment Readiness | 3/10 |
| **Overall** | **5.2/10** |

## Go / No-Go

**NO-GO** for production or external launch — the blockers are the absence of the product (real
data), of operations (deploy/backup/monitoring), and of legal gates (consent UI, AI advisory
completeness). **GO** for continued build — the foundation and discipline are worth building on.
Path to GO: ~6–10 focused weeks, starting with the free AMFI feed.

**Customer/investor question — would I approve it tomorrow?** No. What is shown is a beautiful
mock talking to a stub: a real upload returns "insufficient data" on every fund, on a
desktop-only screen, with no way to deploy, back up, or monitor it. The discipline says the
founder can build it right; that is not the same as having a product. Come back when one real CAS
upload returns one real labelled report in production.

## Tracking

Core launch gaps filed as **B36–B46** in `BLOCKERS.md`. Growth/education sequencing in
`GROWTH_BACKLOG.md`. Data gates: **B29** (MF NAV pipeline), **B35** (Mood signals).
