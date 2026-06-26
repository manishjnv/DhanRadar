# Feature — Financial Calculators (engine architecture)

**Status:** DESIGN / not built — calculators hub is pure-UI (`/calculators`, PR #350); this doc
records the agreed engine architecture so it can be reused and improved.     **Phase:** post-launch UI
**Last updated:** 2026-06-26

> Full per-calculator specs (inputs, formulas, tooltips, what-if) live in the working plan
> `docs/project-state/CALCULATORS_IMPLEMENTATION_PLAN.md` (local-only). **This file is the durable,
> committed record of the architecture and engine logic** — the part worth reusing across the app.

## Purpose & scope

A hub of ~55 educational calculators (SIP, EMI, tax, goal, retirement, …) plus a reusable math core
that any other page can call for money calculations (portfolio gain/loss, tax on earnings). The
calculators compute on the **user's own inputs** — they are illustrations, never advice, never a
DhanRadar score.

## Non-goals

- No advice / recommendation / prediction. Calculate · Model · Illustrate · Educate · NEVER advise.
- No DhanRadar score/label/fair-value on these surfaces (the figures are the user's own numbers —
  the no-numeric-in-DOM rule's carve-out applies, same as the live `SipCalculator`).
- No speculative backend engine — see Layer 2 below (built only when a real consumer needs it).

## Architecture — a three-layer model

The classification that drives everything: **pure deterministic math on the user's own inputs — no
PII, no secrets, no score.** So the engine is frontend-primary; the backend is used only where it
earns its keep.

- **Layer 0 — `finance-core` (build first).** Pure, framework-free TS functions (the nine engines +
  tax) in `frontend/src/lib/finance/`. No React, no DOM, no network. **Single source of truth for
  all interactive money math in the app** — calculators, portfolio gain/loss, fund-detail tax
  illustration, tax-on-earnings all import the same functions. The golden-tested
  `frontend/src/features/learn/calculators/sip-math.ts` is its first module — reuse, don't rewrite.
- **Layer 1 — rate-config server seam (build with Layer 0, small).** Tax/scheme/slab rates in a
  Postgres **append-only** table (`config_type, effective_from, payload JSONB`), served via
  `GET /api/v1/config/rates?type=…&as_of=…`, Redis-cached, read by the frontend **at runtime, not
  bundled**. Effects: a Budget-day rate change needs **no redeploy**, and historical correctness
  ("rate as of the calculation date") is possible. Rates are never hard-coded inside an engine —
  engines take rates as parameters. This path is tax-accuracy-adjacent → it gets load-bearing review.
- **Layer 2 — backend Python engine (DEFER; build per-consumer).** Only when a **server-owned,
  authoritative** output needs the math (P&L over real holdings, a downloadable/emailed tax
  statement, a public API, the future mobile app). Then mirror **only the needed functions** in a
  backend `finance` module and gate parity with the shared golden vectors (below). Building the full
  mirror speculatively = double the test surface + drift risk for no consumer.

Rule of thumb: **user-typed inputs → Layer 0.** **Server-owned data or an authoritative artifact →
Layer 2, built when that consumer ships.**

## Config contract (one shape drives the whole UI template)

Each calculator is a typed config, so one template renders all of them — a new calculator is a new
config (+ maybe a new engine), with zero template changes.

```ts
interface CalcConfig {
  slug: string; name: string; emoji: string; accent: Accent; category: CategoryKey;
  blurb: string;
  engine: EngineKey;             // E1..E9
  inputs: InputSpec[];           // sliders / number / select / date — each with a `tip` (tooltip)
  options?: OptionSpec[];        // toggles & selects (step-up, payout mode, asset type…)
  outputs: OutputSpec[];         // KPIs + per-output display decimals (0|1|2)
  whatIf: WhatIfSpec[];          // sensitivity scenarios (auto-computed deltas)
  series?: SeriesSpec;           // chart + year table (time-based calcs)
  donut?: DonutSpec;             // 2-part split (invested vs profit, principal vs interest)
  learn: string; related: string[]; disclaimerExtra?: string;
}
```

- **Tooltips** are a built-in slot (`RangeField`'s hover "i" badge): every input carries a short,
  plain-English `tip`.
- **Sliders pair with a typed number box** for exact entry beyond slider granularity.
- **Advanced features extend an engine with an optional, defaulted parameter** (e.g. `stepUpPct`,
  `annuityDue`, `inflationPct`) — existing callers don't break.

## The nine engines (the math spine)

Monthly compounding convention: `i = annualRate/100/12`, `n = years × 12`; every input clamped to a
finite range; `i = 0` handled explicitly. The 55 calculators map onto these:

- **E1 Accumulation** — SIP `FV = P·((1+i)^n − 1)/i`, lump `FV = L·(1+i)^n`, step-up (year-by-year);
  drives SIP, Lumpsum, Step-up, Future Value, RD/FD/PPF/EPF/NPS accumulation, goal save-for-X.
- **E2 Goal solver** — required SIP `P = FV·i/((1+i)^n − 1)`, required lump `L = FV/(1+i)^n`, inflate
  the target first.
- **E3 Decumulation (SWP)** — `B_n = C·(1+i)^n − W·((1+i)^n − 1)/i`; depletion month, max sustainable.
- **E4 Transfer (STP)** — source decumulates (E3) into target that accumulates (E1).
- **E5 Return rate** — CAGR `(End/Begin)^(1/y) − 1`; **XIRR** (Newton + bisection/Brent fallback,
  tol 1e-7, guard same-sign / <2 flows); Rule of 72/114/144.
- **E6 Inflation** — real rate `(1+nom)/(1+inf) − 1`; real worth; future cost; cost-of-delay.
- **E7 Loan/EMI** — `EMI = P·r·(1+r)^n/((1+r)^n − 1)`; amortization; prepayment; comparison.
- **E8 Tax** — config-driven (see below); STCG/LTCG split, exemption, exit load, harvesting,
  post-tax, dividend, redemption planning.
- **E9 Aggregation** — net worth, emergency fund, passive income.

Scheme conventions (built on E1/E3): FD quarterly compounding, RD monthly-deposit/quarterly-comp,
PPF annual, EPF monthly+annual-interest, NPS accumulate→60% lump + 40% annuity.

## Tax rules (E8 / `TAX_CONFIG`) — FY 2025-26, all config knobs

- Equity MF (≥65% equity): STCG **20%** (≤12 mo); LTCG **12.5%** above **₹1.25 L**/yr (>12 mo), no
  indexation; **grandfathering** = max(actual cost, FMV on 31 Jan 2018) for pre-Feb-2018 units.
- Debt MF: bought **on/after 1 Apr 2023** → slab rate, any holding; before → ≤24 mo slab, >24 mo
  12.5% no indexation.
- Hybrid by equity share (≥65% → equity rules; else debt). IDCW → slab (TDS 10% if > ₹5,000).
  Exit load default 1% within 365 days. Surcharge (cap 15% on 111A/112A) + 4% cess on top.
- **Budget 2024 capital-gains changes effective 23 Jul 2024.** Every rate is **effective-dated** in
  Layer 1 so historical calculations use the rate in force then.

## Accuracy & display rounding

- **Accuracy = the calculation is correct** (right formula → right number), **not** float-vs-decimal.
  Native JS `number` is fine for these calculators; we do **not** add a decimal library. Accuracy is
  enforced by validating each engine against trusted reference calculators (fund-house / Excel /
  ClearTax) — see Testing.
- **Display decimals are a per-calculator choice (0 / 1 / 2)** via the output config — rupee corpus
  0 dp, return % 1–2 dp, multiplier 1 dp. Indian digit grouping + lakh/crore in KPIs; round only at
  display.
- **XIRR is the one algorithm-correctness item** (Newton-Raphson alone can return a wrong/no answer)
  → robust fallback solver. About the right number, not rounding.
- A decimal type is needed **only** for a future Layer-2 authoritative stored rupee figure (tax
  statement).

## Testing (where "accurate" is enforced)

- **Golden vectors** — `tests/fixtures/calc-vectors.json`, each case carrying its trusted **source +
  date** and a small tolerance (≤ ₹1 / ≤ 0.01%). Consumed by `vitest` now; consumed by `pytest` the
  day Layer 2 exists → a **cross-language parity gate** (TS↔Python drift fails CI). 30–50/engine.
- **Property tests** — `fast-check` (TS) / `hypothesis` (Py): monotonicity, `r=0 → FV = P·n`,
  round-trip E1↔E2, conservation `FV ≥ invested`, XIRR round-trip `NPV ≈ 0` + scale-invariance, tax
  monotonicity + slab continuity + below-exemption → ₹0.
- **Per-config smoke test** — template renders, recomputes on change, shows disclaimer + sensitivity
  strip (compliance regression guard, mirroring `SipCalculator.test.tsx`).

## Reuse across the app ("feed other pages")

`finance-core` is imported wherever the app does money math — **portfolio gain/loss**, **fund-detail
post-tax illustration**, **tax-on-earnings** surfaces — one implementation, no copy-paste.
**CAS-prefill (the moat):** parsed CAS holdings feed the capital-gains / XIRR calculator inputs (buy
NAV, units, dates) — data flows both ways; no Indian competitor does this as a calculator.

## Compliance (inherited from the live `SipCalculator`)

Rates are labelled as the user's assumption; mandatory disclaimer renders next to the result; a
sensitivity strip prevents a lone optimistic number; AI-insight cards (templated from the user's own
inputs, no LLM call) sit under `DisclosureBundle notAdvice`; no advisory verbs (CI grep). **Skip
entirely:** Monte-Carlo "success %", "X% chance you reach your goal", readiness scores, "on track"
verdicts — probabilistic/evaluative claims about the user's future read as advice/prediction.

## Related

- Working plan (local-only): `docs/project-state/CALCULATORS_IMPLEMENTATION_PLAN.md`
- Live seed engine: `frontend/src/features/learn/calculators/sip-math.ts`
- UI primitives: `frontend/src/components/calculators/` (`CalculatorHub.tsx`, `ui.tsx`, `data.ts`)
- Compliance root: `DhanRadar-Goal-Planning-Calculator` + non-negotiables #1/#2 in `CLAUDE.md`
