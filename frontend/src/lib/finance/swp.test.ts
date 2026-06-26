/**
 * Tests for the E3 SWP / withdrawal engine. Checks the sustainability boundary
 * (W ≤ corpus·i never depletes), the 0%-rate split, and monotonic behaviour.
 */
import { describe, it, expect } from 'vitest';
import { computeSwp, SWP_MAX_MONTHS } from './swp';

describe('computeSwp', () => {
  it('withdrawing only the interest is sustainable (never depletes)', () => {
    const corpus = 10_000_000;
    const rate = 8;
    const sustainableMonthly = Math.floor((corpus * rate) / 100 / 12) - 100; // just under interest
    const r = computeSwp({ corpus, monthlyWithdrawal: sustainableMonthly, annualRatePct: rate });
    expect(r.sustainable).toBe(true);
    expect(r.monthsLasted).toBe(SWP_MAX_MONTHS);
  });

  it('withdrawing more than the interest depletes the corpus in finite time', () => {
    const r = computeSwp({ corpus: 10_000_000, monthlyWithdrawal: 100_000, annualRatePct: 8 });
    expect(r.sustainable).toBe(false);
    expect(r.monthsLasted).toBeGreaterThan(0);
    expect(r.monthsLasted).toBeLessThan(SWP_MAX_MONTHS);
  });

  it('0% return → corpus / withdrawal months', () => {
    const r = computeSwp({ corpus: 1_200_000, monthlyWithdrawal: 10_000, annualRatePct: 0 });
    expect(r.monthsLasted).toBe(120);
    expect(r.sustainable).toBe(false);
  });

  it('a bigger withdrawal depletes the corpus sooner', () => {
    const small = computeSwp({ corpus: 5_000_000, monthlyWithdrawal: 40_000, annualRatePct: 7 });
    const big = computeSwp({ corpus: 5_000_000, monthlyWithdrawal: 60_000, annualRatePct: 7 });
    expect(big.monthsLasted).toBeLessThan(small.monthsLasted);
  });

  it('inflation-indexed withdrawals deplete faster than flat', () => {
    const flat = computeSwp({ corpus: 5_000_000, monthlyWithdrawal: 35_000, annualRatePct: 8 });
    const indexed = computeSwp({ corpus: 5_000_000, monthlyWithdrawal: 35_000, annualRatePct: 8, inflationPct: 6 });
    expect(indexed.monthsLasted).toBeLessThanOrEqual(flat.monthsLasted);
  });

  it('edge inputs stay finite', () => {
    const r = computeSwp({ corpus: NaN, monthlyWithdrawal: -5, annualRatePct: 999, inflationPct: 999 });
    expect(Number.isFinite(r.monthsLasted)).toBe(true);
    expect(Number.isFinite(r.totalWithdrawn)).toBe(true);
    for (const p of r.series) expect(Number.isFinite(p.balance)).toBe(true);
  });
});
