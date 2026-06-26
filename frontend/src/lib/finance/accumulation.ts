/**
 * Generic SIP / lump-sum compounding math — PURE, deterministic, golden-tested.
 *
 * This is illustrative compounding arithmetic ONLY. It is NOT a projection by
 * DhanRadar and NOT tied to any fund, score, label, or mood signal. The annual
 * return rate is the USER's own assumption — never an expected or assured value.
 *
 * Convention (documented + consistent across both modes, Goal-Calculator Inv. 12):
 *   everything compounds MONTHLY. i = annualRatePct / 100 / 12, n = years × 12.
 *   - SIP (ordinary annuity, contributions at period end):
 *       FV = P · ((1+i)^n − 1) / i        (i = 0 → FV = P · n)
 *   - Lump sum: FV = L · (1+i)^n
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

/** Future value of a series + lump sum after `months` at monthly rate `i`. */
function compound(monthlySip: number, lumpSum: number, i: number, months: number): number {
  const sipFv = i === 0 ? monthlySip * months : monthlySip * ((Math.pow(1 + i, months) - 1) / i);
  const lumpFv = lumpSum * Math.pow(1 + i, months);
  const fv = sipFv + lumpFv;
  return Number.isFinite(fv) ? fv : 0;
}

/**
 * Compute the illustrative future value for the user's own assumptions.
 * Deterministic: identical inputs always yield identical outputs (Inv. 12).
 */
export function computeSip(input: SipInput): SipResult {
  const monthlySip = clampFinite(input.monthlySip, 0, MAX_AMOUNT);
  const lumpSum = clampFinite(input.lumpSum, 0, MAX_AMOUNT);
  const years = clampFinite(input.years, 0, MAX_YEARS);
  const rate = clampFinite(input.annualRatePct, 0, MAX_RATE_PCT);
  const stepUpPct = clampFinite(input.stepUpPct ?? 0, 0, MAX_STEPUP_PCT);

  const i = rate / 100 / 12;
  const months = Math.round(years * 12);
  const wholeYears = Math.floor(years);

  // ── Flat SIP (no step-up): unchanged closed-form path ──────────────────────
  if (stepUpPct === 0) {
    const futureValue = compound(monthlySip, lumpSum, i, months);
    const totalInvested = monthlySip * months + lumpSum;
    const wealthGained = Math.max(futureValue - totalInvested, 0);

    const series: SipYearPoint[] = [];
    for (let y = 0; y <= wholeYears; y += 1) {
      const m = y * 12;
      series.push({
        year: y,
        invested: monthlySip * m + lumpSum,
        value: compound(monthlySip, lumpSum, i, m),
      });
    }
    return { futureValue, totalInvested, wealthGained, series };
  }

  // ── Step-up SIP: the monthly amount rises by `g` each whole year ───────────
  // Month-by-month accumulation (ordinary annuity, contribution at period end),
  // identical convention to the flat path so the two are directly comparable.
  const g = stepUpPct / 100;
  const sim = (m: number): { fv: number; invested: number } => {
    let bal = lumpSum;
    let invested = lumpSum;
    for (let k = 0; k < m; k += 1) {
      const sip = monthlySip * Math.pow(1 + g, Math.floor(k / 12));
      bal = bal * (1 + i) + sip;
      invested += sip;
    }
    return {
      fv: Number.isFinite(bal) ? bal : 0,
      invested: Number.isFinite(invested) ? invested : 0,
    };
  };

  const full = sim(months);
  const wealthGained = Math.max(full.fv - full.invested, 0);

  const series: SipYearPoint[] = [];
  for (let y = 0; y <= wholeYears; y += 1) {
    const s = sim(y * 12);
    series.push({ year: y, invested: s.invested, value: s.fv });
  }

  return { futureValue: full.fv, totalInvested: full.invested, wealthGained, series };
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
 * Compact rupee formatting for KPI tiles — crore / lakh / thousand abbreviations
 * (e.g. ₹1.25 Cr, ₹45.0 L, ₹17K). Non-finite or non-positive → ₹0 so the DOM
 * never shows NaN / Infinity / -₹. Display-only meaningful rounding (Inv. 7).
 */
export function formatInrShort(amount: number): string {
  if (!Number.isFinite(amount) || amount <= 0) return '₹0';
  if (amount >= 1e7) return `₹${(amount / 1e7).toFixed(2)} Cr`;
  if (amount >= 1e5) return `₹${(amount / 1e5).toFixed(1)} L`;
  if (amount >= 1e3) return `₹${Math.round(amount / 1e3)}K`;
  return `₹${Math.round(amount)}`;
}
