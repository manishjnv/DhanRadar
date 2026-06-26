/**
 * E4 — Transfer (STP: Systematic Transfer Plan). Two coupled flows: a SOURCE fund
 * decumulates while a fixed monthly amount is transferred into a TARGET fund that
 * accumulates. Pure, deterministic, clamped.
 *
 * Timing convention (grow-then-transfer, ordinary): each month both balances grow
 * by their monthly rate, then the transfer moves from source to target. This makes
 * the conservation property exact — at equal rates, source+target always equals a
 * single untouched fund (tested).
 */
import { MAX_AMOUNT, MAX_RATE_PCT, MAX_YEARS } from './accumulation';

export interface StpInput {
  sourceCorpus: number; // starting lump in the source fund (₹)
  monthlyTransfer: number; // amount moved each month (₹)
  sourceRatePct: number; // assumed source return (e.g. debt ~6%)
  targetRatePct: number; // assumed target return (e.g. equity assumption)
  years: number;
}

export interface StpYearPoint {
  year: number;
  source: number;
  target: number;
  combined: number;
}

export interface StpResult {
  targetBuilt: number;
  sourceLeft: number;
  combined: number;
  totalTransferred: number;
  monthsToDrain: number; // 0 if the source never drains within the horizon
  series: StpYearPoint[];
}

function clampF(v: number, min: number, max: number) {
  if (!Number.isFinite(v)) return min;
  return Math.min(Math.max(v, min), max);
}

export function computeStp(input: StpInput): StpResult {
  const source0 = clampF(input.sourceCorpus, 0, MAX_AMOUNT);
  const transfer = clampF(input.monthlyTransfer, 0, MAX_AMOUNT);
  const is = clampF(input.sourceRatePct, 0, MAX_RATE_PCT) / 100 / 12;
  const it = clampF(input.targetRatePct, 0, MAX_RATE_PCT) / 100 / 12;
  const months = Math.round(clampF(input.years, 0, MAX_YEARS) * 12);

  let source = source0;
  let target = 0;
  let transferred = 0;
  let monthsToDrain = 0;
  const series: StpYearPoint[] = [{ year: 0, source, target: 0, combined: source }];

  for (let m = 0; m < months; m += 1) {
    const srcAfterGrowth = source * (1 + is);
    const w = Math.min(transfer, srcAfterGrowth); // can't transfer more than the source holds
    source = srcAfterGrowth - w;
    target = target * (1 + it) + w;
    transferred += w;
    if (source <= 1e-6 && monthsToDrain === 0) { source = 0; monthsToDrain = m + 1; }
    if ((m + 1) % 12 === 0) series.push({ year: (m + 1) / 12, source, target, combined: source + target });
  }

  const safe = (x: number) => (Number.isFinite(x) ? x : 0);
  return {
    targetBuilt: safe(target),
    sourceLeft: safe(source),
    combined: safe(source + target),
    totalTransferred: safe(transferred),
    monthsToDrain,
    series,
  };
}
