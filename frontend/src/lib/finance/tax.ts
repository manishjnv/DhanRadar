/**
 * E8 — capital-gains tax on Indian mutual funds / equity.
 *
 * Rates: FY 2025-26 (post Budget 2024, effective 23 Jul 2024). Source-verified
 * against ClearTax + Finnovate. Kept in TAX_CONFIG because budgets change them.
 *
 *   Equity (≥65% equity): STCG @20% (≤12 mo); LTCG @12.5% above ₹1.25 L/yr (>12 mo), no indexation.
 *   Debt bought on/after 1 Apr 2023: taxed at the investor's SLAB rate, any holding.
 *   Debt bought before 1 Apr 2023: ≤24 mo slab; >24 mo LTCG @12.5% (no indexation).
 *   Plus a 4% Health & Education cess on the tax (surcharge ignored — income-dependent).
 *
 * Educational estimate only — NOT tax advice.
 */
import { MAX_AMOUNT } from './accumulation';

export const TAX_CONFIG = {
  equityStcgPct: 20,
  equityLtcgPct: 12.5,
  equityLtcgExemption: 125000,
  equityLtMonths: 12,
  debtPreLtcgPct: 12.5,
  debtPreLtMonths: 24,
  cessPct: 4,
  asOf: 'FY 2025-26',
};

export type AssetType = 'equity' | 'debt-new' | 'debt-old';

export interface CapGainInput {
  buyValue: number;
  sellValue: number;
  holdingMonths: number;
  assetType: AssetType;
  slabPct?: number; // income-tax slab — used for debt / slab-taxed cases (default 30)
  ltcgExemptionUsed?: number; // ₹1.25 L LTCG exemption already used this FY
}

export interface CapGainResult {
  gain: number;
  term: 'short' | 'long';
  taxableGain: number;
  ratePct: number; // headline rate before cess
  exemptionUsed: number;
  baseTax: number;
  cess: number;
  tax: number; // baseTax + cess
  postTaxValue: number;
  effectivePct: number; // tax as % of the gain
}

function clampF(v: number, min: number, max: number) {
  if (!Number.isFinite(v)) return min;
  return Math.min(Math.max(v, min), max);
}

export function computeCapitalGainsTax(input: CapGainInput): CapGainResult {
  const C = TAX_CONFIG;
  const buy = clampF(input.buyValue, 0, MAX_AMOUNT);
  const sell = clampF(input.sellValue, 0, MAX_AMOUNT);
  const months = clampF(input.holdingMonths, 0, 1200);
  const slab = clampF(input.slabPct ?? 30, 0, 50);
  const used = clampF(input.ltcgExemptionUsed ?? 0, 0, C.equityLtcgExemption);
  const gain = sell - buy;

  let term: 'short' | 'long';
  let ratePct: number;
  let exemptionUsed = 0;
  let taxableGain = Math.max(gain, 0);

  if (input.assetType === 'equity') {
    term = months <= C.equityLtMonths ? 'short' : 'long';
    if (term === 'short') {
      ratePct = C.equityStcgPct;
    } else {
      ratePct = C.equityLtcgPct;
      const exemptionLeft = Math.max(C.equityLtcgExemption - used, 0);
      exemptionUsed = Math.min(taxableGain, exemptionLeft);
      taxableGain = Math.max(taxableGain - exemptionUsed, 0);
    }
  } else if (input.assetType === 'debt-new') {
    term = months <= C.equityLtMonths ? 'short' : 'long'; // label only — slab either way
    ratePct = slab;
  } else {
    if (months <= C.debtPreLtMonths) { term = 'short'; ratePct = slab; }
    else { term = 'long'; ratePct = C.debtPreLtcgPct; }
  }

  if (gain <= 0) { ratePct = 0; taxableGain = 0; exemptionUsed = 0; }

  const baseTax = (taxableGain * ratePct) / 100;
  const cess = (baseTax * C.cessPct) / 100;
  const tax = baseTax + cess;
  const postTaxValue = sell - tax;
  const effectivePct = gain > 0 ? (tax / gain) * 100 : 0;

  const safe = (x: number) => (Number.isFinite(x) ? x : 0);
  return {
    gain: safe(gain),
    term,
    taxableGain: safe(taxableGain),
    ratePct: safe(ratePct),
    exemptionUsed: safe(exemptionUsed),
    baseTax: safe(baseTax),
    cess: safe(cess),
    tax: safe(tax),
    postTaxValue: safe(postTaxValue),
    effectivePct: safe(effectivePct),
  };
}
