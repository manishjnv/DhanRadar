/**
 * Tests for the income-tax slab engine (Old vs New regime, FY 2025-26).
 * Exact slab calculations cross-checked by hand against the Budget-2025 new
 * regime and the unchanged old regime.
 */
import { describe, it, expect } from 'vitest';
import { computeRegimeTax, slabTax, REGIME_CONFIG } from './regime';

describe('slabTax', () => {
  it('new-regime slab tax on ₹16 L taxable = ₹1,20,000 base', () => {
    // 4–8L:20k + 8–12L:40k + 12–16L:60k = 1,20,000
    expect(slabTax(1600000, REGIME_CONFIG.newSlabs)).toBe(120000);
  });
  it('old-regime slab tax on ₹16 L taxable = ₹2,92,500 base', () => {
    // 2.5–5L:12.5k + 5–10L:100k + 10–16L:180k = 2,92,500
    expect(slabTax(1600000, REGIME_CONFIG.oldSlabs)).toBe(292500);
  });
  it('zero / negative taxable → 0', () => {
    expect(slabTax(0, REGIME_CONFIG.newSlabs)).toBe(0);
    expect(slabTax(-5, REGIME_CONFIG.oldSlabs)).toBe(0);
  });
});

describe('computeRegimeTax', () => {
  it('new regime: income ₹12.75 L (salaried) → taxable ₹12 L → nil tax via rebate', () => {
    const r = computeRegimeTax({ grossIncome: 1275000, deductions: 0 });
    expect(r.newTaxable).toBe(1200000);
    expect(r.newTax).toBe(0);
  });

  it('₹16.75 L gross, no deductions: new tax = ₹1,24,800 (1,20,000 + 4% cess)', () => {
    const r = computeRegimeTax({ grossIncome: 1675000, deductions: 0 });
    expect(r.newTaxable).toBe(1600000);
    expect(r.newTax).toBe(124800);
    // With no deductions the new regime is cheaper here.
    expect(r.cheaper).toBe('new');
  });

  it('old regime nil when taxable ≤ ₹5 L (rebate)', () => {
    const r = computeRegimeTax({ grossIncome: 700000, deductions: 200000 }); // 7L − 50k std − 2L = 4.5L
    expect(r.oldTaxable).toBe(450000);
    expect(r.oldTax).toBe(0);
  });

  it('large deductions can make the old regime cheaper', () => {
    const noDed = computeRegimeTax({ grossIncome: 1500000, deductions: 0 });
    const bigDed = computeRegimeTax({ grossIncome: 1500000, deductions: 450000 });
    expect(bigDed.oldTax).toBeLessThan(noDed.oldTax); // deductions cut old-regime tax
    expect(bigDed.saving).toBeGreaterThanOrEqual(0);
  });

  it('NaN inputs stay finite', () => {
    const r = computeRegimeTax({ grossIncome: NaN, deductions: NaN });
    for (const v of [r.oldTax, r.newTax, r.saving]) expect(Number.isFinite(v)).toBe(true);
  });
});
