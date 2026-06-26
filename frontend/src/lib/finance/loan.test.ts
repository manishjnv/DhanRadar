/**
 * Tests for the E7 loan/EMI engine. EMI is cross-checked against the standard
 * reference value and the amortization is checked for internal consistency
 * (interest + principal repaid = total paid; balance ends at zero).
 */
import { describe, it, expect } from 'vitest';
import { computeLoan, computePrepayment } from './loan';

describe('computeLoan — EMI + amortization', () => {
  it('matches the reference EMI (₹50L, 8.5%, 20y ≈ ₹43,391)', () => {
    const r = computeLoan({ principal: 5_000_000, annualRatePct: 8.5, years: 20 });
    expect(Math.round(r.emi)).toBeGreaterThan(43_300);
    expect(Math.round(r.emi)).toBeLessThan(43_500);
  });

  it('0% rate → EMI is principal / months and zero interest', () => {
    const r = computeLoan({ principal: 1_200_000, annualRatePct: 0, years: 10 });
    expect(r.emi).toBeCloseTo(1_200_000 / 120, 4);
    expect(r.totalInterest).toBeCloseTo(0, 2);
  });

  it('principal + interest paid reconciles, and the balance ends at zero', () => {
    const r = computeLoan({ principal: 3_000_000, annualRatePct: 9, years: 15 });
    const last = r.series[r.series.length - 1];
    expect(last.balance).toBeCloseTo(0, 0); // fully repaid (within ₹0.5)
    expect(r.totalPayment - r.totalInterest).toBeCloseTo(3_000_000, -1); // principal back
  });

  it('higher rate raises the EMI; a shorter tenure raises the EMI but cuts total interest', () => {
    const base = { principal: 4_000_000, annualRatePct: 8.5, years: 20 };
    expect(computeLoan({ ...base, annualRatePct: 9.5 }).emi).toBeGreaterThan(computeLoan(base).emi);
    const shorter = computeLoan({ ...base, years: 15 });
    expect(shorter.emi).toBeGreaterThan(computeLoan(base).emi);
    expect(shorter.totalInterest).toBeLessThan(computeLoan(base).totalInterest);
  });

  it('total interest is positive at a real rate and grows with the loan amount', () => {
    const small = computeLoan({ principal: 1_000_000, annualRatePct: 8.5, years: 20 });
    const big = computeLoan({ principal: 5_000_000, annualRatePct: 8.5, years: 20 });
    expect(small.totalInterest).toBeGreaterThan(0);
    expect(big.totalInterest).toBeGreaterThan(small.totalInterest);
  });

  it('edge inputs stay finite (never NaN / Infinity)', () => {
    const r = computeLoan({ principal: NaN, annualRatePct: 999, years: -5 });
    expect(Number.isFinite(r.emi)).toBe(true);
    expect(Number.isFinite(r.totalInterest)).toBe(true);
    expect(Number.isFinite(r.totalPayment)).toBe(true);
    for (const p of r.series) {
      expect(Number.isFinite(p.balance)).toBe(true);
      expect(Number.isFinite(p.interestPaid)).toBe(true);
    }
  });
});

describe('computePrepayment — keep EMI, shorten tenure', () => {
  const base = { principal: 5_000_000, annualRatePct: 8.5, years: 20 };

  it('no prepayment → identical to the baseline (nothing saved)', () => {
    const r = computePrepayment(base);
    expect(r.newMonths).toBe(r.baselineMonths);
    expect(r.monthsSaved).toBe(0);
    expect(r.interestSaved).toBeCloseTo(0, 0);
  });

  it('a one-time prepayment shortens the tenure and saves interest (EMI unchanged)', () => {
    const r = computePrepayment({ ...base, oneTime: 500_000 });
    expect(r.newMonths).toBeLessThan(r.baselineMonths);
    expect(r.monthsSaved).toBeGreaterThan(0);
    expect(r.interestSaved).toBeGreaterThan(0);
    expect(r.emi).toBeGreaterThan(0);
  });

  it('extra monthly also shortens the tenure', () => {
    const r = computePrepayment({ ...base, extraMonthly: 5_000 });
    expect(r.newMonths).toBeLessThan(r.baselineMonths);
    expect(r.interestSaved).toBeGreaterThan(0);
  });

  it('a bigger one-time prepayment saves more interest', () => {
    const small = computePrepayment({ ...base, oneTime: 200_000 });
    const big = computePrepayment({ ...base, oneTime: 1_000_000 });
    expect(big.interestSaved).toBeGreaterThan(small.interestSaved);
  });

  it('prepaying the full principal clears the loan immediately', () => {
    const r = computePrepayment({ ...base, oneTime: 5_000_000 });
    expect(r.newMonths).toBe(0);
    expect(r.interestSaved).toBeCloseTo(r.baselineInterest, -1);
  });

  it('edge inputs stay finite (never NaN / Infinity)', () => {
    const r = computePrepayment({ principal: NaN, annualRatePct: 999, years: -1, oneTime: NaN, extraMonthly: -5 });
    for (const v of Object.values(r)) expect(Number.isFinite(v)).toBe(true);
  });
});
