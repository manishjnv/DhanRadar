/**
 * Income-tax slab engine — Old vs New regime, FY 2025-26 (AY 2026-27).
 *
 * New-regime slabs + the ₹12 L rebate are the Budget-2025 figures effective
 * FY 2025-26. Rates are config knobs (REGIME_CONFIG) because budgets change them.
 * Educational estimate — surcharge, marginal relief at the rebate edge, and many
 * special-rate incomes are not modelled.
 */

export interface Slab { upTo: number; rate: number } // rate as %, upTo = upper bound (Infinity for top)

export const REGIME_CONFIG = {
  asOf: 'FY 2025-26',
  cessPct: 4,
  newStandardDeduction: 75000,
  oldStandardDeduction: 50000,
  newRebateUpTo: 1200000, // total income ≤ ₹12 L → nil tax (87A, new regime)
  oldRebateUpTo: 500000, // taxable income ≤ ₹5 L → nil tax (87A, old regime)
  newSlabs: [
    { upTo: 400000, rate: 0 },
    { upTo: 800000, rate: 5 },
    { upTo: 1200000, rate: 10 },
    { upTo: 1600000, rate: 15 },
    { upTo: 2000000, rate: 20 },
    { upTo: 2400000, rate: 25 },
    { upTo: Infinity, rate: 30 },
  ] as Slab[],
  oldSlabs: [
    { upTo: 250000, rate: 0 },
    { upTo: 500000, rate: 5 },
    { upTo: 1000000, rate: 20 },
    { upTo: Infinity, rate: 30 },
  ] as Slab[],
};

function clampF(v: number, min: number, max: number) {
  if (!Number.isFinite(v)) return min;
  return Math.min(Math.max(v, min), max);
}

/** Progressive slab tax on a taxable amount. */
export function slabTax(taxable: number, slabs: Slab[]): number {
  const t = Math.max(taxable, 0);
  let tax = 0;
  let lower = 0;
  for (const s of slabs) {
    if (t <= lower) break;
    const band = Math.min(t, s.upTo) - lower;
    if (band > 0) tax += (band * s.rate) / 100;
    lower = s.upTo;
  }
  return Number.isFinite(tax) ? tax : 0;
}

export interface RegimeTaxInput {
  grossIncome: number; // annual gross (salary) income
  deductions?: number; // old-regime deductions: 80C + 80D + HRA + home-loan interest, etc.
  salaried?: boolean; // apply the standard deduction (default true)
}
export interface RegimeTaxResult {
  oldTaxable: number;
  newTaxable: number;
  oldTax: number; // incl. 4% cess, after 87A rebate
  newTax: number;
  cheaper: 'old' | 'new' | 'equal';
  saving: number; // |oldTax − newTax|
}

export function computeRegimeTax(input: RegimeTaxInput): RegimeTaxResult {
  const C = REGIME_CONFIG;
  const gross = clampF(input.grossIncome, 0, 1e12);
  const deductions = clampF(input.deductions ?? 0, 0, 1e12);
  const salaried = input.salaried ?? true;
  const stdNew = salaried ? C.newStandardDeduction : 0;
  const stdOld = salaried ? C.oldStandardDeduction : 0;

  const newTaxable = Math.max(gross - stdNew, 0); // new regime: almost no other deductions
  const oldTaxable = Math.max(gross - stdOld - deductions, 0);

  const withCessRebate = (taxable: number, slabs: Slab[], rebateUpTo: number) => {
    let base = slabTax(taxable, slabs);
    if (taxable <= rebateUpTo) base = 0; // 87A rebate makes it nil at/under the threshold
    const tax = base * (1 + C.cessPct / 100);
    return Number.isFinite(tax) ? tax : 0;
  };

  const newTax = withCessRebate(newTaxable, C.newSlabs, C.newRebateUpTo);
  const oldTax = withCessRebate(oldTaxable, C.oldSlabs, C.oldRebateUpTo);
  const cheaper: 'old' | 'new' | 'equal' = newTax < oldTax ? 'new' : oldTax < newTax ? 'old' : 'equal';

  return {
    oldTaxable, newTaxable,
    oldTax: Math.round(oldTax),
    newTax: Math.round(newTax),
    cheaper,
    saving: Math.abs(Math.round(oldTax) - Math.round(newTax)),
  };
}
