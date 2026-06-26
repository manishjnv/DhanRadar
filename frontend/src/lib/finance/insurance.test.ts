/**
 * Tests for the E10 insurance need estimators. Indicative figures only — these
 * check the math (PV annuity, needs gap, inflation band), not a product pick.
 */
import { describe, it, expect } from 'vitest';
import { computeHlv, computeTermCover, computeHealthCover, INSURANCE_CONFIG } from './insurance';

describe('computeHlv', () => {
  it('0% discount → income × working years', () => {
    const r = computeHlv({ annualIncome: 1200000, currentAge: 30, retirementAge: 60, discountRatePct: 0 });
    expect(r.workingYears).toBe(30);
    expect(r.hlv).toBe(1200000 * 30);
    expect(r.multiplierCheck).toBe(1200000 * INSURANCE_CONFIG.hlvIncomeMultiplier);
  });

  it('a positive discount makes HLV less than the undiscounted sum', () => {
    const r = computeHlv({ annualIncome: 1200000, currentAge: 30, retirementAge: 60, discountRatePct: 5 });
    expect(r.hlv).toBeLessThan(1200000 * 30);
    expect(r.hlv).toBeGreaterThan(0);
  });

  it('existing cover reduces the gap', () => {
    const r = computeHlv({ annualIncome: 1000000, currentAge: 35, retirementAge: 60, discountRatePct: 4, existingCover: 5000000 });
    expect(r.coverGap).toBe(Math.max(r.hlv - 5000000, 0));
  });

  it('NaN inputs stay finite', () => {
    const r = computeHlv({ annualIncome: NaN, currentAge: -1, retirementAge: NaN, discountRatePct: NaN });
    for (const v of [r.hlv, r.multiplierCheck, r.coverGap]) expect(Number.isFinite(v)).toBe(true);
  });
});

describe('computeTermCover', () => {
  it('gap = income replacement + loans + goals − existing assets', () => {
    const r = computeTermCover({ annualIncome: 1200000, yearsToCover: 20, discountRatePct: 0, outstandingLoans: 3000000, futureGoals: 2000000, existingCoverAssets: 5000000 });
    expect(r.incomeReplacement).toBe(1200000 * 20);
    expect(r.totalNeed).toBe(1200000 * 20 + 3000000 + 2000000);
    expect(r.gap).toBe(r.totalNeed - 5000000);
  });

  it('existing assets above the need → zero gap (never negative)', () => {
    const r = computeTermCover({ annualIncome: 500000, yearsToCover: 5, discountRatePct: 0, outstandingLoans: 0, futureGoals: 0, existingCoverAssets: 100000000 });
    expect(r.gap).toBe(0);
  });

  it('NaN inputs stay finite', () => {
    const r = computeTermCover({ annualIncome: NaN, yearsToCover: -1, discountRatePct: NaN, outstandingLoans: NaN, futureGoals: NaN, existingCoverAssets: NaN });
    for (const v of [r.incomeReplacement, r.totalNeed, r.gap]) expect(Number.isFinite(v)).toBe(true);
  });
});

describe('computeHealthCover', () => {
  it('tier-1 single person today → the tier base', () => {
    const r = computeHealthCover({ cityTier: 1, familySize: 1, horizonYears: 0 });
    expect(r.baseCover).toBe(INSURANCE_CONFIG.healthBaseByTier[1]);
    expect(r.indicativeCover).toBe(r.baseCover);
    expect(r.bandLow).toBeLessThan(r.indicativeCover);
    expect(r.bandHigh).toBeGreaterThan(r.indicativeCover);
  });

  it('more family members raise the base cover', () => {
    const solo = computeHealthCover({ cityTier: 2, familySize: 1, horizonYears: 0 });
    const family = computeHealthCover({ cityTier: 2, familySize: 4, horizonYears: 0 });
    expect(family.baseCover).toBeGreaterThan(solo.baseCover);
  });

  it('medical inflation grows the cover over the horizon', () => {
    const now = computeHealthCover({ cityTier: 1, familySize: 2, horizonYears: 0 });
    const later = computeHealthCover({ cityTier: 1, familySize: 2, horizonYears: 10 });
    expect(later.indicativeCover).toBeGreaterThan(now.indicativeCover);
  });

  it('NaN inputs stay finite', () => {
    const r = computeHealthCover({ cityTier: NaN, familySize: -3, horizonYears: NaN });
    for (const v of [r.baseCover, r.indicativeCover, r.bandLow, r.bandHigh]) expect(Number.isFinite(v)).toBe(true);
  });
});
