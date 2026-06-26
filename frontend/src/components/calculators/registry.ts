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
  | 'loanAmount' | 'loanRate' | 'tenure' | 'oneTime' | 'extraMonthly';
export type Fmt = 'inr' | 'pct' | 'years';

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
  kind: 'accumulation' | 'goal' | 'loan' | 'prepayment' | 'loan-compare'; // result-renderer family
  inputs: CalcInputSpec[];
  stepUp?: boolean; // show the step-up toggle (accumulation only)
  stepUpDefault?: boolean; // step-up on by default (Step-up SIP)
  related: string[]; // related calculator slugs
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

// Format a value for a given input type (slider badge + min/max labels).
export function fmtValue(fmt: Fmt, n: number): string {
  if (fmt === 'pct') return `${n}%`;
  if (fmt === 'years') return `${n} ${n === 1 ? 'yr' : 'yrs'}`;
  return formatInr(n);
}

// Compact label for a preset chip.
export function fmtPreset(fmt: Fmt, n: number): string {
  if (fmt === 'pct') return `${n}%`;
  if (fmt === 'years') return `${n}y`;
  return formatInrShort(n);
}

// Unit hint for the editable value box.
export function fmtUnit(fmt: Fmt): '₹' | '%' | 'yrs' {
  if (fmt === 'pct') return '%';
  if (fmt === 'years') return 'yrs';
  return '₹';
}
