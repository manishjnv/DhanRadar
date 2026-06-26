/**
 * E3 — decumulation (SWP / withdrawal). A corpus earns a return while a monthly
 * amount is withdrawn (optionally rising with inflation): how long it lasts and
 * how much is withdrawn. Pure, deterministic, clamped.
 *
 *   B_{t+1} = B_t·(1+i) − W   (monthly). Sustainable when W ≤ corpus·i.
 */
import { MAX_AMOUNT, MAX_RATE_PCT } from './accumulation';

export const SWP_MAX_MONTHS = 720; // 60-year cap (treated as "sustainable")
const MAX_INFLATION = 20;

export interface SwpInput {
  corpus: number;
  monthlyWithdrawal: number;
  annualRatePct: number;
  inflationPct?: number; // step the withdrawal up this much each year
}

export interface SwpYearPoint {
  year: number;
  withdrawn: number; // cumulative
  balance: number;
}

export interface SwpResult {
  monthsLasted: number;
  sustainable: boolean; // reached the cap without depleting
  totalWithdrawn: number;
  series: SwpYearPoint[];
}

function clampF(v: number, min: number, max: number) {
  if (!Number.isFinite(v)) return min;
  return Math.min(Math.max(v, min), max);
}

export function computeSwp(input: SwpInput): SwpResult {
  const corpus = clampF(input.corpus, 0, MAX_AMOUNT);
  const w0 = clampF(input.monthlyWithdrawal, 0, MAX_AMOUNT);
  const rate = clampF(input.annualRatePct, 0, MAX_RATE_PCT);
  const infl = clampF(input.inflationPct ?? 0, 0, MAX_INFLATION);
  const i = rate / 100 / 12;
  const g = infl / 100;

  let bal = corpus;
  let cum = 0;
  let months = 0;
  let depleted = false;
  const series: SwpYearPoint[] = [{ year: 0, withdrawn: 0, balance: corpus }];

  for (let m = 0; m < SWP_MAX_MONTHS; m += 1) {
    const w = w0 * Math.pow(1 + g, Math.floor(m / 12));
    const afterGrowth = bal * (1 + i);
    if (afterGrowth < w) {
      cum += Math.max(afterGrowth, 0); // withdraw whatever remains
      bal = 0;
      months = m + 1;
      depleted = true;
      series.push({ year: Math.ceil((m + 1) / 12), withdrawn: cum, balance: 0 });
      break;
    }
    bal = afterGrowth - w;
    cum += w;
    months = m + 1;
    if (bal <= 1e-6) { // exactly exhausted on this withdrawal
      bal = 0;
      depleted = true;
      series.push({ year: Math.ceil((m + 1) / 12), withdrawn: cum, balance: 0 });
      break;
    }
    if ((m + 1) % 12 === 0) series.push({ year: (m + 1) / 12, withdrawn: cum, balance: bal });
  }

  return {
    monthsLasted: months,
    sustainable: !depleted,
    totalWithdrawn: Number.isFinite(cum) ? cum : 0,
    series,
  };
}

// ── E3 inverse — corpus needed to fund an income ─────────────────────────────
// Reverse of computeSwp: given a monthly income (today's money) and a horizon,
// the corpus needed today is the present value of every withdrawal discounted at
// the assumed return, with each year's withdrawal stepped up by inflation.
// Drives Corpus Calculator + Retirement Planner.

export interface CorpusForIncomeInput {
  monthlyWithdrawal: number; // income wanted, in today's money
  years: number; // how long it must last
  annualRatePct: number; // assumed (post-retirement) return
  inflationPct?: number; // step the income up this much each year
}

export interface CorpusForIncomeResult {
  corpusNeeded: number; // lasts exactly `years`
  perpetualCorpus: number; // never touches principal (nominal): W / i
}

export function corpusForIncome(input: CorpusForIncomeInput): CorpusForIncomeResult {
  const w0 = clampF(input.monthlyWithdrawal, 0, MAX_AMOUNT);
  const rate = clampF(input.annualRatePct, 0, MAX_RATE_PCT);
  const infl = clampF(input.inflationPct ?? 0, 0, MAX_INFLATION);
  const months = Math.round(clampF(input.years, 0, 100) * 12);
  const i = rate / 100 / 12;
  const g = infl / 100;

  let pv = 0;
  for (let m = 0; m < months; m += 1) {
    const w = w0 * Math.pow(1 + g, Math.floor(m / 12));
    pv += i === 0 ? w : w / Math.pow(1 + i, m + 1); // discount each withdrawal to today
  }
  const perpetual = i > 0 ? w0 / i : 0;
  const safe = (x: number) => (Number.isFinite(x) ? x : 0);
  return { corpusNeeded: safe(pv), perpetualCorpus: safe(perpetual) };
}
