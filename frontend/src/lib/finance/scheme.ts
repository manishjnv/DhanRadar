/**
 * Scheme calculators — FD, RD, PPF. Each uses its real-world compounding
 * convention so the numbers match bank / Post-Office calculators.
 *
 *   FD : lump sum, compounded N times/year (quarterly by default). A = P(1+r/N)^(N·y)
 *   RD : monthly deposit, interest compounded QUARTERLY (the bank convention),
 *        modelled month-by-month at the quarterly-equivalent monthly rate.
 *   PPF: annual deposit, compounded ANNUALLY (notified rate), typically 15 years.
 *
 * Pure, deterministic, clamped. Rates are the user's input (PPF/EPF rates are
 * government-notified and change — surfaced as editable, not hard-coded).
 */
import { MAX_AMOUNT, MAX_RATE_PCT, MAX_YEARS } from './accumulation';

export interface SchemeYearPoint {
  year: number;
  invested: number;
  value: number;
}

export interface SchemeResult {
  maturity: number;
  invested: number;
  interest: number;
  series: SchemeYearPoint[];
}

function clampF(v: number, min: number, max: number) {
  if (!Number.isFinite(v)) return min;
  return Math.min(Math.max(v, min), max);
}

/** Fixed Deposit — lump sum compounded `compoundsPerYear` times a year. */
export function computeFd(principal: number, annualRatePct: number, years: number, compoundsPerYear = 4): SchemeResult {
  const P = clampF(principal, 0, MAX_AMOUNT);
  const r = clampF(annualRatePct, 0, MAX_RATE_PCT) / 100;
  const y = clampF(years, 0, MAX_YEARS);
  const n = clampF(compoundsPerYear, 1, 12);
  const at = (t: number) => {
    const v = P * Math.pow(1 + r / n, n * t);
    return Number.isFinite(v) ? v : 0;
  };
  const series: SchemeYearPoint[] = [];
  const wholeYears = Math.floor(y);
  for (let t = 0; t <= wholeYears; t += 1) series.push({ year: t, invested: P, value: at(t) });
  const maturity = at(y);
  return { maturity, invested: P, interest: Math.max(maturity - P, 0), series };
}

/** Recurring Deposit — monthly deposit, interest compounded quarterly. */
export function computeRd(monthlyDeposit: number, annualRatePct: number, years: number): SchemeResult {
  const D = clampF(monthlyDeposit, 0, MAX_AMOUNT);
  const r = clampF(annualRatePct, 0, MAX_RATE_PCT) / 100;
  const y = clampF(years, 0, MAX_YEARS);
  // Quarterly compounding expressed as an equivalent monthly rate (deposit at start of month).
  const im = Math.pow(1 + r / 4, 1 / 3) - 1;
  const months = Math.round(y * 12);
  const at = (m: number) => {
    let bal = 0;
    for (let k = 0; k < m; k += 1) bal = (bal + D) * (1 + im);
    return Number.isFinite(bal) ? bal : 0;
  };
  const series: SchemeYearPoint[] = [];
  const wholeYears = Math.floor(y);
  for (let t = 0; t <= wholeYears; t += 1) series.push({ year: t, invested: D * t * 12, value: at(t * 12) });
  const maturity = at(months);
  const invested = D * months;
  return { maturity, invested, interest: Math.max(maturity - invested, 0), series };
}

export interface EpfInput {
  monthlyBasic: number; // basic + DA
  contributionPct: number; // total going into EPF (employee + employer), e.g. 24
  annualRatePct: number; // notified EPF rate
  years: number;
  salaryGrowthPct?: number; // annual increment in basic
}

/**
 * EPF — monthly contribution on (basic+DA), interest accrued monthly and credited
 * annually (EPF convention), with optional annual salary growth.
 */
export function computeEpf(input: EpfInput): SchemeResult {
  const basic0 = clampF(input.monthlyBasic, 0, MAX_AMOUNT);
  const pct = clampF(input.contributionPct, 0, 100) / 100;
  const r = clampF(input.annualRatePct, 0, MAX_RATE_PCT) / 100;
  const y = clampF(input.years, 0, MAX_YEARS);
  const g = clampF(input.salaryGrowthPct ?? 0, 0, 50) / 100;
  const im = r / 12;
  const wholeYears = Math.floor(y);

  let bal = 0;
  let basic = basic0;
  let cumContrib = 0;
  let yearInterest = 0;
  const series: SchemeYearPoint[] = [{ year: 0, invested: 0, value: 0 }];

  for (let m = 1; m <= wholeYears * 12; m += 1) {
    const contribution = basic * pct;
    bal += contribution;
    cumContrib += contribution;
    yearInterest += bal * im; // accrue interest on the running balance
    if (m % 12 === 0) {
      bal += yearInterest;
      yearInterest = 0;
      series.push({ year: m / 12, invested: cumContrib, value: Number.isFinite(bal) ? bal : 0 });
      basic *= 1 + g; // next year's salary
    }
  }
  const maturity = Number.isFinite(bal) ? bal : 0;
  return { maturity, invested: cumContrib, interest: Math.max(maturity - cumContrib, 0), series };
}

/** PPF — annual deposit, compounded annually at the notified rate. */
export function computePpf(yearlyDeposit: number, annualRatePct: number, years: number): SchemeResult {
  const A = clampF(yearlyDeposit, 0, MAX_AMOUNT);
  const r = clampF(annualRatePct, 0, MAX_RATE_PCT) / 100;
  const y = clampF(years, 0, MAX_YEARS);
  const wholeYears = Math.floor(y);
  const series: SchemeYearPoint[] = [{ year: 0, invested: 0, value: 0 }];
  let bal = 0;
  for (let t = 1; t <= wholeYears; t += 1) {
    bal = (bal + A) * (1 + r); // deposit then a year's interest
    series.push({ year: t, invested: A * t, value: Number.isFinite(bal) ? bal : 0 });
  }
  const maturity = Number.isFinite(bal) ? bal : 0;
  const invested = A * wholeYears;
  return { maturity, invested, interest: Math.max(maturity - invested, 0), series };
}
