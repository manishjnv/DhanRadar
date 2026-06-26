/**
 * Golden tests for the SIP / lump-sum compounding math.
 *
 * Conventions match mainstream Indian calculators (SBI / Groww / Motilal):
 * SIP = monthly annuity DUE, lump sum = ANNUAL compounding. Correctness is
 * cross-checked against an independent reference and against hand/site values.
 */
import { describe, it, expect } from 'vitest';
import { computeSip, formatInr, formatInrShort, MAX_AMOUNT } from './accumulation';

// Independent reference: SIP month-by-month (annuity DUE — contribution at the
// START of each month) + lump sum compounded ANNUALLY.
function refFv(monthlySip: number, lumpSum: number, annualRatePct: number, years: number) {
  const i = annualRatePct / 100 / 12;
  const months = Math.round(years * 12);
  let bal = 0;
  for (let m = 0; m < months; m += 1) bal = (bal + monthlySip) * (1 + i);
  return bal + lumpSum * Math.pow(1 + annualRatePct / 100, years);
}

describe('computeSip — SIP (monthly annuity due)', () => {
  it('matches the independent iterative reference (₹10k/mo, 12%, 10y)', () => {
    const r = computeSip({ monthlySip: 10_000, lumpSum: 0, years: 10, annualRatePct: 12 });
    expect(r.futureValue).toBeCloseTo(refFv(10_000, 0, 12, 10), 2);
  });

  it('matches the site value (₹10k/mo, 12%, 10y ≈ ₹23,23,391 — SBI/Groww)', () => {
    const r = computeSip({ monthlySip: 10_000, lumpSum: 0, years: 10, annualRatePct: 12 });
    expect(Math.round(r.futureValue)).toBeGreaterThan(2_323_200);
    expect(Math.round(r.futureValue)).toBeLessThan(2_323_600);
    expect(r.totalInvested).toBe(1_200_000); // 10k × 120 months
  });

  it('0% rate → pure sum of contributions, no growth', () => {
    const r = computeSip({ monthlySip: 5_000, lumpSum: 0, years: 10, annualRatePct: 0 });
    expect(r.futureValue).toBe(600_000); // 5k × 120
    expect(r.wealthGained).toBe(0);
  });
});

describe('computeSip — lump sum (annual compounding)', () => {
  it("matches SBI/Motilal exactly (₹1L, 13%, 15y → ₹6,25,427)", () => {
    const r = computeSip({ monthlySip: 0, lumpSum: 100_000, years: 15, annualRatePct: 13 });
    expect(Math.round(r.futureValue)).toBeGreaterThan(625_400);
    expect(Math.round(r.futureValue)).toBeLessThan(625_460);
    expect(r.totalInvested).toBe(100_000);
  });

  it('₹1L at 12% for 10y → ₹3,10,585 (annual, not monthly)', () => {
    const r = computeSip({ monthlySip: 0, lumpSum: 100_000, years: 10, annualRatePct: 12 });
    expect(Math.round(r.futureValue)).toBeGreaterThan(310_500);
    expect(Math.round(r.futureValue)).toBeLessThan(310_650);
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

describe('formatInrShort — abbreviations with trailing zeros stripped', () => {
  it('strips trailing zeros and uses no space (₹1L, ₹1.5L, ₹1.23L, ₹82K, ₹6.25Cr)', () => {
    expect(formatInrShort(100_000)).toBe('₹1L');
    expect(formatInrShort(150_000)).toBe('₹1.5L');
    expect(formatInrShort(123_434)).toBe('₹1.23L');
    expect(formatInrShort(80_000)).toBe('₹80K'); // trailing-zero guard: not ₹8K
    expect(formatInrShort(82_000)).toBe('₹82K');
    expect(formatInrShort(12_500_000)).toBe('₹1.25Cr');
    expect(formatInrShort(500)).toBe('₹500');
  });

  it('NaN / Infinity / non-positive → ₹0', () => {
    expect(formatInrShort(NaN)).toBe('₹0');
    expect(formatInrShort(Infinity)).toBe('₹0');
    expect(formatInrShort(0)).toBe('₹0');
    expect(formatInrShort(-100)).toBe('₹0');
  });
});

describe('formatInr — full rupee precision, Indian grouping', () => {
  it('groups in the Indian system and drops paise (₹6,25,427)', () => {
    expect(formatInr(625_427.45)).toBe('₹6,25,427');
    expect(formatInr(2_323_391)).toBe('₹23,23,391');
  });

  it('NaN / Infinity / negative render as ₹0 (never leaks to the DOM)', () => {
    expect(formatInr(NaN)).toBe('₹0');
    expect(formatInr(Infinity)).toBe('₹0');
    expect(formatInr(-100)).toBe('₹0');
  });
});
