/**
 * Tests for the E2 goal solver. Correctness is cross-checked by round-tripping
 * through E1 (computeSip): the SIP/lump the solver returns must, when fed back
 * into the accumulation engine, actually reach the target.
 */
import { describe, it, expect } from 'vitest';
import { solveGoal } from './goal';
import { computeSip } from './accumulation';

describe('solveGoal — E2 goal solver', () => {
  it('round-trips with E1: the required SIP reaches the target', () => {
    const target = 5_000_000, years = 15, rate = 12;
    const r = solveGoal({ targetToday: target, years, annualRatePct: rate });
    const fv = computeSip({ monthlySip: r.requiredMonthly, lumpSum: 0, years, annualRatePct: rate }).futureValue;
    expect(fv).toBeCloseTo(target, -1); // within ~₹5 of the target
  });

  it('the required lump sum grows back to the target', () => {
    const target = 2_000_000, years = 10, rate = 11;
    const r = solveGoal({ targetToday: target, years, annualRatePct: rate });
    const fv = computeSip({ monthlySip: 0, lumpSum: r.requiredLump, years, annualRatePct: rate }).futureValue;
    expect(fv).toBeCloseTo(target, -1);
  });

  it('inflation raises both the future cost and the required SIP', () => {
    const base = { targetToday: 3_000_000, years: 12, annualRatePct: 12 };
    const noInfl = solveGoal(base);
    const withInfl = solveGoal({ ...base, inflationPct: 7 });
    expect(withInfl.inflatedTarget).toBeGreaterThan(noInfl.inflatedTarget);
    expect(withInfl.requiredMonthly).toBeGreaterThan(noInfl.requiredMonthly);
  });

  it('current savings reduces the required SIP and can zero it out', () => {
    const base = { targetToday: 1_000_000, years: 10, annualRatePct: 12 };
    expect(solveGoal({ ...base, currentSavings: 200_000 }).requiredMonthly)
      .toBeLessThan(solveGoal(base).requiredMonthly);
    const covered = solveGoal({ ...base, currentSavings: 5_000_000 });
    expect(covered.shortfall).toBe(0);
    expect(covered.requiredMonthly).toBe(0);
  });

  it('0% rate → required SIP is a simple split of the target', () => {
    const r = solveGoal({ targetToday: 1_200_000, years: 10, annualRatePct: 0 });
    expect(r.requiredMonthly).toBeCloseTo(1_200_000 / 120, 4); // target / months
  });

  it('a longer horizon needs a smaller monthly SIP', () => {
    const base = { targetToday: 4_000_000, annualRatePct: 12 };
    expect(solveGoal({ ...base, years: 20 }).requiredMonthly)
      .toBeLessThan(solveGoal({ ...base, years: 10 }).requiredMonthly);
  });

  it('edge inputs stay finite (never NaN / Infinity)', () => {
    const r = solveGoal({ targetToday: -5, years: -1, annualRatePct: 999, inflationPct: 999, currentSavings: NaN });
    for (const v of Object.values(r)) expect(Number.isFinite(v)).toBe(true);
  });
});
