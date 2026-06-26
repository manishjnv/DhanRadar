/**
 * Tests for the E8 capital-gains tax engine. Values cross-checked against the
 * FY 2025-26 rules (equity LTCG 12.5% above ₹1.25 L; STCG 20%; debt at slab).
 */
import { describe, it, expect } from 'vitest';
import {
  computeCapitalGainsTax, computeExitLoad, computeDividendTax,
  computeTaxHarvesting, computePortfolioTax, computeRedemptionPlan,
} from './tax';

describe('computeCapitalGainsTax — equity', () => {
  it('LTCG: ₹2 L gain held 24 mo → tax on (2L − 1.25L) @12.5% = ₹9,375 + 4% cess', () => {
    const r = computeCapitalGainsTax({ buyValue: 100000, sellValue: 300000, holdingMonths: 24, assetType: 'equity' });
    expect(r.term).toBe('long');
    expect(r.taxableGain).toBe(75000);
    expect(Math.round(r.baseTax)).toBe(9375);
    expect(Math.round(r.tax)).toBe(9750); // + 4% cess
  });

  it('LTCG below the ₹1.25 L exemption → zero tax', () => {
    const r = computeCapitalGainsTax({ buyValue: 100000, sellValue: 200000, holdingMonths: 18, assetType: 'equity' });
    expect(r.term).toBe('long');
    expect(r.tax).toBe(0);
  });

  it('STCG: held ≤ 12 mo → 20% on the full gain + cess', () => {
    const r = computeCapitalGainsTax({ buyValue: 100000, sellValue: 150000, holdingMonths: 6, assetType: 'equity' });
    expect(r.term).toBe('short');
    expect(r.ratePct).toBe(20);
    expect(Math.round(r.baseTax)).toBe(10000);
    expect(Math.round(r.tax)).toBe(10400);
  });

  it('exemption already used this year reduces the free slab', () => {
    const full = computeCapitalGainsTax({ buyValue: 100000, sellValue: 300000, holdingMonths: 24, assetType: 'equity' });
    const partial = computeCapitalGainsTax({ buyValue: 100000, sellValue: 300000, holdingMonths: 24, assetType: 'equity', ltcgExemptionUsed: 125000 });
    expect(partial.tax).toBeGreaterThan(full.tax); // no exemption left → whole gain taxed
    expect(partial.taxableGain).toBe(200000);
  });
});

describe('computeCapitalGainsTax — debt', () => {
  it('debt bought after 1 Apr 2023 → slab rate, any holding period', () => {
    const r = computeCapitalGainsTax({ buyValue: 100000, sellValue: 200000, holdingMonths: 40, assetType: 'debt-new', slabPct: 30 });
    expect(r.ratePct).toBe(30);
    expect(Math.round(r.baseTax)).toBe(30000);
    expect(Math.round(r.tax)).toBe(31200);
  });

  it('debt bought before 1 Apr 2023, >24 mo → LTCG 12.5%', () => {
    const r = computeCapitalGainsTax({ buyValue: 100000, sellValue: 200000, holdingMonths: 30, assetType: 'debt-old', slabPct: 30 });
    expect(r.term).toBe('long');
    expect(r.ratePct).toBe(12.5);
    expect(Math.round(r.baseTax)).toBe(12500);
  });

  it('debt-old ≤24 mo → slab', () => {
    const r = computeCapitalGainsTax({ buyValue: 100000, sellValue: 200000, holdingMonths: 12, assetType: 'debt-old', slabPct: 20 });
    expect(r.term).toBe('short');
    expect(r.ratePct).toBe(20);
  });
});

describe('computeCapitalGainsTax — edges', () => {
  it('a loss (sell < buy) → no tax', () => {
    const r = computeCapitalGainsTax({ buyValue: 200000, sellValue: 150000, holdingMonths: 24, assetType: 'equity' });
    expect(r.gain).toBe(-50000);
    expect(r.tax).toBe(0);
  });

  it('NaN / negative inputs stay finite', () => {
    const r = computeCapitalGainsTax({ buyValue: NaN, sellValue: -1, holdingMonths: -5, assetType: 'equity' });
    for (const v of [r.gain, r.tax, r.taxableGain, r.postTaxValue, r.effectivePct]) expect(Number.isFinite(v)).toBe(true);
  });
});

describe('computeExitLoad', () => {
  it('1% load on ₹1 L redeemed within the 12-mo window → ₹1,000 load', () => {
    const r = computeExitLoad({ redeemValue: 100000, loadPct: 1, holdingMonths: 6, loadWindowMonths: 12 });
    expect(r.applies).toBe(true);
    expect(r.loadAmount).toBe(1000);
    expect(r.netValue).toBe(99000);
  });

  it('held beyond the window → no load', () => {
    const r = computeExitLoad({ redeemValue: 100000, loadPct: 1, holdingMonths: 18, loadWindowMonths: 12 });
    expect(r.applies).toBe(false);
    expect(r.loadAmount).toBe(0);
    expect(r.netValue).toBe(100000);
  });

  it('NaN / negative inputs stay finite', () => {
    const r = computeExitLoad({ redeemValue: NaN, loadPct: -1, holdingMonths: -5, loadWindowMonths: NaN });
    for (const v of [r.loadAmount, r.netValue]) expect(Number.isFinite(v)).toBe(true);
  });
});

describe('computeDividendTax', () => {
  it('₹50,000 dividend at 30% slab → ₹15,000 tax, TDS ₹5,000', () => {
    const r = computeDividendTax({ dividend: 50000, slabPct: 30 });
    expect(r.tax).toBe(15000);
    expect(r.tds).toBe(5000); // 10% over the ₹5,000 threshold
    expect(r.netInHand).toBe(35000);
    expect(Math.round(r.effectivePct)).toBe(30);
  });

  it('dividend at/under ₹5,000 → no TDS', () => {
    const r = computeDividendTax({ dividend: 5000, slabPct: 20 });
    expect(r.tds).toBe(0);
    expect(r.tax).toBe(1000);
  });

  it('NaN inputs stay finite', () => {
    const r = computeDividendTax({ dividend: NaN, slabPct: NaN });
    for (const v of [r.tax, r.tds, r.netInHand, r.effectivePct]) expect(Number.isFinite(v)).toBe(true);
  });
});

describe('computeTaxHarvesting', () => {
  it('gain under the exemption → harvesting pays ₹0, straight pays on the pooled excess', () => {
    const r = computeTaxHarvesting({ annualGain: 100000, years: 5 }); // 1L/yr < 1.25L exemption
    expect(r.taxHarvesting).toBe(0); // each year fully exempt
    // straight: 5L gain − 1.25L = 3.75L @ 12.5% + 4% cess
    expect(Math.round(r.taxStraight)).toBe(Math.round(375000 * 0.125 * 1.04));
    expect(r.taxSaved).toBe(r.taxStraight);
  });

  it('harvesting never costs more than straight', () => {
    const r = computeTaxHarvesting({ annualGain: 300000, years: 10 });
    expect(r.taxHarvesting).toBeLessThanOrEqual(r.taxStraight);
    expect(r.taxSaved).toBeGreaterThanOrEqual(0);
    expect(r.yearsExemptionFullyUsed).toBe(true);
  });

  it('NaN inputs stay finite', () => {
    const r = computeTaxHarvesting({ annualGain: NaN, years: -3 });
    for (const v of [r.taxHarvesting, r.taxStraight, r.taxSaved]) expect(Number.isFinite(v)).toBe(true);
  });
});

describe('computePortfolioTax', () => {
  it('shares ONE ₹1.25 L exemption across all long-term equity holdings', () => {
    const r = computePortfolioTax([
      { buyValue: 100000, sellValue: 200000, holdingMonths: 24, assetType: 'equity' }, // +1L LT
      { buyValue: 100000, sellValue: 200000, holdingMonths: 24, assetType: 'equity' }, // +1L LT
    ]);
    expect(r.exemptionUsed).toBe(125000); // 2L pooled, only 1.25L exempt
    // taxable 75k @ 12.5% = 9,375 base + 4% cess
    expect(Math.round(r.ltcgTax)).toBe(9375);
    expect(Math.round(r.totalTax)).toBe(Math.round(9375 * 1.04));
  });

  it('mixes short-term equity (20%) and long-term, post-tax value is sell − tax', () => {
    const r = computePortfolioTax([
      { buyValue: 100000, sellValue: 150000, holdingMonths: 6, assetType: 'equity' }, // ST +50k @20%
      { buyValue: 100000, sellValue: 300000, holdingMonths: 24, assetType: 'equity' }, // LT +2L
    ]);
    expect(Math.round(r.stcgTax)).toBe(10000); // 50k @ 20%
    expect(r.exemptionUsed).toBe(125000);
    expect(Math.round(r.postTaxValue)).toBe(Math.round(450000 - r.totalTax));
  });

  it('a loss-making holding does not add tax', () => {
    const r = computePortfolioTax([{ buyValue: 200000, sellValue: 150000, holdingMonths: 24, assetType: 'equity' }]);
    expect(r.totalTax).toBe(0);
    expect(r.rows[0].gain).toBe(-50000);
  });
});

describe('computeRedemptionPlan', () => {
  it('redeems long-term equity first (exemption → low tax) before short-term', () => {
    const r = computeRedemptionPlan([
      { label: 'ST equity', currentValue: 500000, cost: 300000, holdingMonths: 6, assetType: 'equity' },
      { label: 'LT equity', currentValue: 500000, cost: 400000, holdingMonths: 24, assetType: 'equity' },
    ], 300000);
    expect(r.steps[0].label).toBe('LT equity'); // cheapest tax first
    expect(r.netRaised).toBeGreaterThanOrEqual(300000 - 1); // covers the need
    expect(r.shortfall).toBe(0);
  });

  it('uses the ₹1.25 L exemption on long-term equity gains', () => {
    const r = computeRedemptionPlan([
      { label: 'LT', currentValue: 1000000, cost: 900000, holdingMonths: 24, assetType: 'equity' }, // +1L gain, under exemption
    ], 200000);
    expect(r.exemptionUsed).toBeGreaterThan(0);
    expect(r.totalTax).toBe(0); // gain within the exemption
  });

  it('reports a shortfall when lots cannot raise the cash', () => {
    const r = computeRedemptionPlan([{ currentValue: 100000, cost: 50000, holdingMonths: 6, assetType: 'equity' }], 500000);
    expect(r.shortfall).toBeGreaterThan(0);
  });

  it('NaN inputs stay finite', () => {
    const r = computeRedemptionPlan([{ currentValue: NaN, cost: NaN, holdingMonths: NaN, assetType: 'equity' }], NaN);
    for (const v of [r.totalRedeemed, r.totalTax, r.netRaised, r.shortfall]) expect(Number.isFinite(v)).toBe(true);
  });
});
