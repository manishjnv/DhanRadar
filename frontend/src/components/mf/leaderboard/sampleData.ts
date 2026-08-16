/**
 * Rankings & Leaderboards V1 — illustrative PREVIEW data.
 *
 * Ported 1:1 from the approved LeaderboardPageV1 desktop + mobile mockups. This
 * is a PURE-UI build: every value here is illustrative sample data so the full
 * page can be designed now and wired to the real ranking feed in a later session
 * (founder call 2026-06-24 — build all UI now, wire data later).
 *
 * Two design→compliance bridges are baked in so the page renders through the
 * guards the way the sister V3 pages (Fund Comparison, Fund Detail) already do —
 * the VISUAL design is untouched:
 *   1. DhanRadar composite scores are kept here as raw seeds but the UI renders a
 *      BAND ring / strength WORD, never the raw 0–100 number (non-neg #2).
 *   2. The verdict pill uses the canonical educational labels (In Form / On Track
 *      / Off Track / Out of Form), never advisory verbs (non-neg #1).
 * Third-party ratings (Morningstar / CRISIL / Value Research) and factual
 * published metrics (returns %, cost %, AUM, flows) render as-is.
 */

import type { Strength, Band3 } from '@/components/mf/funddetail/sampleData';
import type { Label } from '@/components/charts/ScoreRing';

// ── Mockup colour constants (decorative brand-letter tiles + accents) ────────
// Mirrors the E/B/A/R/O/V/C/N/P/T/G palette in the mockups, nudged to the
// DhanRadar brand hexes where one exists (emerald/royal/amber/red/cyan/navy).
export const COLORS = {
  E: '#00B386', // emerald
  B: '#1E5EFF', // royal
  A: '#F5A623', // amber
  R: '#E5484D', // red
  O: '#F97316', // orange
  V: '#8B5CF6', // violet
  C: '#00C2FF', // cyan
  N: '#0B1F3A', // navy
  P: '#EC4899', // pink
  T: '#14B8A6', // teal
  G: '#D4A017', // gold
} as const;
const { E, B, A, R, O, V, C, N, P, T, G } = COLORS;

// ── Score → band / strength / educational-label helpers ──────────────────────
export function toBand(score: number): Band3 {
  if (score >= 85) return 'high';
  if (score >= 60) return 'medium';
  return 'low';
}
export function toStrength(score: number): Strength {
  if (score >= 88) return 'strong';
  if (score >= 78) return 'good';
  if (score >= 65) return 'moderate';
  return 'soft';
}
/** Canonical educational label (replaces the mockup's advisory verdict verbs). */
export function eduLabel(score: number): { word: string; color: string } {
  if (score >= 85) return { word: 'In Form', color: E };
  if (score >= 72) return { word: 'On Track', color: B };
  if (score >= 60) return { word: 'Watch', color: A };
  return { word: 'Off Form', color: R };
}
export const STRENGTH_WORD: Record<Strength, string> = { strong: 'Strong', good: 'Good', moderate: 'Fair', soft: 'Soft' };
export const STRENGTH_COLOR: Record<Strength, string> = { strong: E, good: C, moderate: A, soft: R };

/** Live-data verb_label → the same educational word/colour vocabulary eduLabel()
 * uses on this page (page-local wording: 'Watch'/'Off Form', not the site-wide
 * LabelChip copy) — real rows carry no numeric score, only the enum. */
export function eduWordFromLabel(label: Label): { word: string; color: string } {
  switch (label) {
    case 'in_form': return { word: 'In Form', color: E };
    case 'on_track': return { word: 'On Track', color: B };
    case 'off_track': return { word: 'Watch', color: A };
    case 'out_of_form': return { word: 'Off Form', color: R };
    default: return { word: 'Insufficient Data', color: 'var(--text-muted)' };
  }
}

export function riskColor(rk: string): string {
  return ({ Low: E, Moderate: A, 'Mod. High': O, High: R, 'Very High': R } as Record<string, string>)[rk] ?? A;
}
export function ringColor(score: number): string {
  return score >= 85 ? E : score >= 70 ? B : score >= 55 ? A : score >= 40 ? O : R;
}
export function aum(v: number): string {
  return v >= 10000 ? '₹' + (v / 1000).toFixed(1) + 'k Cr' : '₹' + v.toLocaleString('en-IN') + ' Cr';
}

// ── Hero ─────────────────────────────────────────────────────────────────────
export const HERO_KPIS: { label: string; value: string; sub?: string; valueColor?: string; small?: boolean }[] = [
  { label: 'Funds Ranked', value: '2,847' },
  { label: 'Categories', value: '32' },
  { label: 'Live Boards', value: '11' },
  { label: 'Top Rated Today', value: 'Parag Parikh', small: true },
  { label: 'Trending', value: 'Small Cap', small: true },
  { label: 'DMMI', value: '62', sub: 'Caut+', valueColor: '#FBBF24' },
];
export type QuickLink = { label: string; href: string };
export const HERO_QUICK: QuickLink[] = [
  { label: 'Top Rated', href: '#top100' },
  { label: 'Best SIP', href: '#sip' },
  { label: 'Highest Returns', href: '#performance' },
  { label: 'Lowest Risk', href: '#risk' },
  { label: 'Best Value', href: '#value' },
  { label: 'Most Consistent', href: '#sip' },
  { label: 'Trending', href: '#trending' },
  { label: 'Hidden Gems', href: '#intelligence' },
  { label: 'AI Spotlight', href: '#intelligence' },
  { label: 'Tax Saving', href: '/mf/explore?category=Equity%20Scheme%20-%20ELSS' },
  { label: 'Retirement', href: '/mf/explore?category=Solution%20Oriented%20Scheme%20-%20Retirement%20Fund' },
  { label: 'Index', href: '/mf/explore?category=Other%20Scheme%20-%20Index%20Funds' },
  { label: 'International', href: '/mf/explore' },
];
export const MOBILE_QUICK: QuickLink[] = [
  { label: 'Top Rated', href: '#top100' },
  { label: 'Best SIP', href: '#sip' },
  { label: 'Highest Returns', href: '#performance' },
  { label: 'Lowest Risk', href: '#risk' },
  { label: 'Best Value', href: '#value' },
  { label: 'Trending', href: '#trending' },
  { label: 'Hidden Gems', href: '#intelligence' },
  { label: 'AI Spotlight', href: '#intelligence' },
  { label: 'ELSS', href: '/mf/explore?category=Equity%20Scheme%20-%20ELSS' },
  { label: 'Index', href: '/mf/explore?category=Other%20Scheme%20-%20Index%20Funds' },
];

// ── Discovery shortcuts ──────────────────────────────────────────────────────
export type Disc = { icon: string; name: string; count: string; color: string; anchor: string };
export const DISC: Disc[] = [
  { icon: '🏆', name: 'Best Overall', count: 'Top 100', color: G, anchor: '#top100' },
  { icon: '📈', name: 'Best Returns', count: '9 boards', color: E, anchor: '#performance' },
  { icon: '💰', name: 'Best SIP', count: '6 boards', color: B, anchor: '#sip' },
  { icon: '🛡', name: 'Lowest Risk', count: '8 boards', color: T, anchor: '#risk' },
  { icon: '⭐', name: 'Highest Rated', count: 'Multi-agency', color: A, anchor: '#top100' },
  { icon: '📊', name: 'Best Categories', count: '32 winners', color: V, anchor: '#champions' },
  { icon: '🏦', name: 'Best AMC', count: 'Top houses', color: C, anchor: '#amc' },
  { icon: '👤', name: 'Best Managers', count: 'Track records', color: P, anchor: '#managers' },
  { icon: '📉', name: 'Lowest Cost', count: 'Value boards', color: E, anchor: '#value' },
  { icon: '🚀', name: 'Trending', count: 'Hot now', color: O, anchor: '#trending' },
  { icon: '🧠', name: 'AI Spotlight', count: 'In-form funds', color: V, anchor: '#intelligence' },
  { icon: '🌍', name: 'International', count: 'Global funds', color: B, anchor: '#intelligence' },
];

// ── Top 100 funds ────────────────────────────────────────────────────────────
export type Fund = {
  name: string; amc: string; cat: string; logo: string; color: string;
  score: number; risk: string; r3: number; r5: number; sip: number; exp: number;
  aum: number; rankd: string; trend: 'up' | 'down' | 'flat';
};
const RAW: [string, string, string, string, string, number, string, number, number, number, number, number, string, Fund['trend']][] = [
  ['Parag Parikh Flexi Cap', 'PPFAS', 'Flexi Cap', 'P', N, 93, 'Mod. High', 22.4, 21.8, 94, 0.62, 78420, '+6', 'up'],
  ['ICICI Pru Bluechip', 'ICICI', 'Large Cap', 'I', O, 91, 'Moderate', 17.8, 16.4, 87, 0.52, 68400, '+5', 'up'],
  ['Bandhan Small Cap', 'Bandhan', 'Small Cap', 'B', B, 91, 'High', 28.6, 26.1, 90, 0.42, 9840, '+12', 'up'],
  ['Axis Small Cap', 'Axis', 'Small Cap', 'A', R, 89, 'High', 27.1, 28.4, 87, 0.68, 42100, '0', 'flat'],
  ['SBI Contra Fund', 'SBI', 'Value', 'S', B, 89, 'Mod. High', 28.2, 24.8, 86, 0.62, 38600, '+7', 'up'],
  ['HDFC Flexi Cap', 'HDFC', 'Flexi Cap', 'H', R, 88, 'Mod. High', 24.1, 20.6, 88, 0.74, 52600, '+3', 'up'],
  ['Nippon India Small Cap', 'Nippon', 'Small Cap', 'N', E, 89, 'High', 27.1, 28.4, 87, 0.68, 58200, '+4', 'up'],
  ['Mirae Asset Large Cap', 'Mirae', 'Large Cap', 'M', C, 86, 'Moderate', 16.2, 15.8, 85, 0.54, 37920, '-1', 'down'],
  ['Kotak Emerging Equity', 'Kotak', 'Mid Cap', 'K', E, 87, 'High', 25.2, 25.6, 84, 0.46, 42100, '+4', 'up'],
  ['Mirae ELSS Tax Saver', 'Mirae', 'ELSS', 'M', V, 86, 'Mod. High', 21.4, 20.8, 85, 0.58, 24800, '+2', 'up'],
  ['Canara Robeco Bluechip', 'Canara', 'Large Cap', 'C', B, 85, 'Moderate', 16.8, 16.2, 85, 0.48, 14200, '+1', 'up'],
  ['HDFC Balanced Advantage', 'HDFC', 'Balanced Adv.', 'H', R, 85, 'Moderate', 16.4, 14.8, 86, 0.74, 94200, '0', 'flat'],
  ['Quant Small Cap', 'Quant', 'Small Cap', 'Q', V, 84, 'Very High', 31.0, 30.2, 82, 0.64, 24180, '+9', 'up'],
  ['HDFC Smallcap Index', 'HDFC', 'Index', 'H', B, 84, 'High', 28.6, 26.1, 90, 0.42, 9840, '+3', 'up'],
  ['Axis Midcap Fund', 'Axis', 'Mid Cap', 'A', P, 83, 'High', 23.4, 24.1, 83, 0.56, 29800, '-2', 'down'],
  ['SBI Equity Hybrid', 'SBI', 'Hybrid', 'S', B, 82, 'Mod. High', 15.2, 14.4, 82, 0.72, 68800, '+1', 'up'],
  ['HDFC Healthcare Fund', 'HDFC', 'Healthcare', 'H', R, 83, 'High', 26.4, 22.8, 81, 0.68, 6800, '+11', 'up'],
  ['ICICI Pru Technology', 'ICICI', 'Technology', 'I', O, 78, 'Very High', 22.6, 28.1, 77, 0.62, 13600, '-4', 'down'],
  ['Motilal Nasdaq 100', 'Motilal', 'International', 'M', V, 76, 'High', 18.6, 21.2, 78, 0.58, 8200, '-3', 'down'],
  ['UTI Nifty 50 Index', 'UTI', 'Index', 'U', N, 79, 'Moderate', 14.2, 13.9, 80, 0.20, 18400, '0', 'flat'],
];
export const FUNDS: Fund[] = RAW
  .map(([name, amc, cat, logo, color, score, risk, r3, r5, sip, exp, av, rankd, trend]) => ({
    name, amc, cat, logo, color, score, risk, r3, r5, sip, exp, aum: av, rankd, trend,
  }))
  .sort((a, b) => b.score - a.score);

// ── Category champions ───────────────────────────────────────────────────────
export type Champ = {
  cat: string; winner: string; wLogo: string; wColor: string; score: number; ret: string;
  runner: string; rLogo: string; rColor: string; why: string;
};
export const CHAMP: Champ[] = [
  { cat: 'Best Large Cap', winner: 'ICICI Bluechip', wLogo: 'I', wColor: O, score: 91, ret: '17.8% 3Y', runner: 'Mirae Large Cap', rLogo: 'M', rColor: C, why: 'Lowest drawdown with steady alpha.' },
  { cat: 'Best Flexi Cap', winner: 'Parag Parikh', wLogo: 'P', wColor: N, score: 93, ret: '22.4% 3Y', runner: 'HDFC Flexi Cap', rLogo: 'H', rColor: R, why: 'Best risk-adjusted returns + global mix.' },
  { cat: 'Best Mid Cap', winner: 'Kotak Emerging', wLogo: 'K', wColor: E, score: 87, ret: '25.2% 3Y', runner: 'Axis Midcap', rLogo: 'A', rColor: P, why: 'Consistent top-quartile with risk control.' },
  { cat: 'Best Small Cap', winner: 'Bandhan Small Cap', wLogo: 'B', wColor: B, score: 91, ret: '28.6% 3Y', runner: 'Nippon Small Cap', rLogo: 'N', rColor: E, why: 'Top returns, lowest volatility in category.' },
  { cat: 'Best Value', winner: 'SBI Contra', wLogo: 'S', wColor: B, score: 89, ret: '28.2% 3Y', runner: 'ICICI Value', rLogo: 'I', rColor: O, why: 'Contrarian picks paying off strongly.' },
  { cat: 'Best ELSS', winner: 'Mirae ELSS', wLogo: 'M', wColor: V, score: 86, ret: '21.4% 3Y', runner: 'Quant ELSS', rLogo: 'Q', rColor: V, why: 'Low cost tax-saver, strong consistency.' },
  { cat: 'Best Hybrid', winner: 'HDFC Bal. Adv.', wLogo: 'H', wColor: R, score: 85, ret: '16.4% 3Y', runner: 'ICICI Bal. Adv.', rLogo: 'I', rColor: O, why: 'Smoothest ride, only −11% worst fall.' },
  { cat: 'Best Index', winner: 'UTI Nifty 50', wLogo: 'U', wColor: N, score: 79, ret: '14.2% 3Y', runner: 'HDFC Nifty', rLogo: 'H', rColor: B, why: 'Cheapest at 0.20% with low tracking error.' },
  { cat: 'Best International', winner: 'Motilal Nasdaq', wLogo: 'M', wColor: V, score: 76, ret: '18.6% 3Y', runner: 'Franklin US Opp', rLogo: 'F', rColor: B, why: 'Cleanest US-tech exposure for Indians.' },
  { cat: 'Best Healthcare', winner: 'HDFC Healthcare', wLogo: 'H', wColor: R, score: 83, ret: '26.4% 3Y', runner: 'Nippon Pharma', rLogo: 'N', rColor: E, why: 'Riding strong pharma earnings momentum.' },
  { cat: 'Best Liquid', winner: 'Edelweiss Liquid', wLogo: 'E', wColor: E, score: 74, ret: '7.2% 1Y', runner: 'HDFC Liquid', rLogo: 'H', rColor: R, why: 'Highest safety for parking cash short-term.' },
  { cat: 'Best Tax Saver', winner: 'Mirae ELSS', wLogo: 'M', wColor: V, score: 86, ret: '21.4% 3Y', runner: 'Quant ELSS', rLogo: 'Q', rColor: V, why: 'Low cost tax-saver, strong consistency.' },
];

// ── Mini-leaderboard rails ───────────────────────────────────────────────────
// V1: `sub` is a tiny muted caption under `val` — e.g. a category-average
// comparison ("cat avg 14.1%") or (V6) a short flow explainer. Optional; rows
// without it render exactly as before.
export type RailRow = { name: string; logo: string; color: string; val: string; up?: boolean; href?: string; sub?: string };
/** `live` marks a rail as fed by a wired board (renders a small LiveBadge in its header). */
export type Rail = { title: string; q: string; icon: string; color: string; rows: RailRow[]; live?: boolean };

const row = (name: string, logo: string, color: string, val: string, up?: boolean): RailRow => ({ name, logo, color, val, up });

export const PERF_RAIL: Rail[] = [
  { title: 'Highest 1Y Return', q: 'Best last year', icon: '📈', color: E, rows: [row('Quant Small Cap', 'Q', V, '+42%'), row('Bandhan Small Cap', 'B', B, '+38%'), row('HDFC Healthcare', 'H', R, '+36%'), row('SBI Contra', 'S', B, '+34%')] },
  { title: 'Highest 3Y Return', q: 'Best 3-year', icon: '📊', color: B, rows: [row('Quant Small Cap', 'Q', V, '+31%'), row('Bandhan Small Cap', 'B', B, '+29%'), row('Nippon Small Cap', 'N', E, '+27%'), row('SBI Contra', 'S', B, '+28%')] },
  { title: 'Highest 5Y Return', q: 'Best 5-year', icon: '🏆', color: G, rows: [row('Quant Small Cap', 'Q', V, '+30%'), row('Nippon Small Cap', 'N', E, '+28%'), row('ICICI Tech', 'I', O, '+28%'), row('Bandhan SC', 'B', B, '+26%')] },
  { title: 'Best Wealth Creator', q: 'Highest since launch', icon: '💎', color: V, rows: [row('Nippon Small Cap', 'N', E, '42×'), row('Parag Parikh', 'P', N, '8×'), row('HDFC Flexi', 'H', R, '24×'), row('Mirae Large', 'M', C, '6×')] },
];
export const SIP_RAIL: Rail[] = [
  { title: 'Best 3Y SIP', q: 'Top monthly return', icon: '💰', color: B, rows: [row('Quant Small Cap', 'Q', V, '28.1'), row('Bandhan SC', 'B', B, '24.0'), row('HDFC Healthcare', 'H', R, '22.6'), row('SBI Contra', 'S', B, '23.1')] },
  { title: 'Best 5Y SIP', q: '5-year monthly', icon: '📈', color: E, rows: [row('Quant Small Cap', 'Q', V, '21.2'), row('Nippon SC', 'N', E, '19.8'), row('Bandhan SC', 'B', B, '18.6'), row('ICICI Tech', 'I', O, '25.2')] },
  { title: 'Best SIP Consistency', q: 'Steadiest monthly', icon: '🎯', color: T, rows: [row('Parag Parikh', 'P', N, 'Strong'), row('ICICI Bluechip', 'I', O, 'Strong'), row('HDFC Bal Adv', 'H', R, 'Good'), row('Mirae ELSS', 'M', V, 'Good')] },
  { title: 'Steady SIP Starters', q: 'Rule-based · no advice', icon: '❤️', color: P, rows: [row('Parag Parikh', 'P', N, 'Top'), row('ICICI Bluechip', 'I', O, 'Safe'), row('Mirae Large', 'M', C, 'Easy'), row('HDFC Bal Adv', 'H', R, 'Calm')] },
];
export const RISK_RAIL: Rail[] = [
  { title: 'Lowest Risk', q: 'Safest funds', icon: '🛡', color: E, rows: [row('Edelweiss Liquid', 'E', E, 'Very Low', false), row('HDFC Corp Bond', 'H', R, 'Low', false), row('ICICI Bal Adv', 'I', O, 'Mod', false), row('HDFC Bal Adv', 'H', R, 'Mod', false)] },
  { title: 'Smallest Falls', q: 'Lowest drawdown', icon: '📉', color: B, rows: [row('ICICI Bal Adv', 'I', O, '−9%'), row('HDFC Bal Adv', 'H', R, '−11%'), row('Parag Parikh', 'P', N, '−19%'), row('ICICI Bluechip', 'I', O, '−15%')] },
  { title: 'Best Risk-Adjusted', q: 'Highest Sharpe', icon: '⚖', color: V, rows: [row('Parag Parikh', 'P', N, '1.42'), row('ICICI Bluechip', 'I', O, '1.31'), row('HDFC Bal Adv', 'H', R, '1.28'), row('Mirae ELSS', 'M', V, '1.18')] },
  { title: 'Fastest Recovery', q: 'Bounces back quick', icon: '🔄', color: T, rows: [row('Parag Parikh', 'P', N, '7 mo'), row('ICICI Bluechip', 'I', O, '8 mo'), row('Mirae Large', 'M', C, '9 mo'), row('Kotak EE', 'K', E, '11 mo')] },
];
export const VALUE_RAIL: Rail[] = [
  { title: 'Lowest Annual Cost', q: 'Cheapest funds', icon: '💸', color: E, rows: [row('UTI Nifty 50', 'U', N, '0.20%', false), row('Edelweiss Liquid', 'E', E, '0.18%', false), row('HDFC SC Index', 'H', B, '0.42%', false), row('Bandhan SC', 'B', B, '0.42%', false)] },
  { title: 'Best Return Per Cost', q: 'Most efficient', icon: '📊', color: B, rows: [row('UTI Nifty 50', 'U', N, '71×'), row('Bandhan SC', 'B', B, '68×'), row('Parag Parikh', 'P', N, '36×'), row('Kotak EE', 'K', E, '54×')] },
  { title: 'Best Low-Cost Index', q: 'Cheapest passives', icon: '📈', color: C, rows: [row('UTI Nifty 50', 'U', N, '0.20%', false), row('HDFC SC Index', 'H', B, '0.42%', false), row('Nippon Nifty', 'N', E, '0.20%', false), row('ICICI Nifty', 'I', O, '0.17%', false)] },
];
export const INTEL_RAIL: Rail[] = [
  { title: 'Hidden Gems', q: 'Underrated winners', icon: '💎', color: V, rows: [row('HDFC Healthcare', 'H', R, 'Gem'), row('SBI Contra', 'S', B, 'Gem'), row('Canara Bluechip', 'C', B, 'Gem'), row('Bandhan SC', 'B', B, 'Gem')] },
  { title: 'Future Leaders', q: 'Rising fast', icon: '🚀', color: O, rows: [row('Bandhan SC', 'B', B, '+12'), row('HDFC Healthcare', 'H', R, '+11'), row('Quant SC', 'Q', V, '+9'), row('SBI Contra', 'S', B, '+7')] },
  { title: 'Highest Momentum', q: 'Strongest trend', icon: '⚡', color: A, rows: [row('Quant Small Cap', 'Q', V, 'Strong'), row('Bandhan SC', 'B', B, 'Strong'), row('HDFC Healthcare', 'H', R, 'High'), row('SBI Contra', 'S', B, 'High')] },
  { title: 'Best Portfolio Quality', q: 'Cleanest holdings', icon: '✨', color: B, rows: [row('Parag Parikh', 'P', N, 'Strong'), row('ICICI Bluechip', 'I', O, 'Strong'), row('Mirae Large', 'M', C, 'Good'), row('Kotak EE', 'K', E, 'Good')] },
  { title: 'AI Spotlight', q: 'In Form across the most boards', icon: '🧠', color: V, rows: [row('Parag Parikh', 'P', N, 'Pick'), row('Bandhan SC', 'B', B, 'Pick'), row('ICICI Bluechip', 'I', O, 'Pick'), row('SBI Contra', 'S', B, 'Pick')] },
];
export const FLOW_RAIL: Rail[] = [
  { title: 'Highest Net Inflows', q: 'Most new money', icon: '📥', color: E, rows: [row('Parag Parikh', 'P', N, '+8.9k Cr'), row('HDFC Bal Adv', 'H', R, '+6.4k Cr'), row('Nippon SC', 'N', E, '+6.1k Cr'), row('ICICI Bluechip', 'I', O, '+5.6k Cr')] },
  { title: 'Fastest Growing AUM', q: 'Quickest growth', icon: '🚀', color: B, rows: [row('Quant SC', 'Q', V, '+52%'), row('Bandhan SC', 'B', B, '+38%'), row('HDFC Health', 'H', R, '+34%'), row('Tata Digital', 'T', C, '+29%')] },
  { title: 'Retail Favorites', q: 'Most popular', icon: '❤️', color: P, rows: [row('Parag Parikh', 'P', N, '#1'), row('Axis Small Cap', 'A', R, '#2'), row('Mirae ELSS', 'M', V, '#3'), row('HDFC Flexi', 'H', R, '#4')] },
];
export const IMPROVED_RAIL: Rail[] = [
  { title: 'Biggest Rank Jump', q: 'Climbed most', icon: '📈', color: E, rows: [row('HDFC Healthcare', 'H', R, '+11'), row('Bandhan SC', 'B', B, '+12'), row('Quant SC', 'Q', V, '+9'), row('SBI Contra', 'S', B, '+7')] },
  { title: 'Label Upgrades', q: 'Moved to a stronger label', icon: '⬆', color: B, rows: [row('HDFC Health', 'H', R, 'Watch → On Track'), row('SBI Contra', 'S', B, 'Off Form → Watch'), row('Kotak EE', 'K', E, 'On Track → In Form'), row('Bandhan SC', 'B', B, 'Watch → On Track')] },
  { title: 'Entering Top 10', q: 'New arrivals', icon: '🌟', color: G, rows: [row('Bandhan SC', 'B', B, '#3'), row('SBI Contra', 'S', B, '#5'), row('Nippon SC', 'N', E, '#7'), row('Kotak EE', 'K', E, '#9')] },
];
export const TREND_RAIL: Rail[] = [
  { title: 'Biggest Rank Jump', q: 'Up the most', icon: '📈', color: E, rows: [row('HDFC Healthcare', 'H', R, '+11'), row('Bandhan SC', 'B', B, '+12'), row('Quant SC', 'Q', V, '+9'), row('SBI Contra', 'S', B, '+7')] },
  { title: 'Biggest Rank Drop', q: 'Down the most', icon: '📉', color: R, rows: [row('ICICI Tech', 'I', O, '−4', false), row('Motilal Nasdaq', 'M', V, '−3', false), row('Axis Midcap', 'A', P, '−2', false), row('Gold FOF', 'G', A, '−2', false)] },
  { title: 'Highest AUM Growth', q: 'Fastest inflows', icon: '🐋', color: B, rows: [row('Quant SC', 'Q', V, '+52%'), row('Bandhan SC', 'B', B, '+38%'), row('HDFC Health', 'H', R, '+34%'), row('Tata Digital', 'T', C, '+29%')] },
  { title: 'Highest Investor Interest', q: 'Most viewed', icon: '👀', color: O, rows: [row('Parag Parikh', 'P', N, '#1'), row('Bandhan SC', 'B', B, '#2'), row('Axis SC', 'A', R, '#3'), row('HDFC Health', 'H', R, '#4')] },
];

// ── Current market (DMMI) ────────────────────────────────────────────────────
export type DmmiFund = { name: string; logo: string; color: string };
const f = (name: string, logo: string, color: string): DmmiFund => ({ name, logo, color });
export const DMMI = {
  value: 62,
  mood: 'Cautiously Optimistic',
  phase: 'Accumulation phase',
  strategy: 'Typical phase: Accumulation',
  best: [f('Parag Parikh', 'P', N), f('SBI Contra', 'S', B), f('ICICI Bluechip', 'I', O)],
  sip: [f('Bandhan Small Cap', 'B', B), f('Kotak Emerging', 'K', E), f('Mirae ELSS', 'M', V)],
  lump: [f('ICICI Bluechip', 'I', O), f('HDFC Bal Adv', 'H', R), f('Parag Parikh', 'P', N)],
  out: [f('Motilal Nasdaq', 'M', V), f('ICICI Tech', 'I', O), f('Gold FOFs', 'G', A)],
};

// ── V5 — regime teach-mode copy (MarketSection) ─────────────────────────────
// Static, reviewed, educational. Describes what a phase has historically meant
// for volatility/investor behaviour — NEVER predicts what happens next, never
// advice. Keyed by the real mood Regime enum (components/mood/MoodGauge.tsx);
// 'insufficient_data'/'data_unavailable' are intentionally absent — the
// section renders nothing new for those (honest: no phase to describe).
export const REGIME_EXPLAINER: Record<string, string> = {
  extreme_fear: 'In sharp downturns like this, markets have historically swung more than usual and many investors have favoured steadier, lower-volatility funds. Phases pass — this describes today’s mood, it predicts nothing.',
  fear: 'In cautious phases, markets tend to swing more and investors often favour steadier funds. Phases pass — this describes today, it predicts nothing.',
  neutral: 'In neutral phases, market direction has been more balanced and swings closer to average. This describes current conditions — it is not a forecast.',
  greed: 'In confident phases, markets tend to run hotter and valuations can stretch further. This describes today’s mood — it says nothing about what happens next.',
  extreme_greed: 'In euphoric phases, markets have historically been more prone to sharp swings once sentiment turns. This describes today, not a prediction.',
};

// ── Best managers ────────────────────────────────────────────────────────────
export type Manager = {
  name: string; av: string; color: string; exp: string; funds: string; score: number;
  beating: string; success: string; topFund: string; rating: string;
};
export const MGR: Manager[] = [
  { name: 'Rajeev Thakkar', av: 'RT', color: N, exp: '22 yrs', funds: '3 funds', score: 93, beating: '9/10', success: '98%', topFund: 'Parag Parikh Flexi', rating: '★★★★★' },
  { name: 'Sankaran Naren', av: 'SN', color: O, exp: '28 yrs', funds: '5 funds', score: 89, beating: '8/10', success: '94%', topFund: 'ICICI Bluechip', rating: '★★★★★' },
  { name: 'Roshi Jain', av: 'RJ', color: R, exp: '18 yrs', funds: '2 funds', score: 88, beating: '8/10', success: '92%', topFund: 'HDFC Flexi Cap', rating: '★★★★☆' },
  { name: 'Sailesh Raj Bhan', av: 'SB', color: E, exp: '24 yrs', funds: '4 funds', score: 88, beating: '8/10', success: '93%', topFund: 'Nippon Small Cap', rating: '★★★★★' },
  { name: 'Harsha Upadhyaya', av: 'HU', color: B, exp: '20 yrs', funds: '3 funds', score: 86, beating: '7/10', success: '90%', topFund: 'Kotak Emerging', rating: '★★★★☆' },
  { name: 'Neelesh Surana', av: 'NS', color: C, exp: '21 yrs', funds: '4 funds', score: 86, beating: '8/10', success: '91%', topFund: 'Mirae Large Cap', rating: '★★★★★' },
];

// ── Best AMCs ────────────────────────────────────────────────────────────────
export type Amc = {
  name: string; av: string; color: string; score: number; topFunds: number; confidence: string;
  aum: string; age: string; indexFunds: number; trust: string;
};
export const AMC: Amc[] = [
  { name: 'HDFC Mutual Fund', av: 'H', color: R, score: 90, topFunds: 12, confidence: 'High', aum: '₹6.2L Cr', age: '29 yrs', indexFunds: 82, trust: '★★★★★' },
  { name: 'ICICI Prudential', av: 'I', color: O, score: 89, topFunds: 10, confidence: 'High', aum: '₹7.4L Cr', age: '25 yrs', indexFunds: 76, trust: '★★★★★' },
  { name: 'SBI Mutual Fund', av: 'S', color: B, score: 87, topFunds: 9, confidence: 'Very High', aum: '₹9.1L Cr', age: '37 yrs', indexFunds: 68, trust: '★★★★☆' },
  { name: 'Mirae Asset', av: 'M', color: C, score: 88, topFunds: 6, confidence: 'High', aum: '₹1.8L Cr', age: '16 yrs', indexFunds: 24, trust: '★★★★★' },
  { name: 'Parag Parikh (PPFAS)', av: 'P', color: N, score: 93, topFunds: 3, confidence: 'Very High', aum: '₹98k Cr', age: '12 yrs', indexFunds: 8, trust: '★★★★★' },
  { name: 'Kotak Mahindra', av: 'K', color: E, score: 86, topFunds: 8, confidence: 'High', aum: '₹4.2L Cr', age: '26 yrs', indexFunds: 54, trust: '★★★★☆' },
  { name: 'Axis Mutual Fund', av: 'A', color: R, score: 84, topFunds: 7, confidence: 'Moderate', aum: '₹3.1L Cr', age: '15 yrs', indexFunds: 42, trust: '★★★★☆' },
];

// ── AI insights ──────────────────────────────────────────────────────────────
export const AI_INSIGHTS = [
  '**Small Cap continues to dominate long-term rankings** — but the gap with Flexi Cap on a risk-adjusted basis is narrowing.',
  '**Index funds now lead cost efficiency** — UTI Nifty 50 returns the most per rupee of fee, at just 0.20%.',
  '**Healthcare funds are climbing rapidly** — HDFC Healthcare jumped 11 ranks on strong pharma earnings.',
  '**Current DMMI favors Flexi Cap funds** — they balance the upside of this market with protection if it turns.',
  '**Category money is on the move** — Flexi Cap and Small Cap drew the largest net inflows this month.',
  '**International funds are out of favour** — high valuations and a strong rupee have pulled them down the rankings.',
];

// ── FAQ ──────────────────────────────────────────────────────────────────────
export const FAQ: [string, string][] = [
  ['How are DhanRadar rankings calculated?', 'We score every fund 0–100 on six factors — returns, risk control, consistency, cost, manager quality and portfolio quality — normalised within each category so funds are compared fairly. Funds are then ranked by this composite, not by past returns alone.'],
  ['How is the "Steady SIP Starters" list built?', 'By a fixed, published rule — not advice: large-cap and hybrid funds (excluding arbitrage) whose educational label is On Track or better, ordered by how steady their rolling 1-year returns have been. It is an educational shortlist for learning what steadier funds look like, never a recommendation.'],
  ['How often are rankings updated?', 'Scores and ranks recompute daily after market close using the latest NAV, portfolio disclosures and flow data.'],
  ['What is a Hidden Gem?', 'A fund that scores highly on DhanRadar intelligence but hasn’t yet attracted big inflows or wide attention — strong fundamentals before the crowd notices.'],
  ['How is "Strong on All Three Lenses" built?', 'By a fixed, published rule — not advice: active growth funds that sit in the top quarter of their own category on all three lenses at once — 3-year return, deepest fall, and yearly cost — shown by highest 3-year return. Only categories with at least 8 fully-measured funds qualify. It exists to show the trade-off: being strong on returns, risk control and cost together is rare.'],
];

// ── Filter sheet (mobile) ────────────────────────────────────────────────────
export const FILTER_GROUPS: [string, string[]][] = [
  ['Category', ['Equity', 'Debt', 'Hybrid', 'Index', 'ELSS', 'International']],
  ['Sub-category', ['Large Cap', 'Flexi Cap', 'Mid Cap', 'Small Cap', 'Value']],
  ['Risk', ['Low', 'Moderate', 'Mod. High', 'High', 'Very High']],
  ['DMMI Fit', ['Best in Fear', 'Best in Recovery', 'Best in Bull']],
];

// Sticky category nav anchors
export const CATNAV: { id: string; label: string }[] = [
  { id: 'top100', label: 'Top 100' },
  { id: 'champions', label: 'Champions' },
  { id: 'performance', label: 'Performance' },
  { id: 'sip', label: 'SIP' },
  { id: 'risk', label: 'Risk' },
  { id: 'value', label: 'Value' },
  { id: 'intelligence', label: 'Intelligence' },
  { id: 'market', label: 'Market Now' },
  { id: 'flows', label: 'Flows' },
  { id: 'improved', label: 'Improved' },
  { id: 'managers', label: 'Managers' },
  { id: 'amc', label: 'AMCs' },
  { id: 'trending', label: 'Trending' },
];
