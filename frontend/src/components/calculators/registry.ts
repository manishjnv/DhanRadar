/**
 * Calculator registry — the typed config that drives the detail template.
 *
 * A new calculator is a new entry here (+ maybe a new engine) — no template code.
 * Phase 0 ships the E1 "accumulation" family (SIP, Lumpsum, Step-up SIP); more
 * configs/engines follow. See docs/features/calculators.md.
 */
import { formatInr, formatInrShort } from '@/lib/finance';

export type InputKey = 'monthly' | 'lumpSum' | 'rate' | 'years' | 'target' | 'inflation' | 'current';
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
  kind: 'accumulation' | 'goal'; // result-renderer family (E1 / E2)
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
