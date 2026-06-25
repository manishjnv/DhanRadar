/**
 * Watchlist Monitor — illustrative PREVIEW data.
 *
 * Pure-UI build (founder call 2026-06-25 — build all UI now, wire data later):
 * every value here is illustrative. The real watchlist pipeline (save / track /
 * alerts / compare / export) is wired in a later session.
 *
 * Compliance bridges (same as Portfolio / Leaderboard / Compare V-pages):
 *   1. No raw DhanRadar composite score in the DOM — composite scores are kept
 *      as internal SEEDS only; the DOM renders a band ring + a strength WORD.
 *   2. Educational momentum / verdict labels only — never advisory verbs
 *      (buy / sell / hold / switch / avoid / caution are rejected by CI).
 * Public facts DhanRadar does not compute (NAV, returns, cost, AUM, rank,
 * category, DMMI mood index) are DOM-allowed.
 */

import type { Strength, Band3 } from '@/components/mf/funddetail/sampleData';

// Warm brand palette (live tokens — reconciled toward the brand guide).
export const COLORS = {
  E: '#00B386', B: '#1E5EFF', A: '#F5A623', R: '#E5484D',
  O: '#F97316', V: '#8B5CF6', C: '#00C2FF', N: '#0B1F3A',
  P: '#EC4899', T: '#14B8A6', S: '#64748B',
} as const;

const { E, B, A, R, O, V, C, N, P } = COLORS;

// ── Score → band / strength helpers (composite stays internal) ───────────────
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
export const STRENGTH_WORD: Record<Strength, string> = {
  strong: 'Strong', good: 'Good', moderate: 'Fair', soft: 'Soft',
};
export const STRENGTH_COLOR: Record<Strength, string> = {
  strong: E, good: C, moderate: A, soft: R,
};
export function ringColor(score: number): string {
  return score >= 85 ? E : score >= 70 ? B : score >= 55 ? A : score >= 40 ? O : R;
}
export function riskColor(rk: string): string {
  return ({ Low: E, Moderate: A, 'Mod. High': O, High: R, 'Very High': R } as Record<string, string>)[rk] ?? A;
}
/** Educational verdict label (replaces the mockup's advisory verbs). */
export function verdictOf(score: number): [string, string] {
  if (score >= 85) return ['In Form', E];
  if (score >= 72) return ['On Track', B];
  if (score >= 60) return ['Watch', A];
  if (score >= 48) return ['Neutral', COLORS.S];
  return ['Needs Review', R];
}
/** Educational momentum label. */
export function momentumOf(st: string): [string, string] {
  return ({
    Improving: ['▲ Improving', E],
    Trending: ['◆ Trending', O],
    Stable: ['● Stable', B],
    Declining: ['▼ Declining', R],
  } as Record<string, [string, string]>)[st] ?? ['● Stable', B];
}

export function fmtAum(v: number): string {
  return v >= 10000 ? `₹${(v / 1000).toFixed(1)}k Cr` : `₹${v.toLocaleString('en-IN')} Cr`;
}

// ── Fund model ───────────────────────────────────────────────────────────────
export type Fund = {
  name: string; amc: string; cat: string; logo: string; color: string;
  age: number; nav: number; chg: number;
  /** internal composite SEED — never rendered as a number; drives band/word */
  score: number;
  risk: string; rank: number; r3: number; r5: number;
  /** internal SIP-suitability SEED — rendered as a strength word */
  sip: number; exp: number; aum: number; dmmi: string; status: string;
};

const F = (
  name: string, amc: string, cat: string, logo: string, color: string,
  age: number, nav: number, chg: number, score: number, risk: string,
  rank: number, r3: number, r5: number, sip: number, exp: number,
  aum: number, dmmi: string, status: string,
): Fund => ({ name, amc, cat, logo, color, age, nav, chg, score, risk, rank, r3, r5, sip, exp, aum, dmmi, status });

export const FUNDS: Fund[] = [
  F('Parag Parikh Flexi Cap', 'PPFAS MF', 'Flexi Cap', 'P', N, 12, 84.21, 0.51, 93, 'Mod. High', 1, 22.4, 21.8, 94, 0.62, 78420, 'Excellent', 'Trending'),
  F('ICICI Pru Bluechip', 'ICICI MF', 'Large Cap', 'I', O, 16, 102.84, 0.38, 87, 'Moderate', 2, 17.8, 16.4, 87, 0.52, 68400, 'Excellent', 'Improving'),
  F('Axis Small Cap Fund', 'Axis MF', 'Small Cap', 'A', R, 13, 256.40, -0.42, 88, 'High', 4, 27.1, 28.4, 87, 0.68, 42100, 'Good', 'Stable'),
  F('Kotak Emerging Equity', 'Kotak MF', 'Mid Cap', 'K', E, 17, 184.50, 0.62, 85, 'High', 4, 25.2, 25.6, 84, 0.46, 42100, 'Good', 'Improving'),
  F('SBI Contra Fund', 'SBI MF', 'Value', 'S', B, 18, 312.60, 0.71, 87, 'Mod. High', 3, 28.2, 24.8, 86, 0.62, 38600, 'Excellent', 'Improving'),
  F('HDFC Smallcap Index', 'HDFC MF', 'Small Cap Index', 'H', B, 6, 142.30, -0.57, 84, 'High', 4, 28.6, 26.1, 90, 0.42, 9840, 'Good', 'Trending'),
  F('Mirae ELSS Tax Saver', 'Mirae MF', 'ELSS', 'M', V, 9, 38.42, 0.34, 85, 'Mod. High', 2, 21.4, 20.8, 85, 0.58, 24800, 'Excellent', 'Stable'),
  F('Quant Small Cap', 'Quant MF', 'Small Cap', 'Q', V, 5, 256.40, -0.84, 78, 'Very High', 7, 31.0, 30.2, 80, 0.64, 24180, 'Average', 'Declining'),
];

export const DMMI_COLOR: Record<string, string> = { Excellent: E, Good: B, Average: A, Poor: R };

// ── Hero ─────────────────────────────────────────────────────────────────────
export const HERO = {
  title: 'My Watchlist',
  sub: '8 funds you’re tracking · Updated 25 Jun 2026, 6:00 PM',
  // KPI 'value' is a WORD/fact — no raw composite score reaches the DOM.
  kpis: [
    { label: 'Funds Tracked', value: '8' },
    { label: 'Avg Strength', value: 'Strong', color: '#6EE7B7' },
    { label: 'Avg Risk', value: 'High' },
    { label: 'Top Rated', value: 'Parag Parikh', sub: 'Strong', small: true },
    { label: 'Improved ▲', value: '3', color: '#6EE7B7' },
    { label: 'Declined ▼', value: '1', color: '#FCA5A5' },
  ] as { label: string; value: string; sub?: string; color?: string; small?: boolean }[],
  summary: [
    { n: '4', color: '#6EE7B7', text: 'In Form' },
    { n: '3', color: '#FBBF24', text: 'Watch' },
    { n: '1', color: '#FCA5A5', text: 'Needs Review' },
    { n: '62 Cautious+', color: '#FBBF24', text: '🌡 DMMI:', prefix: true },
  ] as { n: string; color: string; text: string; prefix?: boolean }[],
  actions: [
    { label: '⇄ Compare Selected', primary: true },
    { label: '+ Explore Funds' },
    { label: '⬇ Export' },
  ] as { label: string; primary?: boolean }[],
};

// ── Empty state ──────────────────────────────────────────────────────────────
export const BENEFITS: [string, string, string, string][] = [
  ['📊', 'Track performance', 'See NAV, returns & strength daily', B],
  ['🤖', 'Get AI insights', 'Plain-English nudges on each fund', V],
  ['⇄', 'Compare funds', 'Shortlist and compare side by side', C],
  ['🏆', 'Monitor rankings', 'Know when a fund climbs or falls', E],
  ['🌡', 'DMMI suitability', 'Is each fund right for this market?', A],
  ['💡', 'Recommendations', 'Discover better alternatives', O],
];

// ── AI summaries / insights ──────────────────────────────────────────────────
export const AI_SUMMARY: string[] = [
  '**3 funds look excellent for SIPs today** — Parag Parikh, ICICI Bluechip and Kotak Emerging all rank in the strong band with steady consistency.',
  '**2 funds improved their ranking this week** — Kotak Emerging climbed to #4 and SBI Contra to #3 in their categories.',
  '**Small-cap funds continue to attract inflows** — but valuations are stretched, so fresh entries are often staggered.',
  '**Current market suits most of your watchlist** — 5 of 8 funds are well-positioned for this accumulation phase.',
];
export const INSIGHTS: string[] = [
  '**Most of your watchlist is Small Cap (3 of 8 funds)** — strong upside, but expect bigger swings if the market corrects.',
  '**Current market suits your large-cap & flexi-cap funds** — ICICI Bluechip and Parag Parikh are best-positioned now.',
  '**Your watchlist carries high overall risk** — a low-risk or debt fund would balance it.',
  '**Axis and Quant Small Cap have similar portfolios** — you may not need to track both.',
];

// ── Filters ──────────────────────────────────────────────────────────────────
export const FILTER_CHIPS: [string, number][] = [
  ['All', 8], ['In Form', 4], ['Improving', 3], ['Low Risk', 2],
  ['Best SIP', 3], ['Small Cap', 3], ['Needs Review', 1],
];
export const SORT_OPTIONS = ['Recently Added', 'DhanRadar Strength', 'Returns', 'Risk', 'Fund Size', 'Alphabetical'];

// ── What changed ─────────────────────────────────────────────────────────────
export const CHANGED: [string, string, string, string, string, string, string][] = [
  ['Kotak Emerging', 'K', E, 'Rank improved from #6 to #4', '📈', E, '2 days ago'],
  ['SBI Contra', 'S', B, 'DhanRadar strength rose into the strong band', '⬆', E, '3 days ago'],
  ['HDFC Smallcap Index', 'H', B, 'Fund flows increased +₹420 Cr', '🐋', B, '4 days ago'],
  ['Mirae ELSS', 'M', V, 'Annual cost reduced 0.62% → 0.58%', '💰', E, '5 days ago'],
  ['Quant Small Cap', 'Q', V, 'Risk increased — price swings up 18%', '⚠', R, '6 days ago'],
  ['Axis Small Cap', 'A', R, 'Sector allocation updated — added pharma', '🔄', B, '1 week ago'],
];

// ── Opportunities ────────────────────────────────────────────────────────────
export const OPPORTUNITIES: [string, string, string, string, string, string][] = [
  ['Best SIP Fund', 'HDFC SC Index', 'H', B, 'Strong', 'SIP fit'],
  ['Lowest Risk', 'Mirae ELSS', 'M', V, 'Mod.', 'Risk level'],
  ['Highest Growth', 'Quant Small Cap', 'Q', V, '31%', '3Y return'],
  ['Lowest Cost', 'HDFC SC Index', 'H', B, '0.42%', 'Annual cost'],
  ['Most Consistent', 'Parag Parikh', 'P', N, '9/10', 'Yrs beat cat'],
  ['Best DMMI Match', 'ICICI Bluechip', 'I', O, 'Excellent', 'Market fit'],
  ['Best Beginner', 'Parag Parikh', 'P', N, 'Top pick', 'Low drama'],
  ['Highest Rated', 'Parag Parikh', 'P', N, 'Strong', 'DhanRadar'],
];

// ── DMMI ─────────────────────────────────────────────────────────────────────
export const DMMI = {
  value: 62,
  mood: 'Cautiously Optimistic',
  phase: 'Accumulation phase',
  best: [
    ['Parag Parikh', 'P', N, '+ Best fit'],
    ['ICICI Bluechip', 'I', O, '+ Stable'],
    ['SBI Contra', 'S', B, '+ Value play'],
  ] as [string, string, string, string][],
  risk: [
    ['Quant Small Cap', 'Q', V, 'High swings'],
    ['Axis Small Cap', 'A', R, 'Stretched'],
    ['HDFC SC Index', 'H', B, 'Watch'],
  ] as [string, string, string, string][],
  soWhat:
    '**Market mood is Cautiously Optimistic (62/100).** 5 of your 8 funds are well-positioned for this accumulation phase. The two small-cap funds carry the most short-term swing risk if sentiment turns.',
};

// ── Performance ──────────────────────────────────────────────────────────────
export const PERF_TABS = ['Returns', 'Rolling Returns', 'Ranking Trend', 'SIP Growth'];
export const PERF_HEAD = ['Series', '1M', '3M', '6M', '1Y', '3Y', '5Y'];
export const PERF_ROWS: [string, number, number, number, number, number, number][] = [
  ['Watchlist Avg', 2.1, 6.8, 11.2, 18.4, 25.6, 23.1],
  ['Category Avg', 1.6, 5.1, 9.4, 14.8, 19.2, 17.4],
  ['NIFTY 50', 1.2, 4.2, 8.1, 12.6, 15.2, 14.1],
];

// ── Smart alerts ─────────────────────────────────────────────────────────────
export const ALERTS: [string, string, string, string, string][] = [
  ['Fund entered Top 10', 'Kotak Emerging is now #4 in Mid Cap', '📈', E, '2d'],
  ['Strength downgraded', 'Quant Small Cap eased to the good band', '⬇', R, '3d'],
  ['Risk increased', 'Quant Small Cap price swings up 18%', '⚠', O, '3d'],
  ['Annual cost changed', 'Mirae ELSS cut cost to 0.58%', '💰', E, '5d'],
  ['Fund manager changed', 'HDFC Mid Cap got a new manager', '👤', A, '1w'],
  ['AUM crossed milestone', 'Parag Parikh crossed ₹78,000 Cr', '🏆', B, '1w'],
];

// ── Similar funds ────────────────────────────────────────────────────────────
export const SIMILAR: [string, string, string, string, string[]][] = [
  ['↗ Higher return than Axis Small Cap', 'Nippon India Small Cap', 'N', E, ['+1.3% better 5Y return', 'Larger, more stable AUM', 'Strong band']],
  ['↗ Lower risk than Quant Small Cap', 'Kotak Small Cap', 'K', E, ['Smoother ride, lower swings', 'Better downside protection', 'Good band']],
  ['↗ Higher strength than HDFC SC Index', 'Bandhan Small Cap', 'B', B, ['Active management edge', 'Strong vs good band', 'Lower drawdown']],
];

// ── Statistics ───────────────────────────────────────────────────────────────
export const STATS: [string, string, string][] = [
  ['+25.4%', 'Avg Return', E],
  ['High', 'Avg Risk', O],
  ['0.57%', 'Avg Cost', 'var(--ink, #0F172A)'],
  ['Strong', 'Avg Strength', B],
];
export const CATEGORY_MIX: [string, number, string][] = [
  ['Small Cap', 3, B], ['Flexi', 1, E], ['Large', 1, C], ['Mid', 1, V], ['Value', 1, A], ['ELSS', 1, P],
];

// ── Discovery ────────────────────────────────────────────────────────────────
export const DISCOVERY: [string, string, string, string][] = [
  ['🔥', 'Trending Funds', 'Hot this week', O],
  ['✨', 'New Launches', 'Fresh NFOs', V],
  ['⭐', 'Top Rated', 'Strong band', E],
  ['📈', 'Most Improved', 'Climbing ranks', B],
  ['🐋', 'Highest Inflows', 'Smart money', C],
  ['💰', 'Best SIP', 'Top monthly', E],
  ['🏦', 'Best ELSS', 'Tax savers', A],
  ['📊', 'Best Index', 'Lowest cost', N],
];

// ── Recently viewed ──────────────────────────────────────────────────────────
export const RECENTLY_VIEWED: [string, string, string, string][] = [
  ['Nippon India Small Cap', 'N', E, 'Small Cap · Strong'],
  ['Bandhan Small Cap', 'B', B, 'Small Cap · Strong'],
  ['Canara Robeco Bluechip', 'C', B, 'Large Cap · Good'],
  ['Motilal Nasdaq 100', 'M', V, 'Intl · Fair'],
  ['HDFC Balanced Adv', 'H', R, 'Hybrid · Good'],
];

// ── FAQ ──────────────────────────────────────────────────────────────────────
export const FAQ: [string, string][] = [
  ['How does the Watchlist work?', 'Save any fund you’re researching and DhanRadar tracks its NAV, strength, ranking, risk and DMMI fit daily. It surfaces what changed, flags what needs attention, and helps you decide when to keep watching or compare.'],
  ['Will my watchlist update automatically?', 'Yes. Strength bands, NAVs, rankings and flows refresh daily after market close. The “What Changed” and “Smart Alerts” sections highlight anything that moved since you last checked.'],
  ['How is the DhanRadar strength band calculated?', 'A composite of returns, risk control, consistency, cost, manager quality and portfolio quality — normalised within each category so funds are compared fairly, and shown as an educational band rather than a raw number.'],
  ['How do I compare funds?', 'Tap ⇄ on any fund card to shortlist it. Select up to 4, then open Compare in the tray to see them side by side across every metric.'],
  ['Can I export my watchlist?', 'Yes — use Export in the action bar to download your watchlist with all metrics as a CSV or PDF.'],
];

// ── Mobile filter sheet groups ───────────────────────────────────────────────
export const FILTER_GROUPS: [string, string[]][] = [
  ['Category', ['Equity', 'Debt', 'Hybrid', 'Index', 'ELSS']],
  ['Sub-category', ['Large Cap', 'Flexi Cap', 'Mid Cap', 'Small Cap', 'Value']],
  ['Risk', ['Low', 'Moderate', 'Mod. High', 'High', 'Very High']],
  ['AI Recommendation', ['In Form', 'On Track', 'Watch', 'Needs Review']],
  ['DMMI Fit', ['Excellent', 'Good', 'Average']],
  ['Momentum', ['Improving', 'Trending', 'Stable', 'Declining']],
];
