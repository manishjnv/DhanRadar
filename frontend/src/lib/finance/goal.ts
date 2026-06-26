/**
 * E2 — Goal solver (the reverse of E1 accumulation).
 *
 * Given a target amount, horizon, and an assumed return, solve the contribution
 * needed to reach it: the required monthly SIP and the required one-time lump sum.
 * Optionally inflate the goal to its future cost and net off what the user has
 * already saved. Pure, deterministic, clamped — never NaN/Infinity.
 *
 * The assumed return / inflation are the USER's own assumptions, not predictions.
 */
import { MAX_AMOUNT, MAX_RATE_PCT, MAX_YEARS } from './accumulation';

export const MAX_INFLATION_PCT = 50;

export interface GoalInput {
  /** Goal cost in TODAY's money (₹). */
  targetToday: number;
  /** Years until the goal. */
  years: number;
  /** USER-CHOSEN assumed annual return % (0–50). */
  annualRatePct: number;
  /** Optional inflation % to grow the goal to its future cost. */
  inflationPct?: number;
  /** Optional amount already saved (grows at the assumed return). */
  currentSavings?: number;
}

export interface GoalResult {
  /** The goal's cost at the target date (today's cost grown by inflation). */
  inflatedTarget: number;
  /** What the user's current savings grows to by the target date. */
  futureOfSavings: number;
  /** The gap the new investing must cover (≥ 0). */
  shortfall: number;
  /** Monthly SIP that closes the shortfall (ordinary annuity). */
  requiredMonthly: number;
  /** One-time amount today that closes the shortfall. */
  requiredLump: number;
}

function clampFinite(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}

/** Solve the contribution needed to reach a goal. Deterministic + finite. */
export function solveGoal(input: GoalInput): GoalResult {
  const targetToday = clampFinite(input.targetToday, 0, MAX_AMOUNT);
  const years = clampFinite(input.years, 0, MAX_YEARS);
  const rate = clampFinite(input.annualRatePct, 0, MAX_RATE_PCT);
  const infl = clampFinite(input.inflationPct ?? 0, 0, MAX_INFLATION_PCT);
  const current = clampFinite(input.currentSavings ?? 0, 0, MAX_AMOUNT);

  const i = rate / 100 / 12; // monthly rate (SIP)
  const annual = rate / 100; // annual rate (lump / savings)
  const n = Math.round(years * 12);
  const monthlyGrowth = Math.pow(1 + i, n); // (1+i)^n
  const annualGrowth = Math.pow(1 + annual, years); // (1+annual)^years

  const inflatedTarget = targetToday * Math.pow(1 + infl / 100, years);
  const futureOfSavings = current * annualGrowth; // existing savings compound annually
  const shortfall = Math.max(inflatedTarget - futureOfSavings, 0);

  // Required SIP — invert the annuity-DUE formula (matches computeSip):
  //   FV = P · ((1+i)^n − 1)/i · (1+i)   (i = 0 → FV / n)
  const dueFactor = i === 0 ? n : ((monthlyGrowth - 1) / i) * (1 + i);
  const requiredMonthly = dueFactor > 0 ? shortfall / dueFactor : 0;
  // Required one-time lump today — invert annual compounding: L = FV / (1+annual)^years.
  const requiredLump = annualGrowth > 0 ? shortfall / annualGrowth : 0;

  const safe = (x: number) => (Number.isFinite(x) ? x : 0);
  return {
    inflatedTarget: safe(inflatedTarget),
    futureOfSavings: safe(futureOfSavings),
    shortfall: safe(shortfall),
    requiredMonthly: safe(requiredMonthly),
    requiredLump: safe(requiredLump),
  };
}
