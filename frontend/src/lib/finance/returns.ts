/**
 * E5 — return / growth-rate math: CAGR, the Rule-of-72/114/144, and XIRR.
 *
 * Pure, deterministic, clamped. XIRR uses Newton-Raphson with a bisection
 * fallback (plain Newton diverges near −100% or on flat NPV curves).
 */
import { MAX_AMOUNT, MAX_RATE_PCT, MAX_YEARS } from './accumulation';

function clampFinite(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}

export interface CagrResult {
  cagrPct: number; // compound annual growth rate %
  absolutePct: number; // total (point-to-point) return %
  doublingYears: number; // years to double at this CAGR (0 if non-positive)
}

/** CAGR between a start and end value over `years`. */
export function computeCagr(begin: number, end: number, years: number): CagrResult {
  const b = clampFinite(begin, 0, MAX_AMOUNT);
  const e = clampFinite(end, 0, MAX_AMOUNT);
  const y = clampFinite(years, 0, MAX_YEARS);
  if (b <= 0 || y <= 0) return { cagrPct: 0, absolutePct: 0, doublingYears: 0 };
  const cagr = Math.pow(e / b, 1 / y) - 1;
  const absolute = (e - b) / b;
  const doubling = cagr > 0 ? Math.log(2) / Math.log(1 + cagr) : 0;
  return {
    cagrPct: Number.isFinite(cagr) ? cagr * 100 : 0,
    absolutePct: Number.isFinite(absolute) ? absolute * 100 : 0,
    doublingYears: Number.isFinite(doubling) ? doubling : 0,
  };
}

export interface RuleResult {
  double: number; // years to 2× (Rule of 72)
  triple: number; // years to 3× (Rule of 114)
  quad: number; // years to 4× (Rule of 144)
  exactDouble: number; // exact years to 2× (ln 2 / ln(1+r))
}

/** Rule-of-72/114/144 doubling/tripling/quadrupling times for a rate. */
export function ruleOf(annualRatePct: number): RuleResult {
  const r = clampFinite(annualRatePct, 0, MAX_RATE_PCT);
  const approx = (n: number) => (r > 0 ? n / r : 0);
  const exact = (k: number) => (r > 0 ? Math.log(k) / Math.log(1 + r / 100) : 0);
  return {
    double: approx(72),
    triple: approx(114),
    quad: approx(144),
    exactDouble: Number.isFinite(exact(2)) ? exact(2) : 0,
  };
}

/**
 * E6 — real (inflation-adjusted) annual rate: (1+nominal)/(1+inflation) − 1.
 * The return the money earns *above* the rise in prices. Clamped to a finite %.
 */
export function realReturn(nominalPct: number, inflationPct: number): number {
  const n = clampFinite(nominalPct, -100, MAX_RATE_PCT) / 100;
  const f = clampFinite(inflationPct, 0, MAX_RATE_PCT) / 100;
  const real = (1 + n) / (1 + f) - 1;
  return Number.isFinite(real) ? real * 100 : 0;
}

export interface CashFlow {
  date: Date;
  amount: number; // outflows (investments) negative, inflows (redemptions) positive
}

export interface XirrResult {
  xirrPct: number;
  converged: boolean;
}

/** XIRR for dated, irregular cash flows. Newton-Raphson + bisection fallback. */
export function computeXirr(flows: CashFlow[]): XirrResult {
  const valid = flows.filter((f) => Number.isFinite(f.amount) && f.date instanceof Date && !Number.isNaN(f.date.getTime()));
  if (valid.length < 2) return { xirrPct: 0, converged: false };
  const amounts = valid.map((f) => f.amount);
  if (amounts.every((a) => a >= 0) || amounts.every((a) => a <= 0)) return { xirrPct: 0, converged: false };

  const t0 = Math.min(...valid.map((f) => f.date.getTime()));
  const MS_PER_YEAR = 365 * 24 * 3600 * 1000;
  const yrs = (d: Date) => (d.getTime() - t0) / MS_PER_YEAR;
  const xnpv = (rate: number) => valid.reduce((s, f) => s + f.amount / Math.pow(1 + rate, yrs(f.date)), 0);

  // Newton-Raphson.
  let rate = 0.1;
  for (let i = 0; i < 60; i += 1) {
    const f = xnpv(rate);
    const df = valid.reduce((s, cf) => {
      const t = yrs(cf.date);
      return s - (t * cf.amount) / Math.pow(1 + rate, t + 1);
    }, 0);
    if (!Number.isFinite(df) || Math.abs(df) < 1e-12) break;
    let next = rate - f / df;
    if (!Number.isFinite(next)) break;
    if (next <= -0.9999) next = -0.9999;
    if (Math.abs(next - rate) < 1e-7) {
      rate = next;
      if (Math.abs(xnpv(rate)) < 1) return { xirrPct: rate * 100, converged: true };
      break;
    }
    rate = next;
  }

  // Bisection fallback over a bracket that contains the root.
  let lo = -0.9999;
  let hi = 10;
  const flo = xnpv(lo);
  const fhi = xnpv(hi);
  if (!Number.isFinite(flo) || !Number.isFinite(fhi) || flo * fhi > 0) return { xirrPct: 0, converged: false };
  let a = lo;
  let b = hi;
  let fa = flo;
  for (let i = 0; i < 200; i += 1) {
    const mid = (a + b) / 2;
    const fm = xnpv(mid);
    if (Math.abs(fm) < 1e-6 || (b - a) < 1e-9) return { xirrPct: mid * 100, converged: true };
    if (fa * fm < 0) { b = mid; } else { a = mid; fa = fm; }
  }
  return { xirrPct: ((a + b) / 2) * 100, converged: true };
}
