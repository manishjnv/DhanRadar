/**
 * Golden tests for the SIP / lump-sum compounding math.
 *
 * Correctness is cross-checked two ways: the closed-form result from computeSip()
 * is compared against an INDEPENDENT month-by-month iterative accumulation, and
 * against hand-computed reference values. Edge inputs must never produce NaN or
 * Infinity (Goal-Calculator Inv. 6/9).
 */
import { describe, it, expect } from 'vitest';
import { computeSip, formatInr, MAX_AMOUNT } from './sip-math';

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
