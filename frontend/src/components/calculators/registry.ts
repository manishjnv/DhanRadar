/**
 * Calculator registry — the typed config that drives the detail template.
 *
 * A new calculator is a new entry here (+ maybe a new engine) — no template code.
 * Phase 0 ships the E1 "accumulation" family (SIP, Lumpsum, Step-up SIP); more
 * configs/engines follow. See docs/features/calculators.md.
 */
import { formatInr, formatInrShort } from '@/lib/finance';

export type InputKey =
  | 'monthly' | 'lumpSum' | 'rate' | 'years' | 'target' | 'inflation' | 'current'
  | 'loanAmount' | 'loanRate' | 'tenure' | 'oneTime' | 'extraMonthly'
  | 'beginValue' | 'endValue' | 'buyNav' | 'currentNav' | 'amount'
  | 'corpus' | 'monthlyWithdrawal' | 'principal' | 'yearlyDeposit' | 'contributionPct';
export type Fmt = 'inr' | 'pct' | 'years' | 'num';

export interface CalcInputSpec {
  key: InputKey;
  label: string;
  tip: string; // tooltip / help text — short, plain English
  min: number;
  max: number;
  step: number;
  default: number;
  fmt: Fmt;
  presets: number[]; // quick-pick chip values
}

export interface CalcConfig {
  slug: string;
  name: string;
  emoji: string;
  sub: string;
  kind: 'accumulation' | 'goal' | 'loan' | 'prepayment' | 'loan-compare' | 'rate' | 'rule' | 'xirr' | 'tax' | 'post-tax' | 'exit-load' | 'dividend' | 'tax-harvesting' | 'portfolio-tax' | 'redemption-planner' | 'swp' | 'stp' | 'sip-delay' | 'inflation-return' | 'retirement' | 'fire' | 'passive-income' | 'corpus' | 'scheme' | 'nps' | 'networth' | 'hlv' | 'term-cover' | 'health-cover'; // result family
  inputs: CalcInputSpec[];
  stepUp?: boolean; // show the step-up toggle (accumulation only)
  stepUpDefault?: boolean; // step-up on by default (Step-up SIP)
  related: string[]; // related calculator slugs
  rateMap?: { begin: string; end: string; amount?: string }; // E5 'rate' family input mapping
  scheme?: 'fd' | 'rd' | 'ppf' | 'epf'; // which scheme engine the 'scheme' family uses
  taxMode?: 'stcg' | 'ltcg'; // TaxDetail default framing (STCG = short-term, LTCG = long-term)
}

// Shared tooltips — one wording reused across calculators (founder simple-words rule).
export const TIPS = {
  monthly: 'The amount you invest every month',
  lumpSum: 'A single amount you invest once, at the start',
  rate: 'The average yearly return you assume — your choice, not a DhanRadar prediction',
  years: 'How many years you stay invested',
} as const;

const RATE: CalcInputSpec = { key: 'rate', label: 'Expected Annual Growth', tip: TIPS.rate, min: 1, max: 30, step: 0.5, default: 12, fmt: 'pct', presets: [8, 10, 12, 15] };
const YEARS: CalcInputSpec = { key: 'years', label: 'Investment Period', tip: TIPS.years, min: 1, max: 40, step: 1, default: 15, fmt: 'years', presets: [5, 10, 15, 20, 30] };
const MONTHLY: CalcInputSpec = { key: 'monthly', label: 'Monthly SIP', tip: TIPS.monthly, min: 500, max: 200000, step: 500, default: 25000, fmt: 'inr', presets: [5000, 10000, 25000, 50000, 100000] };
const LUMP: CalcInputSpec = { key: 'lumpSum', label: 'One-time Amount', tip: TIPS.lumpSum, min: 1000, max: 10000000, step: 1000, default: 100000, fmt: 'inr', presets: [50000, 100000, 500000, 1000000] };
const TARGET: CalcInputSpec = { key: 'target', label: 'Goal Amount (today’s cost)', tip: 'How much the goal costs in today’s money', min: 100000, max: 50000000, step: 50000, default: 5000000, fmt: 'inr', presets: [1000000, 2500000, 5000000, 10000000] };
const INFLATION: CalcInputSpec = { key: 'inflation', label: 'Inflation', tip: 'How fast the goal’s cost rises each year', min: 0, max: 12, step: 0.5, default: 6, fmt: 'pct', presets: [4, 6, 8] };
const LOAN_AMOUNT: CalcInputSpec = { key: 'loanAmount', label: 'Loan Amount', tip: 'How much you borrow', min: 100000, max: 100000000, step: 100000, default: 5000000, fmt: 'inr', presets: [2500000, 5000000, 7500000, 10000000] };
const LOAN_RATE: CalcInputSpec = { key: 'loanRate', label: 'Interest Rate', tip: 'The yearly interest rate on the loan', min: 5, max: 20, step: 0.05, default: 8.5, fmt: 'pct', presets: [7.5, 8.5, 9.5, 10.5] };
const TENURE: CalcInputSpec = { key: 'tenure', label: 'Loan Tenure', tip: 'How many years to repay the loan', min: 1, max: 30, step: 1, default: 20, fmt: 'years', presets: [10, 15, 20, 25, 30] };
const ONE_TIME: CalcInputSpec = { key: 'oneTime', label: 'One-time Prepayment', tip: 'A lump sum you pay now toward the loan', min: 0, max: 10000000, step: 50000, default: 500000, fmt: 'inr', presets: [100000, 500000, 1000000, 2000000] };
const EXTRA_MONTHLY: CalcInputSpec = { key: 'extraMonthly', label: 'Extra Per Month', tip: 'Extra you pay every month on top of the EMI', min: 0, max: 200000, step: 1000, default: 0, fmt: 'inr', presets: [0, 2000, 5000, 10000] };
const BEGIN_VALUE: CalcInputSpec = { key: 'beginValue', label: 'Starting Value', tip: 'What it was worth at the start', min: 1000, max: 100000000, step: 1000, default: 100000, fmt: 'inr', presets: [50000, 100000, 500000, 1000000] };
const END_VALUE: CalcInputSpec = { key: 'endValue', label: 'Ending Value', tip: 'What it is worth now', min: 1000, max: 100000000, step: 1000, default: 200000, fmt: 'inr', presets: [150000, 300000, 500000, 1000000] };
const FR_AMOUNT: CalcInputSpec = { key: 'amount', label: 'Amount Invested', tip: 'How much you invested', min: 1000, max: 100000000, step: 1000, default: 100000, fmt: 'inr', presets: [50000, 100000, 500000, 1000000] };
const BUY_NAV: CalcInputSpec = { key: 'buyNav', label: 'Buy NAV', tip: 'The fund NAV when you invested', min: 1, max: 10000, step: 0.01, default: 50, fmt: 'num', presets: [25, 50, 100, 250] };
const CURRENT_NAV: CalcInputSpec = { key: 'currentNav', label: 'Current NAV', tip: 'The fund NAV now', min: 1, max: 10000, step: 0.01, default: 75, fmt: 'num', presets: [50, 75, 100, 200] };
const CORPUS: CalcInputSpec = { key: 'corpus', label: 'Your Corpus', tip: 'The total amount you start with', min: 100000, max: 100000000, step: 100000, default: 10000000, fmt: 'inr', presets: [5000000, 10000000, 25000000, 50000000] };
const MONTHLY_WITHDRAWAL: CalcInputSpec = { key: 'monthlyWithdrawal', label: 'Monthly Withdrawal', tip: 'How much you take out each month', min: 1000, max: 1000000, step: 1000, default: 50000, fmt: 'inr', presets: [25000, 50000, 75000, 100000] };
const FD_PRINCIPAL: CalcInputSpec = { key: 'principal', label: 'Deposit Amount', tip: 'The lump sum you deposit', min: 1000, max: 100000000, step: 1000, default: 100000, fmt: 'inr', presets: [50000, 100000, 500000, 1000000] };
const RD_MONTHLY: CalcInputSpec = { key: 'monthly', label: 'Monthly Deposit', tip: 'How much you deposit each month', min: 500, max: 1000000, step: 500, default: 5000, fmt: 'inr', presets: [2000, 5000, 10000, 25000] };
const PPF_YEARLY: CalcInputSpec = { key: 'yearlyDeposit', label: 'Yearly Deposit', tip: 'How much you put in each year (max ₹1.5 L)', min: 500, max: 150000, step: 500, default: 150000, fmt: 'inr', presets: [50000, 100000, 150000] };
const CONTRIBUTION_PCT: CalcInputSpec = { key: 'contributionPct', label: 'Total Contribution', tip: 'Employee + employer share going into EPF (~24%)', min: 12, max: 24, step: 0.5, default: 24, fmt: 'pct', presets: [12, 24] };

export const CONFIGS: Record<string, CalcConfig> = {
  sip: {
    slug: 'sip', name: 'SIP Calculator', emoji: '📈',
    sub: 'See how your monthly investment grows into wealth over time.',
    kind: 'accumulation', inputs: [MONTHLY, RATE, YEARS], stepUp: true, stepUpDefault: false,
    related: ['lumpsum', 'step-up-sip'],
  },
  lumpsum: {
    slug: 'lumpsum', name: 'Lumpsum Calculator', emoji: '💵',
    sub: 'See how a one-time investment grows over time.',
    kind: 'accumulation', inputs: [LUMP, RATE, YEARS], stepUp: false, stepUpDefault: false,
    related: ['sip', 'step-up-sip'],
  },
  'sip-lumpsum': {
    slug: 'sip-lumpsum', name: 'SIP + Lumpsum Calculator', emoji: '📈',
    sub: 'An upfront amount plus a monthly SIP — see them grow together.',
    kind: 'accumulation', inputs: [{ ...LUMP, label: 'Upfront Amount', default: 100000 }, MONTHLY, RATE, YEARS], stepUp: true, stepUpDefault: false,
    related: ['sip', 'lumpsum', 'step-up-sip'],
  },
  'step-up-sip': {
    slug: 'step-up-sip', name: 'Step-up SIP Calculator', emoji: '📊',
    sub: 'See how raising your SIP a little every year grows your wealth.',
    kind: 'accumulation', inputs: [MONTHLY, RATE, YEARS], stepUp: true, stepUpDefault: true,
    related: ['sip', 'lumpsum'],
  },
  'goal-sip': {
    slug: 'goal-sip', name: 'Goal SIP Calculator', emoji: '🎯',
    sub: 'Find the monthly SIP to reach a goal — adjusted for inflation.',
    kind: 'goal', inputs: [TARGET, YEARS, RATE, INFLATION],
    related: ['savings-goal', 'sip', 'lumpsum'],
  },
  'savings-goal': {
    slug: 'savings-goal', name: 'Savings Goal Calculator', emoji: '🎯',
    sub: 'Find the monthly saving to reach a target amount.',
    kind: 'goal', inputs: [TARGET, YEARS, RATE],
    related: ['goal-sip', 'sip'],
  },
  'home-loan-emi': {
    slug: 'home-loan-emi', name: 'Home Loan EMI Calculator', emoji: '🏠',
    sub: 'See your monthly EMI and how much interest you pay over the loan.',
    kind: 'loan', inputs: [LOAN_AMOUNT, LOAN_RATE, TENURE],
    related: ['sip', 'lumpsum'],
  },

  // ── E1 ──
  'future-value': {
    slug: 'future-value', name: 'Future Value Calculator', emoji: '💹',
    sub: 'See what an amount today could grow to.',
    kind: 'accumulation', inputs: [{ ...LUMP, label: 'Amount Today', default: 100000 }, RATE, YEARS],
    stepUp: false, stepUpDefault: false, related: ['lumpsum', 'sip'],
  },

  // ── E2 goal planners (same engine + view, tailored presets) ──
  'goal-planner': {
    slug: 'goal-planner', name: 'Goal Planner', emoji: '🎯',
    sub: 'Find the monthly SIP for any goal — inflation-adjusted.',
    kind: 'goal', inputs: [TARGET, YEARS, RATE, INFLATION],
    related: ['goal-sip', 'savings-goal', 'sip'],
  },
  'education-planner': {
    slug: 'education-planner', name: 'Education Planner', emoji: '🎓',
    sub: 'Find the monthly SIP for education — inflation-adjusted.',
    kind: 'goal',
    inputs: [{ ...TARGET, label: 'Education Cost (today)', default: 2500000 }, YEARS, RATE, { ...INFLATION, label: 'Education Inflation', default: 10 }],
    related: ['child-education', 'goal-sip', 'sip'],
  },
  'child-education': {
    slug: 'child-education', name: 'Child Education Planner', emoji: '👶',
    sub: "Plan for your child's higher-education costs.",
    kind: 'goal',
    inputs: [{ ...TARGET, label: 'Education Cost (today)', default: 2500000 }, YEARS, RATE, { ...INFLATION, label: 'Education Inflation', default: 10 }],
    related: ['education-planner', 'goal-sip'],
  },
  'marriage-planner': {
    slug: 'marriage-planner', name: 'Marriage Planner', emoji: '💍',
    sub: 'Find the monthly SIP to fund a wedding.',
    kind: 'goal',
    inputs: [{ ...TARGET, label: 'Wedding Cost (today)', default: 2000000 }, { ...YEARS, default: 10 }, RATE, INFLATION],
    related: ['goal-sip', 'savings-goal'],
  },
  'house-purchase': {
    slug: 'house-purchase', name: 'House Purchase Planner', emoji: '🏠',
    sub: 'Save for a home down payment or purchase.',
    kind: 'goal',
    inputs: [{ ...TARGET, label: 'Amount Needed (today)', default: 3000000 }, { ...YEARS, default: 7 }, RATE, INFLATION],
    related: ['home-loan-emi', 'goal-sip'],
  },
  'car-purchase': {
    slug: 'car-purchase', name: 'Car Purchase Planner', emoji: '🚗',
    sub: 'Save for your next car.',
    kind: 'goal',
    inputs: [{ ...TARGET, label: 'Car Price (today)', default: 1000000 }, { ...YEARS, default: 5 }, RATE, INFLATION],
    related: ['goal-sip', 'savings-goal'],
  },
  'vacation-planner': {
    slug: 'vacation-planner', name: 'Vacation Planner', emoji: '✈️',
    sub: 'Save for a dream trip.',
    kind: 'goal',
    inputs: [{ ...TARGET, label: 'Trip Cost (today)', default: 500000 }, { ...YEARS, default: 3 }, RATE, INFLATION],
    related: ['goal-sip', 'savings-goal'],
  },
  'emergency-fund': {
    slug: 'emergency-fund', name: 'Emergency Fund Planner', emoji: '🆘',
    sub: 'Build a safety net of a few months’ expenses.',
    kind: 'goal',
    inputs: [{ ...TARGET, label: 'Fund Target', default: 600000 }, { ...YEARS, label: 'Build Over', default: 2 }, { ...RATE, default: 7 }],
    related: ['savings-goal', 'goal-sip'],
  },

  // ── E7 loan extras ──
  prepayment: {
    slug: 'prepayment', name: 'Loan Prepayment Calculator', emoji: '💳',
    sub: 'See how prepaying cuts your loan tenure and interest.',
    kind: 'prepayment',
    inputs: [{ ...LOAN_AMOUNT, label: 'Outstanding Loan' }, LOAN_RATE, { ...TENURE, label: 'Remaining Tenure' }, ONE_TIME, EXTRA_MONTHLY],
    related: ['home-loan-emi', 'loan-comparison'],
  },
  'loan-comparison': {
    slug: 'loan-comparison', name: 'Loan Comparison Calculator', emoji: '⚖️',
    sub: 'Compare two loan offers side by side.',
    kind: 'loan-compare', inputs: [],
    related: ['home-loan-emi', 'prepayment'],
  },

  // ── E5 returns ──
  cagr: {
    slug: 'cagr', name: 'CAGR Calculator', emoji: '📈',
    sub: 'Find the annual growth rate between two values.',
    kind: 'rate', inputs: [BEGIN_VALUE, END_VALUE, { ...YEARS, label: 'Period', default: 5 }],
    rateMap: { begin: 'beginValue', end: 'endValue' },
    related: ['rule-of-72', 'sip', 'lumpsum'],
  },
  'rule-of-72': {
    slug: 'rule-of-72', name: 'Rule of 72 Calculator', emoji: '📐',
    sub: 'How long money takes to double, triple, and quadruple.',
    kind: 'rule', inputs: [{ ...RATE, label: 'Annual Rate', default: 12 }],
    related: ['cagr', 'sip'],
  },
  'fund-return': {
    slug: 'fund-return', name: 'Fund Return Calculator', emoji: '💰',
    sub: 'Find your return from the buy and current NAV.',
    kind: 'rate', inputs: [FR_AMOUNT, BUY_NAV, CURRENT_NAV, { ...YEARS, label: 'Holding Period', default: 3 }],
    rateMap: { begin: 'buyNav', end: 'currentNav', amount: 'amount' },
    related: ['cagr', 'xirr', 'sip'],
  },
  xirr: {
    slug: 'xirr', name: 'XIRR Calculator', emoji: '🧮',
    sub: 'Your true return when you invest on different dates (like SIPs).',
    kind: 'xirr', inputs: [],
    related: ['cagr', 'fund-return', 'sip'],
  },

  // ── E8 tax ──
  'capital-gains-tax': {
    slug: 'capital-gains-tax', name: 'Capital Gains Tax Calculator', emoji: '🧾',
    sub: 'Tax on mutual fund gains — LTCG / STCG, FY 2025-26.',
    kind: 'tax', inputs: [],
    related: ['stcg', 'ltcg', 'post-tax-return'],
  },
  stcg: {
    slug: 'stcg', name: 'STCG Calculator', emoji: '📋',
    sub: 'Short-term capital gains tax on funds sold within a year.',
    kind: 'tax', taxMode: 'stcg', inputs: [],
    related: ['ltcg', 'capital-gains-tax', 'exit-load'],
  },
  ltcg: {
    slug: 'ltcg', name: 'LTCG Calculator', emoji: '📑',
    sub: 'Long-term capital gains tax, with the ₹1.25 L equity exemption.',
    kind: 'tax', taxMode: 'ltcg', inputs: [],
    related: ['stcg', 'capital-gains-tax', 'tax-harvesting'],
  },
  'post-tax-return': {
    slug: 'post-tax-return', name: 'Post-Tax Return Calculator', emoji: '✅',
    sub: 'Your real take-home return after capital-gains tax.',
    kind: 'post-tax', inputs: [],
    related: ['capital-gains-tax', 'sip', 'lumpsum'],
  },
  'exit-load': {
    slug: 'exit-load', name: 'Exit Load Calculator', emoji: '💸',
    sub: 'The fee charged when you redeem a fund too early.',
    kind: 'exit-load', inputs: [],
    related: ['capital-gains-tax', 'stcg', 'sip'],
  },
  'dividend-tax': {
    slug: 'dividend-tax', name: 'Dividend Tax Calculator', emoji: '💵',
    sub: 'Tax on mutual fund dividends (IDCW) at your slab rate.',
    kind: 'dividend', inputs: [],
    related: ['capital-gains-tax', 'post-tax-return', 'sip'],
  },
  'tax-harvesting': {
    slug: 'tax-harvesting', name: 'Tax Harvesting Calculator', emoji: '🌾',
    sub: 'Save tax by booking ₹1.25 L of equity gains tax-free each year.',
    kind: 'tax-harvesting', inputs: [],
    related: ['ltcg', 'capital-gains-tax', 'portfolio-tax'],
  },
  'portfolio-tax': {
    slug: 'portfolio-tax', name: 'Portfolio Tax Calculator', emoji: '📊',
    sub: 'Tax across all your holdings, sharing one ₹1.25 L exemption.',
    kind: 'portfolio-tax', inputs: [],
    related: ['capital-gains-tax', 'redemption-planner', 'tax-harvesting'],
  },
  'redemption-planner': {
    slug: 'redemption-planner', name: 'Redemption Planner', emoji: '📤',
    sub: 'A tax-efficient order to redeem units for a cash need.',
    kind: 'redemption-planner', inputs: [],
    related: ['portfolio-tax', 'capital-gains-tax', 'ltcg'],
  },

  // ── E3 decumulation ──
  swp: {
    slug: 'swp', name: 'SWP Calculator', emoji: '💸',
    sub: 'How long your corpus lasts with regular withdrawals.',
    kind: 'swp',
    inputs: [CORPUS, MONTHLY_WITHDRAWAL, { ...RATE, label: 'Expected Return', default: 8 }, { ...INFLATION, label: 'Raise Withdrawal Yearly', default: 0 }],
    related: ['goal-sip', 'sip', 'lumpsum'],
  },

  // ── E4 transfer (STP) ──
  stp: {
    slug: 'stp', name: 'STP Calculator', emoji: '🔄',
    sub: 'Move money monthly from one fund to another — see both grow.',
    kind: 'stp', inputs: [],
    related: ['swp', 'sip', 'lumpsum'],
  },

  // ── E6 inflation / cost-of-delay ──
  'sip-delay': {
    slug: 'sip-delay', name: 'SIP Delay Calculator', emoji: '⏰',
    sub: 'See what waiting to start your SIP really costs.',
    kind: 'sip-delay', inputs: [],
    related: ['sip', 'step-up-sip', 'goal-sip'],
  },
  'inflation-adjusted-return': {
    slug: 'inflation-adjusted-return', name: 'Inflation-Adjusted Return Calculator', emoji: '📉',
    sub: 'Your real return after inflation eats into it.',
    kind: 'inflation-return', inputs: [],
    related: ['sip', 'cagr', 'future-value'],
  },

  // ── Retirement (E1→E3 / E2) ──
  'retirement-planner': {
    slug: 'retirement-planner', name: 'Retirement Planner', emoji: '🏖',
    sub: 'The corpus you need at retirement and the SIP to build it.',
    kind: 'retirement', inputs: [],
    related: ['fire-calculator', 'corpus-calculator', 'swp'],
  },
  'fire-calculator': {
    slug: 'fire-calculator', name: 'FIRE Calculator', emoji: '🔥',
    sub: 'Your financial-independence number and years to reach it.',
    kind: 'fire', inputs: [],
    related: ['retirement-planner', 'passive-income', 'swp'],
  },
  'passive-income': {
    slug: 'passive-income', name: 'Passive Income Calculator', emoji: '💵',
    sub: 'The monthly income a corpus can sustainably provide.',
    kind: 'passive-income', inputs: [],
    related: ['swp', 'corpus-calculator', 'fire-calculator'],
  },
  'corpus-calculator': {
    slug: 'corpus-calculator', name: 'Corpus Calculator', emoji: '🏦',
    sub: 'The corpus needed to fund a monthly income in retirement.',
    kind: 'corpus', inputs: [],
    related: ['retirement-planner', 'passive-income', 'goal-sip'],
  },

  // ── E7 loan delta ──
  'interest-savings': {
    slug: 'interest-savings', name: 'Interest Savings Calculator', emoji: '💰',
    sub: 'How much interest a lower rate or shorter tenure saves.',
    kind: 'loan-compare', inputs: [],
    related: ['home-loan-emi', 'prepayment', 'loan-comparison'],
  },

  // ── Scheme calculators ──
  fd: {
    slug: 'fd', name: 'FD Calculator', emoji: '🏦',
    sub: 'See your fixed deposit maturity value (compounded quarterly).',
    kind: 'scheme', scheme: 'fd',
    inputs: [FD_PRINCIPAL, { ...RATE, label: 'Interest Rate', default: 7 }, { ...TENURE, label: 'Tenure', default: 5 }],
    related: ['rd', 'ppf', 'lumpsum'],
  },
  rd: {
    slug: 'rd', name: 'RD Calculator', emoji: '💰',
    sub: 'See your recurring deposit maturity value.',
    kind: 'scheme', scheme: 'rd',
    inputs: [RD_MONTHLY, { ...RATE, label: 'Interest Rate', default: 7 }, { ...TENURE, label: 'Tenure', default: 5 }],
    related: ['fd', 'ppf', 'sip'],
  },
  ppf: {
    slug: 'ppf', name: 'PPF Calculator', emoji: '🛡️',
    sub: 'See your PPF maturity (tax-free) over the term.',
    kind: 'scheme', scheme: 'ppf',
    inputs: [PPF_YEARLY, { ...RATE, label: 'PPF Rate (notified)', default: 7.1 }, { ...TENURE, label: 'Years', default: 15, min: 15, max: 50 }],
    related: ['fd', 'rd', 'sip'],
  },
  epf: {
    slug: 'epf', name: 'EPF Calculator', emoji: '👔',
    sub: 'See your EPF (provident fund) corpus at retirement.',
    kind: 'scheme', scheme: 'epf',
    inputs: [{ ...MONTHLY, label: 'Monthly Basic + DA', default: 25000, min: 1000 }, CONTRIBUTION_PCT, { ...RATE, label: 'EPF Rate', default: 8.25 }, { ...TENURE, label: 'Years to Retirement', default: 25, max: 40 }, { ...INFLATION, label: 'Annual Salary Growth', default: 5, max: 15 }],
    related: ['ppf', 'nps', 'sip'],
  },
  nps: {
    slug: 'nps', name: 'NPS Calculator', emoji: '📊',
    sub: 'Your NPS corpus at 60, plus the pension from the annuity.',
    kind: 'nps', inputs: [],
    related: ['epf', 'ppf', 'sip'],
  },
  'net-worth': {
    slug: 'net-worth', name: 'Net Worth Calculator', emoji: '💎',
    sub: 'Add up what you own minus what you owe.',
    kind: 'networth', inputs: [],
    related: ['sip', 'goal-sip'],
  },

  // ── Insurance (E10 — indicative cover estimates, never a product pick) ──
  'term-cover': {
    slug: 'term-cover', name: 'Term Cover Estimator', emoji: '🛡️',
    sub: 'An indicative life-cover amount from your needs and assets.',
    kind: 'term-cover', inputs: [],
    related: ['hlv', 'health-cover', 'goal-sip'],
  },
  'health-cover': {
    slug: 'health-cover', name: 'Health Cover Estimator', emoji: '🏥',
    sub: 'An indicative health sum-insured for your family and city.',
    kind: 'health-cover', inputs: [],
    related: ['term-cover', 'hlv', 'emergency-fund'],
  },
  hlv: {
    slug: 'hlv', name: 'Human Life Value Calculator', emoji: '❤️',
    sub: 'The income an earner would replace, valued in today’s money.',
    kind: 'hlv', inputs: [],
    related: ['term-cover', 'health-cover', 'retirement-planner'],
  },
};

// Card names differ between the Featured and All grids, so map the variants to a
// canonical slug; anything unmapped is slugified and routes to a "coming soon" page.
const SLUG_OVERRIDES: Record<string, string> = {
  'SIP Calculator': 'sip',
  Lumpsum: 'lumpsum',
  'Lumpsum Calculator': 'lumpsum',
  'SIP Top-up': 'step-up-sip',
  'Step-up SIP': 'step-up-sip',
  'Goal SIP': 'goal-sip',
  'Goal SIP Calculator': 'goal-sip',
  'Savings Goal': 'savings-goal',
  // True duplicates merged to one canonical calculator (SEO/discovery cards may
  // still differ, but they open the same engine).
  'Withdrawal Planner': 'swp', // = SWP (E3 decumulation)
  'Home Down Payment': 'house-purchase', // = House Purchase goal
  'Rule of 72 / 114': 'rule-of-72',
  'Rule of 114': 'rule-of-72', // one card covers 72 / 114 / 144
  'FD Calculator': 'fd',
  'RD Calculator': 'rd',
  'Human Life Value': 'hlv',
};

export function slugFor(name: string): string {
  return SLUG_OVERRIDES[name] ?? name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}

export function getConfig(slug: string): CalcConfig | undefined {
  return CONFIGS[slug];
}

// ponytail: temporary "Live" tagging — true when a calculator is actually built +
// has a working engine. Drives the green "Live" badge on hub cards so the founder
// knows which calculators are ready to test. Remove the badge once all are live.
export function isLive(slug: string): boolean {
  return Object.prototype.hasOwnProperty.call(CONFIGS, slug);
}

/** Title-cased fallback name for an unbuilt slug ("car-purchase" → "Car Purchase"). */
export function humanizeSlug(slug: string): string {
  return slug.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

const plainNum = (n: number) => (n % 1 === 0 ? String(n) : n.toFixed(2));

// Format a value for a given input type (slider badge + min/max labels).
export function fmtValue(fmt: Fmt, n: number): string {
  if (fmt === 'pct') return `${n}%`;
  if (fmt === 'years') return `${n} ${n === 1 ? 'yr' : 'yrs'}`;
  if (fmt === 'num') return plainNum(n);
  return formatInr(n);
}

// Compact label for a preset chip.
export function fmtPreset(fmt: Fmt, n: number): string {
  if (fmt === 'pct') return `${n}%`;
  if (fmt === 'years') return `${n}y`;
  if (fmt === 'num') return plainNum(n);
  return formatInrShort(n);
}

// Unit hint for the editable value box.
export function fmtUnit(fmt: Fmt): '₹' | '%' | 'yrs' | undefined {
  if (fmt === 'pct') return '%';
  if (fmt === 'years') return 'yrs';
  if (fmt === 'num') return undefined;
  return '₹';
}
