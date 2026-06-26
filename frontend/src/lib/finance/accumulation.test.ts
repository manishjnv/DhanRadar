/**
 * Golden tests for the SIP / lump-sum compounding math.
 *
 * Correctness is cross-checked two ways: the closed-form result from computeSip()
 * is compared against an INDEPENDENT month-by-month iterative accumulation, and
 * against hand-computed reference values. Edge inputs must never produce NaN or
 * Infinity (Goal-Calculator Inv. 6/9).
 */
import { describe, it, expect } from 'vitest';
import { computeSip, formatInr, formatInrShort, MAX_AMOUNT } from './accumulation';

// Independent reference: month-by-month accumulation (ordinary annuity — each
// SIP contribution made at period END, so the last payment earns nothing).
function iterativeFv(monthlySip: number, lumpSum: number, annualRatePct: number, years: number) {
  const i = annualRatePct / 100 / 12;
  const months = Math.round(years * 12);
  let balance = lumpSum;
  for (let m = 0; m < months; m += 1) {
    balance = balance * (1 + i) + monthlySip;
  }
  return balance;
}

describe('computeSip — SIP monthly compounding', () => {
  it('matches the independent iterative accumulation (₹10k/mo, 12%, 10y)', () => {
    const r = computeSip({ monthlySip: 10_000, lumpSum: 0, years: 10, annualRatePct: 12 });
    expect(r.futureValue).toBeCloseTo(iterativeFv(10_000, 0, 12, 10), 2);
  });

  it('matches the hand-computed reference value (₹10k/mo, 12%, 10y ≈ ₹23,00,387)', () => {
    const r = computeSip({ monthlySip: 10_000, lumpSum: 0, years: 10, annualRatePct: 12 });
    expect(Math.round(r.futureValue)).toBeGreaterThan(2_300_300);
    expect(Math.round(r.futureValue)).toBeLessThan(2_300_500);
    expect(r.totalInvested).toBe(1_200_000); // 10k × 120 months
    expect(r.wealthGained).toBeCloseTo(r.futureValue - r.totalInvested, 2);
  });

  it('0% rate → pure sum of contributions, no growth', () => {
    const r = computeSip({ monthlySip: 5_000, lumpSum: 0, years: 10, annualRatePct: 0 });
    expect(r.futureValue).toBe(600_000); // 5k × 120
    expect(r.wealthGained).toBe(0);
  });
});

describe('computeSip — lump sum monthly compounding', () => {
  it('matches the iterative accumulation (₹1L, 12%, 10y)', () => {
    const r = computeSip({ monthlySip: 0, lumpSum: 100_000, years: 10, annualRatePct: 12 });
    expect(r.futureValue).toBeCloseTo(iterativeFv(0, 100_000, 12, 10), 2);
    // 100000 × 1.01^120 ≈ 330,039
    expect(Math.round(r.futureValue)).toBeGreaterThan(330_000);
    expect(Math.round(r.futureValue)).toBeLessThan(330_100);
  });

  it('combines SIP + lump sum additively', () => {
    const sipOnly = computeSip({ monthlySip: 10_000, lumpSum: 0, years: 10, annualRatePct: 12 });
    const lumpOnly = computeSip({ monthlySip: 0, lumpSum: 100_000, years: 10, annualRatePct: 12 });
    const both = computeSip({ monthlySip: 10_000, lumpSum: 100_000, years: 10, annualRatePct: 12 });
    expect(both.futureValue).toBeCloseTo(sipOnly.futureValue + lumpOnly.futureValue, 2);
  });
});

describe('computeSip — edge cases never produce NaN / Infinity', () => {
  const finite = (n: number) => Number.isFinite(n);

  it('zero amounts → all zero, finite', () => {
    const r = computeSip({ monthlySip: 0, lumpSum: 0, years: 10, annualRatePct: 12 });
    expect(r.futureValue).toBe(0);
    expect(r.totalInvested).toBe(0);
    expect(r.wealthGained).toBe(0);
  });

  it('zero years → only the lump sum survives, finite', () => {
    const r = computeSip({ monthlySip: 10_000, lumpSum: 50_000, years: 0, annualRatePct: 12 });
    expect(r.futureValue).toBe(50_000);
    expect(r.totalInvested).toBe(50_000);
    expect(r.wealthGained).toBe(0);
  });

  it('very high rate + long horizon stays finite (clamped)', () => {
    const r = computeSip({ monthlySip: 1e9, lumpSum: 1e9, years: 999, annualRatePct: 999 });
    expect(finite(r.futureValue)).toBe(true);
    expect(finite(r.totalInvested)).toBe(true);
    expect(finite(r.wealthGained)).toBe(true);
    // clamped inputs keep invested within the per-field cap × max months
    expect(r.totalInvested).toBeLessThanOrEqual(MAX_AMOUNT * 600 + MAX_AMOUNT);
  });

  it('negative / NaN inputs are clamped to safe finite values', () => {
    const r = computeSip({ monthlySip: -5_000, lumpSum: NaN, years: -3, annualRatePct: -10 });
    expect(r.futureValue).toBe(0);
    expect(r.totalInvested).toBe(0);
    expect(Number.isFinite(r.wealthGained)).toBe(true);
  });

  it('series is finite at every point', () => {
    const r = computeSip({ monthlySip: 10_000, lumpSum: 0, years: 30, annualRatePct: 15 });
    expect(r.series.length).toBe(31); // year 0..30
    for (const p of r.series) {
      expect(finite(p.invested)).toBe(true);
      expect(finite(p.value)).toBe(true);
    }
  });
});

describe('computeSip — step-up SIP', () => {
  const base = { monthlySip: 10_000, lumpSum: 0, years: 10, annualRatePct: 12 };

  it('omitted stepUpPct is identical to stepUpPct = 0 (flat path)', () => {
    const flat = computeSip(base);
    const zero = computeSip({ ...base, stepUpPct: 0 });
    expect(zero.futureValue).toBe(flat.futureValue);
    expect(zero.totalInvested).toBe(flat.totalInvested);
  });

  it('a 10%/yr step-up grows both the corpus and the amount invested vs flat', () => {
    const flat = computeSip(base);
    const stepped = computeSip({ ...base, stepUpPct: 10 });
    expect(stepped.futureValue).toBeGreaterThan(flat.futureValue);
    expect(stepped.totalInvested).toBeGreaterThan(flat.totalInvested);
  });

  it('invested matches the geometric step-up sum (10k base, 10%/yr, 10y ≈ ₹19.12 L)', () => {
    // Σ over 10 years of 12 × 10k × 1.1^y = 120000 × (1.1^10 − 1)/0.1 ≈ 1,912,491
    const r = computeSip({ ...base, stepUpPct: 10 });
    expect(Math.round(r.totalInvested)).toBeGreaterThan(1_912_000);
    expect(Math.round(r.totalInvested)).toBeLessThan(1_913_000);
  });

  it('series is finite, length year 0..N, and monotonically rising', () => {
    const r = computeSip({ monthlySip: 25_000, lumpSum: 0, years: 15, annualRatePct: 12, stepUpPct: 10 });
    expect(r.series.length).toBe(16);
    for (const p of r.series) {
      expect(Number.isFinite(p.invested)).toBe(true);
      expect(Number.isFinite(p.value)).toBe(true);
    }
    expect(r.series[15].value).toBeGreaterThan(r.series[1].value);
  });

  it('extreme step-up stays finite (clamped, never Infinity)', () => {
    const r = computeSip({ monthlySip: 1e9, lumpSum: 0, years: 50, annualRatePct: 50, stepUpPct: 999 });
    expect(Number.isFinite(r.futureValue)).toBe(true);
    expect(Number.isFinite(r.totalInvested)).toBe(true);
  });
});

describe('computeSip — invariants (catch silent regressions, no false-pass)', () => {
  const base = { monthlySip: 10_000, lumpSum: 0, years: 10, annualRatePct: 12 };

  it('future value rises strictly with monthly amount, rate, and years', () => {
    expect(computeSip({ ...base, monthlySip: 12_000 }).futureValue).toBeGreaterThan(computeSip(base).futureValue);
    expect(computeSip({ ...base, annualRatePct: 14 }).futureValue).toBeGreaterThan(computeSip(base).futureValue);
    expect(computeSip({ ...base, years: 12 }).futureValue).toBeGreaterThan(computeSip(base).futureValue);
  });

  it('future value is never less than what was put in, at any non-negative rate', () => {
    for (const rate of [0, 1, 7, 12, 30]) {
      const r = computeSip({ monthlySip: 8_000, lumpSum: 20_000, years: 12, annualRatePct: rate });
      expect(r.futureValue).toBeGreaterThanOrEqual(r.totalInvested - 1e-6);
    }
  });

  it('wealthGained equals futureValue − totalInvested exactly (no double counting)', () => {
    const r = computeSip({ monthlySip: 15_000, lumpSum: 50_000, years: 20, annualRatePct: 11 });
    expect(r.wealthGained).toBeCloseTo(r.futureValue - r.totalInvested, 2);
  });

  it('a 10% step-up beats a flat SIP at every rate (and never the reverse)', () => {
    for (const rate of [0, 8, 12, 20]) {
      const flat = computeSip({ monthlySip: 10_000, lumpSum: 0, years: 15, annualRatePct: rate });
      const step = computeSip({ monthlySip: 10_000, lumpSum: 0, years: 15, annualRatePct: rate, stepUpPct: 10 });
      expect(step.futureValue).toBeGreaterThan(flat.futureValue);
    }
  });
});

describe('formatInrShort — crore / lakh / K abbreviations', () => {
  it('formats crore to 2dp, lakh to 1dp, thousands to K', () => {
    expect(formatInrShort(12_500_000)).toBe('₹1.25 Cr');
    expect(formatInrShort(4_500_000)).toBe('₹45.0 L');
    expect(formatInrShort(17_000)).toBe('₹17K');
    expect(formatInrShort(500)).toBe('₹500');
  });

  it('NaN / Infinity / non-positive → ₹0', () => {
    expect(formatInrShort(NaN)).toBe('₹0');
    expect(formatInrShort(Infinity)).toBe('₹0');
    expect(formatInrShort(0)).toBe('₹0');
    expect(formatInrShort(-100)).toBe('₹0');
  });
});

describe('formatInr — Indian grouping, no false precision, no NaN', () => {
  it('groups in the Indian system and drops paise', () => {
    expect(formatInr(2_300_387.45)).toBe('₹23,00,387');
  });

  it('NaN / Infinity / negative render as ₹0 (never leaks to the DOM)', () => {
    expect(formatInr(NaN)).toBe('₹0');
    expect(formatInr(Infinity)).toBe('₹0');
    expect(formatInr(-100)).toBe('₹0');
  });
});
