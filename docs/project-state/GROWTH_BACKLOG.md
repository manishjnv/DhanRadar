# DhanRadar — Growth & Education Backlog (core-first sequencing)

**Created:** 2026-06-06 · **Owner:** Architect · **Status:** Active (planning)

This file merges the **v2.4 Growth & Education Addendum** (G1–G10, B1, C1) with the
**2026-06-06 independent audit** (`reviews/independent-audit-2026-06-06.md`) into one
sequenced plan. The single rule: **build the engine before the showroom.**

## Why core comes first (the correction to v2.4)

The v2.4 addendum states every item is "additive, decoupled, does not block the MF-first
critical path." That is only true *if the MF-first path works*. The audit found it does not:
market-data providers are stubbed (B29/B35) so every live fund scores `insufficient_data`, the
frontend runs entirely on MSW mocks (B45), and there is no deploy/backup/monitoring (B36–B38).
So most v2.4 items are additive to a product that is **not running yet** — they are resequenced
*behind* the core-fix work, with three cheap exceptions that need no live data.

## Tier 0 — Core functionality (must come first; not in v2.4)

These are the product, not growth. Blockers: B29, B35 (data) + B36–B46 (audit).

1. **Make the data real** — wire the free public AMFI daily NAV feed + deploy `casparser` in the
   worker. Turns `insufficient_data` into real labels. (B29; unblocks most v2.4 items.)
2. **Deployable + recoverable** — deploy/rollback runbook + script; nightly Postgres backup to
   India-resident storage; test Alembic up/down. (B36, B37)
3. **Observable** — initialise Sentry (installed, never called); `/metrics`; crash/health alerts. (B38)
4. **Honest CI** — add ruff + mypy; TimescaleDB image; run real migrations; drop `--passWithNoTests`. (B39, B40)
5. **Usable + legal** — responsive mobile shell; onboarding/risk-profile flow; DPDP consent UI;
   fix the CAS-error infinite spinner; harden the AI advisory filter incl. Hindi. (B42, B43, B44, B46, B23)

## Tier 1 — Cheap parallel wins (buildable NOW, need no live data)

A second track can build these while Tier 0 lands. All are SEO/acquisition assets.

- **C1 — Concept-Explainer "Learn" library (static half).** Build the `concept_explainers`
  content table + fixed approach-card template as anonymous-first crawlable pages now. Contextual
  surfacing (by holdings) waits for data. **Build now.**
- **G8 — Tax-education engine.** Static, calendar-driven, zero AI cost, SEBI-safe, seasonally
  viral. **Build now**; time the push for Feb–Jun.
- **G7 — Beginner funnel / vernacular onboarding.** Fold into the Tier-0 onboarding screen.
  **Build with onboarding.** Gate: the Hindi/regional advisory filter (B23) must exist first.
- **G2 design ethos (calm palette, dark mode, de-emphasised red, less clutter)** — adopt as a
  design principle during the mobile rebuild. Full Calm Mode (drawdown context) is data-gated.

## Tier 2 — Data-gated growth (right after the engine is real)

Unlock once Tier 0 #1 lands and real history accrues.

- **G3 — Deepest MF analytics** (debt-fund Modified Duration/YTM/credit-quality, true overlap,
  rupee expense-drag, manager-change flags). Treat as **core MF differentiation**, fold into the
  "make MF real" work. Overlap + expense-drag math partly exist in the snapshot. Data-gated.
- **G10 — Show your working** (per-score inputs, weights, freshness, "what would change this").
  Strong compliance moat. **Constraint v2.4 misses:** non-neg #2 — the per-instrument numeric
  score must NOT reach the public DOM. Surface label + band + qualitative factors only; keep the
  number server-side.
- **B1 — Compliant benchmark view** (You vs NIFTY 50 TRI, expense drag, behaviour streaks).
  `portfolio_snapshots.benchmark_xirr` is only real once NAV/price history exists. Data-gated.
  Mirror-not-sales-claim line is correct; keep it.
- **G5 — Grounded research assistant** (AI chat over real holdings). Needs real data + AI
  compliance gaps closed (B20 cross-border consent, B23 filter, B21 model_used). Build after AI hardening.

## Tier 3 — Defer (need a user base or unbuilt modules)

- **G1 — Creator Studio** (lagged-data embeds, badges, widgets). Best CAC play, but embeds real
  Mood + fund labels (inert today) and the embed widget isn't built (B35). Schedule as the
  headline of the growth phase, right after data is real.
- **G9 — Aggregate social proof** ("78% held through the drawdown"). Needs users + a behaviour
  aggregate. Zero users today. Defer.
- **G4 — Goal-based SIP health** + **G6 — Multi-asset view.** Need unbuilt modules (goals;
  portfolio across stocks/gold/international). Defer to the portfolio phase. **Compliance watch
  on G4:** probability bands are the closest to implied-performance — keep explicitly
  historical-illustrative, risk shown beside return.

## Merged sequence (one line each)

- **Now (Track A, core):** real data → deploy/backup/monitor → CI honesty → mobile + onboarding + consent + advisory filter.
- **Now (Track B, parallel, no data):** C1 Learn library · G8 tax content · G7 vernacular onboarding · adopt G2 calm design.
- **After data is real:** G3 deep MF analytics · G10 show-your-working · B1 benchmark view.
- **Growth phase:** G1 Creator Studio · G5 research assistant · G9 social proof.
- **Portfolio phase / Y2:** G4 goal health · G6 multi-asset · full G2 Calm Mode.

## Compliance flags specific to v2.4 (verify before building)

1. **G10** must not leak the numeric score to the DOM (non-neg #2) — show inputs/weights/factors,
   not the number.
2. **G4 / B1** are closest to the SEBI performance-attribution line; close the v2.4 §7 open item
   (confirm "education + live data + published scores" with counsel) **before** these ship.
3. **G7 vernacular AI** requires the Hindi/regional advisory filter (B23) first, or you ship
   advice in a language the guard does not read.

## Sequencing IDs

v2.4 items keep their own IDs (G1–G10, B1, C1) — they are tracked here, not given B-numbers.
The core launch gaps are tracked as **B36–B46** in `BLOCKERS.md`. Data gates are **B29** (MF NAV
pipeline) and **B35** (Mood signals).
