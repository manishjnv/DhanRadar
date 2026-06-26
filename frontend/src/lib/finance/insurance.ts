/**
 * E10 — Insurance need estimators (educational, indicative only).
 *
 * These produce an INDICATIVE cover figure to discuss with a licensed advisor —
 * never a product pick, never a recommendation to buy any policy. Pure,
 * deterministic, clamped. Rates/factors live in INSURANCE_CONFIG (they are
 * rules-of-thumb the user can change), per the "leave the knob" rule.
 */
import { MAX_AMOUNT } from './accumulation';

export const INSURANCE_CONFIG = {
  hlvIncomeMultiplier: 15, // simple 10–15× income cross-check
  healthBaseByTier: { 1: 1000000, 2: 700000, 3: 500000 } as Record<number, number>,
  medicalInflationPct: 10,
  bandPct: 20, // ±band around the indicative figure
  asOf: '2026',
};

function clampF(v: number, min: number, max: number) {
  if (!Number.isFinite(v)) return min;
  return Math.min(Math.max(v, min), max);
}

// PV of an annual amount received for `years`, discounted at `dPct` (net of income
// growth). dPct = 0 → amount × years.
function pvAnnuity(annual: number, years: number, dPct: number): number {
  const d = dPct / 100;
  if (d <= 0) return annual * years;
  const pv = annual * ((1 - Math.pow(1 + d, -years)) / d);
  return Number.isFinite(pv) ? pv : 0;
}

// ── Human Life Value (income-replacement) ────────────────────────────────────
export interface HlvInput {
  annualIncome: number;
  currentAge: number;
  retirementAge: number;
  discountRatePct: number; // net discount = return − income growth (an assumption)
  existingCover?: number;
}
export interface HlvResult {
  workingYears: number;
  hlv: number; // present value of the income the earner would replace
  multiplierCheck: number; // annualIncome × 15 (rule-of-thumb cross-check)
  coverGap: number; // hlv − existing cover (≥ 0)
}

export function computeHlv(input: HlvInput): HlvResult {
  const income = clampF(input.annualIncome, 0, MAX_AMOUNT);
  const curAge = clampF(input.currentAge, 18, 75);
  const retAge = clampF(input.retirementAge, 40, 80);
  const d = clampF(input.discountRatePct, 0, 20);
  const existing = clampF(input.existingCover ?? 0, 0, MAX_AMOUNT);
  const workingYears = Math.max(retAge - curAge, 0);
  const hlv = pvAnnuity(income, workingYears, d);
  const safe = (x: number) => (Number.isFinite(x) ? x : 0);
  return {
    workingYears,
    hlv: safe(hlv),
    multiplierCheck: safe(income * INSURANCE_CONFIG.hlvIncomeMultiplier),
    coverGap: safe(Math.max(hlv - existing, 0)),
  };
}

// ── Term Cover (needs-based gap) ─────────────────────────────────────────────
export interface TermCoverInput {
  annualIncome: number;
  yearsToCover: number; // dependent years to replace income for
  discountRatePct: number;
  outstandingLoans: number;
  futureGoals: number; // education / marriage etc. the cover should fund
  existingCoverAssets: number; // existing life cover + liquid assets to subtract
}
export interface TermCoverResult {
  incomeReplacement: number;
  totalNeed: number; // income replacement + loans + goals
  gap: number; // totalNeed − existing (≥ 0)
}

export function computeTermCover(input: TermCoverInput): TermCoverResult {
  const income = clampF(input.annualIncome, 0, MAX_AMOUNT);
  const years = clampF(input.yearsToCover, 0, 60);
  const d = clampF(input.discountRatePct, 0, 20);
  const loans = clampF(input.outstandingLoans, 0, MAX_AMOUNT);
  const goals = clampF(input.futureGoals, 0, MAX_AMOUNT);
  const existing = clampF(input.existingCoverAssets, 0, MAX_AMOUNT);
  const incomeReplacement = pvAnnuity(income, years, d);
  const totalNeed = incomeReplacement + loans + goals;
  const safe = (x: number) => (Number.isFinite(x) ? x : 0);
  return {
    incomeReplacement: safe(incomeReplacement),
    totalNeed: safe(totalNeed),
    gap: safe(Math.max(totalNeed - existing, 0)),
  };
}

// ── Health Cover (city tier × family × medical inflation) ────────────────────
export interface HealthCoverInput {
  cityTier: number; // 1 | 2 | 3
  familySize: number;
  horizonYears: number; // grow the cover for medical inflation over this horizon
}
export interface HealthCoverResult {
  baseCover: number; // tier base × family factor (today)
  indicativeCover: number; // base grown by medical inflation over the horizon
  bandLow: number;
  bandHigh: number;
}

export function computeHealthCover(input: HealthCoverInput): HealthCoverResult {
  const C = INSURANCE_CONFIG;
  const tier = clampF(input.cityTier, 1, 3);
  const family = clampF(input.familySize, 1, 12);
  const horizon = clampF(input.horizonYears, 0, 40);
  const tierBase = C.healthBaseByTier[Math.round(tier)] ?? C.healthBaseByTier[2];
  const familyFactor = 1 + 0.4 * (family - 1); // each extra member adds ~40%
  const baseCover = tierBase * familyFactor;
  const indicativeCover = baseCover * Math.pow(1 + C.medicalInflationPct / 100, horizon);
  const band = C.bandPct / 100;
  const safe = (x: number) => (Number.isFinite(x) ? x : 0);
  return {
    baseCover: safe(baseCover),
    indicativeCover: safe(indicativeCover),
    bandLow: safe(indicativeCover * (1 - band)),
    bandHigh: safe(indicativeCover * (1 + band)),
  };
}
