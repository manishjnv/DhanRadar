/**
 * Tests for the E5 return-rate engine. Values cross-checked against the
 * closed-form expectations (a 2× over 6y ≈ 12.25%; Rule-of-72 vs the exact log).
 */
import { describe, it, expect } from 'vitest';
import { computeCagr, ruleOf, computeXirr } from './returns';

describe('computeCagr', () => {
  it('a 2× over 6 years is ≈ 12.25% CAGR', () => {
    const r = computeCagr(100000, 200000, 6);
    expect(r.cagrPct).toBeCloseTo(12.246, 2);
    expect(r.absolutePct).toBeCloseTo(100, 6);
    expect(r.doublingYears).toBeCloseTo(6, 4); // doubles in exactly the period
  });

  it('flat value → 0% CAGR and 0% absolute', () => {
    const r = computeCagr(50000, 50000, 5);
    expect(r.cagrPct).toBeCloseTo(0, 6);
    expect(r.absolutePct).toBeCloseTo(0, 6);
    expect(r.doublingYears).toBe(0);
  });

  it('edge inputs (zero begin / zero years) stay finite', () => {
    expect(Number.isFinite(computeCagr(0, 100, 5).cagrPct)).toBe(true);
    expect(Number.isFinite(computeCagr(100, 200, 0).cagrPct)).toBe(true);
    expect(Number.isFinite(computeCagr(NaN, Infinity, -1).cagrPct)).toBe(true);
  });
});

describe('ruleOf', () => {
  it('matches the rule-of-thumb and the exact doubling time (8%)', () => {
    const r = ruleOf(8);
    expect(r.double).toBeCloseTo(9, 6); // 72 / 8
    expect(r.triple).toBeCloseTo(14.25, 6); // 114 / 8
    expect(r.quad).toBeCloseTo(18, 6); // 144 / 8
    expect(r.exactDouble).toBeCloseTo(Math.log(2) / Math.log(1.08), 4); // ≈ 9.006
  });

  it('0% rate → no doubling, finite', () => {
    const r = ruleOf(0);
    expect(r.double).toBe(0);
    expect(Number.isFinite(r.exactDouble)).toBe(true);
  });
});

describe('computeXirr', () => {
  const d = (s: string) => new Date(s);

  it('−1000 then +1100 a year later → 10%', () => {
    const r = computeXirr([
      { date: d('2020-01-01'), amount: -1000 },
      { date: d('2021-01-01'), amount: 1100 },
    ]);
    expect(r.converged).toBe(true);
    expect(r.xirrPct).toBeCloseTo(10, 1);
  });

  it('a monthly SIP series solves to a sensible positive rate', () => {
    const flows = [];
    for (let m = 0; m < 12; m += 1) {
      flows.push({ date: new Date(2023, m, 1), amount: -10000 });
    }
    flows.push({ date: new Date(2023, 11, 31), amount: 126000 }); // redeemed for a small gain
    const r = computeXirr(flows);
    expect(r.converged).toBe(true);
    expect(r.xirrPct).toBeGreaterThan(0);
    expect(r.xirrPct).toBeLessThan(100);
  });

  it('round-trips: XNPV at the solved rate is ~0', () => {
    const flows = [
      { date: d('2019-06-01'), amount: -50000 },
      { date: d('2020-09-01'), amount: -30000 },
      { date: d('2023-01-15'), amount: 110000 },
    ];
    const r = computeXirr(flows);
    const rate = r.xirrPct / 100;
    const t0 = Math.min(...flows.map((f) => f.date.getTime()));
    const xnpv = flows.reduce((s, f) => s + f.amount / Math.pow(1 + rate, (f.date.getTime() - t0) / (365 * 24 * 3600 * 1000)), 0);
    expect(Math.abs(xnpv)).toBeLessThan(1);
  });

  it('all-same-sign or <2 flows → not converged (no garbage)', () => {
    expect(computeXirr([{ date: d('2020-01-01'), amount: -1000 }]).converged).toBe(false);
    expect(computeXirr([
      { date: d('2020-01-01'), amount: -1000 },
      { date: d('2021-01-01'), amount: -500 },
    ]).converged).toBe(false);
  });
});
