/**
 * Tests for FD / RD / PPF. Cross-checked against the standard formulas and the
 * usual bank / Post-Office values.
 */
import { describe, it, expect } from 'vitest';
import { computeFd, computeRd, computePpf } from './scheme';

describe('computeFd', () => {
  it('₹1L at 7% for 5y, quarterly → ≈ ₹1,41,478', () => {
    const r = computeFd(100000, 7, 5, 4);
    expect(Math.round(r.maturity)).toBeGreaterThan(141400);
    expect(Math.round(r.maturity)).toBeLessThan(141550);
    expect(r.invested).toBe(100000);
  });

  it('0% → maturity equals principal, no interest', () => {
    const r = computeFd(100000, 0, 5, 4);
    expect(r.maturity).toBe(100000);
    expect(r.interest).toBe(0);
  });
});

describe('computeRd', () => {
  it('₹5,000/mo at 7% for 5y → more than ₹3 L deposited, positive interest', () => {
    const r = computeRd(5000, 7, 5);
    expect(r.invested).toBe(300000);
    expect(r.maturity).toBeGreaterThan(300000);
    expect(r.interest).toBeGreaterThan(0);
  });

  it('₹5,000/mo at 8% for 1y ≈ ₹62,600 (bank RD)', () => {
    const r = computeRd(5000, 8, 1);
    expect(Math.round(r.maturity)).toBeGreaterThan(62300);
    expect(Math.round(r.maturity)).toBeLessThan(62900);
  });

  it('a higher rate gives a higher maturity', () => {
    expect(computeRd(5000, 8, 5).maturity).toBeGreaterThan(computeRd(5000, 6, 5).maturity);
  });
});

describe('computePpf', () => {
  it('₹1.5 L/yr at 7.1% for 15y → ≈ ₹40.68 L', () => {
    const r = computePpf(150000, 7.1, 15);
    expect(Math.round(r.maturity)).toBeGreaterThan(4000000);
    expect(Math.round(r.maturity)).toBeLessThan(4150000);
    expect(r.invested).toBe(2250000); // 1.5L × 15
  });

  it('0% → maturity equals total deposited', () => {
    const r = computePpf(100000, 0, 15);
    expect(r.maturity).toBe(1500000);
    expect(r.interest).toBe(0);
  });
});

describe('scheme — edges stay finite', () => {
  it('NaN / negative inputs', () => {
    for (const r of [computeFd(NaN, 999, -1), computeRd(NaN, 999, -1), computePpf(NaN, 999, -1)]) {
      expect(Number.isFinite(r.maturity)).toBe(true);
      expect(Number.isFinite(r.interest)).toBe(true);
    }
  });
});
