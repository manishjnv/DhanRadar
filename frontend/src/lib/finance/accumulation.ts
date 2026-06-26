/**
 * Generic SIP / lump-sum compounding math — PURE, deterministic, golden-tested.
 *
 * This is illustrative compounding arithmetic ONLY. It is NOT a projection by
 * DhanRadar and NOT tied to any fund, score, label, or mood signal. The annual
 * return rate is the USER's own assumption — never an expected or assured value.
 *
 * Convention — matches mainstream Indian calculators (SBI / Groww / Motilal):
 *   - SIP: MONTHLY, annuity DUE (contribution at the START of each month).
 *       FV = P · ((1+i)^n − 1) / i · (1+i),  i = annualRatePct/100/12, n = years×12
 *       (i = 0 → FV = P · n)
 *   - Lump sum: ANNUAL compounding.  FV = L · (1 + annualRatePct/100)^years
 *
 * All inputs are clamped to sane finite ranges so the result can never be NaN or
 * Infinity (Goal-Calculator Inv. 9) — a bad input yields a safe finite number,
 * never garbage in the DOM.
 */

export interface SipInput {
  /** Monthly SIP contribution in ₹ (≥ 0). */
  monthlySip: number;
  /** One-time lump-sum investment in ₹ (≥ 0). */
  lumpSum: number;
  /** Duration in years (0–50). */
  years: number;
  /** USER-CHOSEN assumed annual return %, 0–50 — not a DhanRadar prediction. */
  annualRatePct: number;
  /** Optional annual SIP step-up % (raise the monthly amount each year), 0–50. Default 0. */
  stepUpPct?: number;
}

export interface SipYearPoint {
  year: number;
  invested: number;
  value: number;
}

export interface SipResult {
  futureValue: number;
  totalInvested: number;
  wealthGained: number;
  /** Year-by-year invested vs projected value, for the illustrative chart. */
  series: SipYearPoint[];
}

// Sane finite bounds — keep every computed figure finite (no Infinity in DOM).
export const MAX_YEARS = 50;
export const MAX_RATE_PCT = 50;
export const MAX_STEPUP_PCT = 50; // cap the annual SIP step-up so the loop can never blow up
export const MAX_AMOUNT = 1_000_000_000; // ₹100 cr cap on a single input field

/** Coerce any value to a finite number in [min, max]; NaN/Infinity → min. */
function clampFinite(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}

/**
 * Compute the illustrative future value for the user's own assumptions.
 * Deterministic: identical inputs always yield identical outputs.
 *
 * SIP compounds monthly (annuity due); the lump sum compounds annually — the
 * conventions mainstream Indian calculators use, so the numbers match SBI/Groww.
 */
export function computeSip(input: SipInput): SipResult {
  const monthlySip = clampFinite(input.monthlySip, 0, MAX_AMOUNT);
  const lumpSum = clampFinite(input.lumpSum, 0, MAX_AMOUNT);
  const years = clampFinite(input.years, 0, MAX_YEARS);
  const rate = clampFinite(input.annualRatePct, 0, MAX_RATE_PCT);
  const stepUpPct = clampFinite(input.stepUpPct ?? 0, 0, MAX_STEPUP_PCT);

  const i = rate / 100 / 12; // monthly rate (SIP)
  const annual = rate / 100; // annual rate (lump sum)
  const g = stepUpPct / 100;
  const n = Math.round(years * 12);
  const wholeYears = Math.floor(years);

  // Lump sum — ANNUAL compounding: L · (1 + annual)^t.
  const lumpAt = (yearsElapsed: number): number => {
    const fv = lumpSum * Math.pow(1 + annual, yearsElapsed);
    return Number.isFinite(fv) ? fv : 0;
  };

  // SIP — MONTHLY, annuity DUE (contribution at the start of each month).
  const sipAt = (months: number): number => {
    if (months <= 0) return 0;
    if (g === 0) {
      const fv = i === 0
        ? monthlySip * months
        : monthlySip * ((Math.pow(1 + i, months) - 1) / i) * (1 + i);
      return Number.isFinite(fv) ? fv : 0;
    }
    // Step-up: month-by-month (annuity due), amount rises by g each whole year.
    let bal = 0;
    for (let k = 0; k < months; k += 1) {
      const sip = monthlySip * Math.pow(1 + g, Math.floor(k / 12));
      bal = (bal + sip) * (1 + i);
    }
    return Number.isFinite(bal) ? bal : 0;
  };

  const investedAt = (months: number): number => {
    if (g === 0) return monthlySip * months;
    let inv = 0;
    for (let k = 0; k < months; k += 1) inv += monthlySip * Math.pow(1 + g, Math.floor(k / 12));
    return Number.isFinite(inv) ? inv : 0;
  };

  const futureValue = sipAt(n) + lumpAt(years);
  const totalInvested = investedAt(n) + lumpSum;
  const wealthGained = Math.max(futureValue - totalInvested, 0);

  const series: SipYearPoint[] = [];
  for (let y = 0; y <= wholeYears; y += 1) {
    series.push({
      year: y,
      invested: investedAt(y * 12) + lumpSum,
      value: sipAt(y * 12) + lumpAt(y),
    });
  }

  return { futureValue, totalInvested, wealthGained, series };
}

/**
 * Format a rupee amount with Indian digit grouping and NO paise (meaningful
 * rounding only — no false precision, Goal-Calculator Inv. 7). Non-finite or
 * negative inputs render as ₹0 so the DOM never shows NaN / Infinity / -₹.
 */
export function formatInr(amount: number): string {
  const safe = Number.isFinite(amount) && amount > 0 ? Math.round(amount) : 0;
  return `₹${safe.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

/**
 * Compact rupee formatting for tables / chart axes — crore / lakh / thousand
 * abbreviations with trailing zeros stripped for consistency: ₹1L (not ₹1.0L),
 * ₹1.5L (not ₹1.50L), ₹1.23L, ₹82K, ₹6.25Cr. Non-finite / non-positive → ₹0.
 */
export function formatInrShort(amount: number): string {
  if (!Number.isFinite(amount) || amount <= 0) return '₹0';
  // toFixed then drop trailing zeros ONLY after a decimal point (never "80"→"8").
  const trim = (n: number, dp: number): string => {
    let s = n.toFixed(dp);
    if (s.includes('.')) s = s.replace(/0+$/, '').replace(/\.$/, '');
    return s;
  };
  if (amount >= 1e7) return `₹${trim(amount / 1e7, 2)}Cr`;
  if (amount >= 1e5) return `₹${trim(amount / 1e5, 2)}L`;
  if (amount >= 1e3) return `₹${trim(amount / 1e3, 0)}K`;
  return `₹${Math.round(amount)}`;
}
