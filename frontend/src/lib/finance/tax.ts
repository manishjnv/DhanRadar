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

// ── Exit load ────────────────────────────────────────────────────────────────
// Most MFs charge an exit load (typically ~1%) if you redeem within a window
// (commonly 12 months). The load is a % of the redemption value, deducted before
// you receive the money. Pure, clamped — never NaN.

export interface ExitLoadInput {
  redeemValue: number; // amount you're redeeming (₹)
  loadPct: number; // exit load rate (% of redemption value)
  holdingMonths: number; // how long you've held
  loadWindowMonths: number; // load applies if held < this many months
}

export interface ExitLoadResult {
  applies: boolean;
  loadAmount: number;
  netValue: number; // redeemValue − loadAmount
}

export function computeExitLoad(input: ExitLoadInput): ExitLoadResult {
  const value = clampF(input.redeemValue, 0, MAX_AMOUNT);
  const pct = clampF(input.loadPct, 0, 10);
  const months = clampF(input.holdingMonths, 0, 1200);
  const windowM = clampF(input.loadWindowMonths, 0, 1200);
  const applies = months < windowM && pct > 0;
  const loadAmount = applies ? (value * pct) / 100 : 0;
  const safe = (x: number) => (Number.isFinite(x) ? x : 0);
  return { applies, loadAmount: safe(loadAmount), netValue: safe(value - loadAmount) };
}

// ── Dividend / IDCW tax ──────────────────────────────────────────────────────
// Since FY 2020-21 dividends (IDCW) are taxed in the investor's hands at their
// slab rate (added to income). TDS @10% applies if total dividend > ₹5,000/yr.
// This estimates the slab tax; the TDS is an advance, not extra tax.

export const DIVIDEND_CONFIG = { tdsThreshold: 5000, tdsPct: 10, asOf: 'FY 2025-26' };

export interface DividendTaxInput {
  dividend: number; // dividend / IDCW received (₹)
  slabPct: number; // investor's income-tax slab
}

export interface DividendTaxResult {
  tax: number; // slab tax on the dividend
  tds: number; // TDS deducted at source (advance), if over the threshold
  netInHand: number; // dividend − tax
  effectivePct: number;
}

export function computeDividendTax(input: DividendTaxInput): DividendTaxResult {
  const D = DIVIDEND_CONFIG;
  const dividend = clampF(input.dividend, 0, MAX_AMOUNT);
  const slab = clampF(input.slabPct, 0, 50);
  const tax = (dividend * slab) / 100;
  const tds = dividend > D.tdsThreshold ? (dividend * D.tdsPct) / 100 : 0;
  const safe = (x: number) => (Number.isFinite(x) ? x : 0);
  return {
    tax: safe(tax),
    tds: safe(tds),
    netInHand: safe(dividend - tax),
    effectivePct: dividend > 0 ? safe((tax / dividend) * 100) : 0,
  };
}

// ── Tax harvesting (equity LTCG) ─────────────────────────────────────────────
// Each financial year you can realise long-term equity gains up to the ₹1.25 L
// exemption tax-free and re-buy (resetting the cost basis). Over a horizon this
// can be far cheaper than letting the whole gain build and realising it once.
// Illustrative: assumes a steady long-term gain accrues each year.

export interface TaxHarvestingInput {
  annualGain: number; // long-term equity gain that accrues each year
  years: number;
  exemption?: number; // default ₹1.25 L (a knob — budgets change it)
}
export interface TaxHarvestingResult {
  taxHarvesting: number; // total tax if you harvest the exemption every year
  taxStraight: number; // total tax if you realise the whole gain once at the end
  taxSaved: number;
  yearsExemptionFullyUsed: boolean; // annualGain ≥ exemption (harvest fully soaks the free slab)
}

export function computeTaxHarvesting(input: TaxHarvestingInput): TaxHarvestingResult {
  const C = TAX_CONFIG;
  const g = clampF(input.annualGain, 0, MAX_AMOUNT);
  const years = Math.round(clampF(input.years, 0, 100));
  const exemption = clampF(input.exemption ?? C.equityLtcgExemption, 0, MAX_AMOUNT);
  const factor = (C.equityLtcgPct / 100) * (1 + C.cessPct / 100);

  // Harvest: realise this year's gain each year, only the part over the exemption is taxed.
  const taxHarvesting = years * Math.max(g - exemption, 0) * factor;
  // Straight: realise the whole accumulated gain once, one exemption applies.
  const taxStraight = Math.max(g * years - exemption, 0) * factor;

  const safe = (x: number) => (Number.isFinite(x) ? x : 0);
  return {
    taxHarvesting: safe(taxHarvesting),
    taxStraight: safe(taxStraight),
    taxSaved: safe(Math.max(taxStraight - taxHarvesting, 0)),
    yearsExemptionFullyUsed: g >= exemption,
  };
}

// ── Portfolio tax (aggregate across holdings) ────────────────────────────────
// Tax across several holdings at once, sharing ONE ₹1.25 L equity-LTCG exemption
// across all long-term equity gains (the correct annual treatment).

export interface Holding {
  label?: string;
  buyValue: number;
  sellValue: number;
  holdingMonths: number;
  assetType: AssetType;
}
export interface PortfolioRowResult {
  gain: number;
  term: 'short' | 'long';
  ratePct: number;
}
export interface PortfolioTaxResult {
  totalSell: number;
  totalGain: number;
  stcgTax: number; // base tax on all short-term + slab-taxed gains
  ltcgTax: number; // base tax on long-term gains after the shared exemption
  exemptionUsed: number;
  cess: number;
  totalTax: number;
  postTaxValue: number;
  rows: PortfolioRowResult[];
}

export function computePortfolioTax(holdings: Holding[], slabPct = 30): PortfolioTaxResult {
  const C = TAX_CONFIG;
  const slab = clampF(slabPct, 0, 50);
  let totalSell = 0;
  let totalGain = 0;
  let stcgBase = 0; // short-term + slab-taxed base tax
  let equityLtGain = 0; // pooled long-term equity gains (share the exemption)
  let debtLtBase = 0; // long-term debt-old base tax (no exemption)
  const rows: PortfolioRowResult[] = [];

  for (const h of holdings) {
    const buy = clampF(h.buyValue, 0, MAX_AMOUNT);
    const sell = clampF(h.sellValue, 0, MAX_AMOUNT);
    const months = clampF(h.holdingMonths, 0, 1200);
    const gain = sell - buy;
    totalSell += sell;
    totalGain += gain;

    let term: 'short' | 'long' = 'short';
    let ratePct = 0;
    const taxableGain = Math.max(gain, 0);

    if (h.assetType === 'equity') {
      term = months <= C.equityLtMonths ? 'short' : 'long';
      if (term === 'short') { ratePct = C.equityStcgPct; stcgBase += (taxableGain * ratePct) / 100; }
      else { ratePct = C.equityLtcgPct; equityLtGain += taxableGain; }
    } else if (h.assetType === 'debt-new') {
      term = months <= C.equityLtMonths ? 'short' : 'long';
      ratePct = slab; stcgBase += (taxableGain * slab) / 100;
    } else { // debt-old
      if (months <= C.debtPreLtMonths) { term = 'short'; ratePct = slab; stcgBase += (taxableGain * slab) / 100; }
      else { term = 'long'; ratePct = C.debtPreLtcgPct; debtLtBase += (taxableGain * ratePct) / 100; }
    }
    rows.push({ gain, term, ratePct: gain > 0 ? ratePct : 0 });
  }

  const exemptionUsed = Math.min(equityLtGain, C.equityLtcgExemption);
  const equityLtBase = Math.max(equityLtGain - exemptionUsed, 0) * (C.equityLtcgPct / 100);
  const ltcgBase = equityLtBase + debtLtBase;
  const baseTax = stcgBase + ltcgBase;
  const cess = baseTax * (C.cessPct / 100);
  const totalTax = baseTax + cess;

  const safe = (x: number) => (Number.isFinite(x) ? x : 0);
  return {
    totalSell: safe(totalSell),
    totalGain: safe(totalGain),
    stcgTax: safe(stcgBase),
    ltcgTax: safe(ltcgBase),
    exemptionUsed: safe(exemptionUsed),
    cess: safe(cess),
    totalTax: safe(totalTax),
    postTaxValue: safe(totalSell - totalTax),
    rows,
  };
}

// ── Redemption planner (tax-efficient order) ─────────────────────────────────
// Given lots and a cash need, redeem in the most tax-efficient order: long-term
// equity first (uses the ₹1.25 L exemption → often 0 tax), then other long-term,
// then short-term. ILLUSTRATIVE — one tax-efficient order, not a recommendation.

export interface Lot {
  label?: string;
  currentValue: number; // what the lot is worth today
  cost: number; // what you paid for it
  holdingMonths: number;
  assetType: AssetType;
}
export interface RedemptionStep {
  label: string;
  redeemValue: number; // value redeemed from this lot
  taxOnStep: number;
  term: 'short' | 'long';
}
export interface RedemptionPlanResult {
  steps: RedemptionStep[];
  totalRedeemed: number; // gross value redeemed
  totalTax: number;
  netRaised: number; // redeemed − tax (what reaches your hand)
  exemptionUsed: number;
  shortfall: number; // cash still unmet after redeeming everything
}

// Effective tax rate on a lot's *gain* (lower = redeem earlier). Long-term equity
// is cheapest (12.5% and may be exemption-covered); short-term is dearest.
function lotRate(lot: Lot, slab: number): { term: 'short' | 'long'; gainRatePct: number; isEquityLt: boolean } {
  const C = TAX_CONFIG;
  const m = lot.holdingMonths;
  if (lot.assetType === 'equity') {
    return m <= C.equityLtMonths
      ? { term: 'short', gainRatePct: C.equityStcgPct, isEquityLt: false }
      : { term: 'long', gainRatePct: C.equityLtcgPct, isEquityLt: true };
  }
  if (lot.assetType === 'debt-new') return { term: m <= C.equityLtMonths ? 'short' : 'long', gainRatePct: slab, isEquityLt: false };
  return m <= C.debtPreLtMonths
    ? { term: 'short', gainRatePct: slab, isEquityLt: false }
    : { term: 'long', gainRatePct: C.debtPreLtcgPct, isEquityLt: false };
}

export function computeRedemptionPlan(lots: Lot[], cashNeeded: number, slabPct = 30): RedemptionPlanResult {
  const C = TAX_CONFIG;
  const slab = clampF(slabPct, 0, 50);
  const need = clampF(cashNeeded, 0, MAX_AMOUNT);
  const cessF = 1 + C.cessPct / 100;

  // Order: equity-LT first (exemption), then by ascending gain tax rate, then by gain ratio.
  const ranked = lots.map((lot, i) => ({ lot, i, meta: lotRate(lot, slab) }))
    .sort((a, b) => {
      if (a.meta.isEquityLt !== b.meta.isEquityLt) return a.meta.isEquityLt ? -1 : 1;
      return a.meta.gainRatePct - b.meta.gainRatePct;
    });

  let exemptionLeft = C.equityLtcgExemption;
  let netRaised = 0;
  let totalRedeemed = 0;
  let totalTax = 0;
  let exemptionUsed = 0;
  const steps: RedemptionStep[] = [];

  for (const { lot, i, meta } of ranked) {
    if (netRaised >= need - 1e-6) break;
    const value = clampF(lot.currentValue, 0, MAX_AMOUNT);
    const cost = clampF(lot.cost, 0, MAX_AMOUNT);
    if (value <= 0) continue;
    const gainFrac = Math.max(value - cost, 0) / value; // gain share of the redemption value

    // How much of THIS lot to redeem to cover the remaining net need? Solve for the
    // gross redemption R whose net (R − tax(R)) closes the gap, capped at the lot value.
    const remaining = need - netRaised;
    const rate = meta.gainRatePct / 100;
    const grossForFull = value;

    // Per-rupee net factor for this lot (after tax on its gain share). Equity-LT may
    // be exemption-covered for part of the gain — handled by capping below.
    const taxPerRupee = gainFrac * rate * cessF;
    const netPerRupee = Math.max(1 - taxPerRupee, 0);
    let redeem = netPerRupee > 0 ? remaining / netPerRupee : grossForFull;
    redeem = Math.min(redeem, value);

    let gainRealised = (Math.max(value - cost, 0)) * (redeem / value);
    let usedExemption = 0;
    if (meta.isEquityLt && exemptionLeft > 0) {
      usedExemption = Math.min(gainRealised, exemptionLeft);
      exemptionLeft -= usedExemption;
      exemptionUsed += usedExemption;
    }
    const taxableGain = Math.max(gainRealised - usedExemption, 0);
    const stepTax = taxableGain * rate * cessF;

    steps.push({ label: lot.label ?? `Lot ${i + 1}`, redeemValue: redeem, taxOnStep: stepTax, term: meta.term });
    totalRedeemed += redeem;
    totalTax += stepTax;
    netRaised += redeem - stepTax;
  }

  const safe = (x: number) => (Number.isFinite(x) ? x : 0);
  return {
    steps,
    totalRedeemed: safe(totalRedeemed),
    totalTax: safe(totalTax),
    netRaised: safe(netRaised),
    exemptionUsed: safe(exemptionUsed),
    shortfall: safe(Math.max(need - netRaised, 0)),
  };
}
