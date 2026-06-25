/**
 * Portfolio Command Center — illustrative PREVIEW data.
 * Pure-UI build: all values are illustrative.
 * Compliance: composite scores kept as internal seeds only;
 * DOM renders band/word (non-neg #2). Educational labels (non-neg #1).
 */

import type { Strength, Band3 } from '@/components/mf/funddetail/sampleData';

export const COLORS = {
  E: '#00B386', B: '#1E5EFF', A: '#F5A623', R: '#E5484D',
  O: '#F97316', V: '#8B5CF6', C: '#00C2FF', N: '#0B1F3A',
  P: '#EC4899', T: '#14B8A6', G: '#D4A017',
} as const;

const { E, B, A, R, O, V, C, N, P, T, G } = COLORS;

// Score → band/strength helpers (mirrors leaderboard pattern)
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
export function ringColor(score: number): string {
  return score >= 85 ? E : score >= 70 ? B : score >= 55 ? A : score >= 40 ? O : R;
}
export function riskColor(rk: string): string {
  return ({ Low: E, Moderate: A, 'Mod. High': O, High: R, 'Very High': R } as Record<string, string>)[rk] ?? A;
}
export const STRENGTH_WORD: Record<Strength, string> = { strong: 'Strong', good: 'Good', moderate: 'Fair', soft: 'Soft' };
export const STRENGTH_COLOR: Record<Strength, string> = { strong: E, good: C, moderate: A, soft: R };

// ── Hero stats ──────────────────────────────────────────────────────────────
export const HERO = {
  totalValue: '₹48,32,640',
  gain: '+₹9,84,210 · 25.6%',
  invested: '₹38,48,430',
  todayGain: '+₹18,420 (0.38%)',
  // portfolioScore: 82 — internal seed only; renders as BandRing + 'Good'
  portfolioScore: 82,
  strengthWord: 'Good',
  label: 'Healthy Portfolio',
  sub: 'Top 18% diversification · Top 22% overall',
  stats: [
    { label: 'XIRR', value: '16.8%', color: '#6EE7B7' },
    { label: 'Monthly SIP', value: '₹42,000' },
    { label: 'Portfolio Age', value: '7.2 yrs' },
    { label: 'Funds', value: '9' },
    { label: 'AMCs', value: '7' },
    { label: '1-Day', value: '+0.38%', color: '#6EE7B7' },
  ],
  statusPills: [
    { text: 'Well Diversified', color: E },
    { text: 'Moderate-High Risk', color: A },
    { text: 'Healthy Returns', color: E },
    { text: 'Good SIP Discipline', color: E },
    { text: 'Needs Rebalancing', color: O },
    { text: 'Tax Efficient', color: E },
  ],
};

// ── Health checks ────────────────────────────────────────────────────────────
export type HealthLight = 'g' | 'y' | 'r';
export type HealthCard = { title: string; light: HealthLight; stat: string; exp: string; tip: string };
export const HEALTH: HealthCard[] = [
  { title: 'Diversification', light: 'g', stat: 'Good', exp: 'Spread across 9 funds & 7 AMCs.', tip: 'Healthy — maintain.' },
  { title: 'Risk', light: 'y', stat: 'Medium-High', exp: 'Small-cap tilt raises swings.', tip: 'Trim small-cap by ~10%.' },
  { title: 'Returns', light: 'g', stat: 'Strong', exp: 'Beating benchmark on 3Y/5Y.', tip: 'Stay invested.' },
  { title: 'Cost', light: 'g', stat: 'Low', exp: '0.80% weighted — below average.', tip: '2 funds could be cheaper.' },
  { title: 'Fund Quality', light: 'g', stat: 'High', exp: '7 of 9 funds score 80+.', tip: 'Review the 2 laggards.' },
  { title: 'Manager Quality', light: 'g', stat: 'Strong', exp: 'Avg tenure 9 yrs, stable.', tip: 'No action needed.' },
  { title: 'Market Cap Mix', light: 'r', stat: 'Skewed', exp: '38% small-cap vs 25% ideal.', tip: 'Rebalance to large-cap.' },
  { title: 'Sector Balance', light: 'y', stat: 'Concentrated', exp: 'Financials 24% — slightly high.', tip: 'Watch financial exposure.' },
  { title: 'AMC Concentration', light: 'g', stat: 'Balanced', exp: 'Top AMC is 22% of corpus.', tip: 'Within safe limits.' },
  { title: 'Portfolio Fit', light: 'g', stat: 'Good', exp: 'Matches your moderate-aggressive profile.', tip: 'On track.' },
];

// ── Actions ──────────────────────────────────────────────────────────────────
export type ActionPri = 'high' | 'med' | 'low';
export type Action = { pri: ActionPri; title: string; desc: string; impact: string; cta: string };
export const ACTIONS: Action[] = [
  { pri: 'high', title: 'Small-cap allocation is too high', desc: 'Small caps are 38% of your equity vs a recommended 25% for your profile. This raises how much your portfolio can fall in a downturn.', impact: 'Could reduce worst-case fall by ~6%', cta: 'Rebalance' },
  { pri: 'high', title: '3 funds have significant overlap', desc: "Your two small-cap funds and one index fund share 50%+ of holdings. You're paying multiple fees for similar exposure.", impact: 'Save ~₹14,200/yr in fees', cta: 'Review overlap' },
  { pri: 'med', title: 'Debt allocation is below recommended', desc: 'Only 3.5% of your portfolio is in debt. A 10–15% debt cushion would smooth out the ride.', impact: 'Lower volatility by ~3%', cta: 'Add debt fund' },
  { pri: 'med', title: 'One fund is underperforming peers', desc: 'HDFC Mid Cap IDCW ranks in the bottom quartile of its category over 3 years.', impact: 'Move could add ~2.4%/yr', cta: 'See alternatives' },
  { pri: 'low', title: 'Portfolio risk increased recently', desc: 'Your risk score rose from 64 to 71 this quarter as small-caps rallied and grew in weight.', impact: 'Monitor monthly', cta: 'View risk' },
];

// ── DMMI ─────────────────────────────────────────────────────────────────────
export const DMMI_VAL = 62;
export const DMMI_MOOD = 'Cautiously Optimistic';
export const DMMI_PHASE = 'Accumulation phase';
export const DMMI_METRICS = [
  { label: 'Portfolio suitability', value: 'Good fit', color: E, detail: 'Your equity-heavy mix suits an accumulation phase.' },
  { label: 'In similar conditions (10 yr)', value: '+14.2% avg', color: E, detail: 'Your portfolio style returned positive in 7 of 9 similar phases.' },
  { label: 'Expected price swings', value: 'Medium-High', color: A, detail: 'Brace for ±12–15% swings given small-cap tilt.' },
  { label: 'Suggested action', value: 'Continue SIP', color: B, detail: 'Keep SIPs running; stagger any fresh lumpsum.' },
];

// ── Allocation ───────────────────────────────────────────────────────────────
export type AllocRow = [string, number, number, string]; // [name, current%, ideal%, color]
export type AllocTab = { sowhat: string; rows: AllocRow[] };
export const ALLOC: Record<string, AllocTab> = {
  'Asset': { sowhat: 'Your portfolio is 96% equity and just 3.5% debt. A 10–15% debt allocation is recommended for your age and goals — it cushions falls without sacrificing much growth.', rows: [['Equity', 96.5, 85, E], ['Debt', 3.5, 12, B], ['Gold', 0, 3, A]] },
  'Category': { sowhat: 'Small Cap dominates at 38%. Flexi Cap (a more balanced choice) is underweight. Shifting ~10% from small to flexi-cap improves your risk-adjusted return.', rows: [['Small Cap', 38, 25, B], ['Flexi Cap', 22, 30, E], ['Large Cap', 16, 25, C], ['Mid Cap', 18, 12, V], ['ELSS', 6, 8, A]] },
  'Sector': { sowhat: 'Financials at 24% is your largest sector bet. Healthcare and Industrials are well-represented. No single sector is dangerously concentrated.', rows: [['Financials', 24, 18, B], ['Industrials', 18, 15, C], ['Healthcare', 15, 12, E], ['Technology', 12, 14, V], ['Consumer', 11, 13, A], ['Others', 20, 28, '#94A3B8']] },
  'Market Cap': { sowhat: '84% of your equity sits in small & mid caps. That is aggressive — great in bull runs, painful in corrections. Large caps provide stability you currently lack.', rows: [['Small Cap', 52, 30, B], ['Mid Cap', 32, 25, C], ['Large Cap', 16, 45, E]] },
  'AMC': { sowhat: 'HDFC is your largest AMC exposure at 22%. That is within safe limits (we flag above 30%). Your AMC spread is healthy.', rows: [['HDFC', 22, 20, B], ['Axis', 17, 15, C], ['Nippon', 14, 12, E], ['Mirae', 12, 12, V], ['ICICI', 11, 12, A], ['Others', 24, 29, '#94A3B8']] },
  'Style': { sowhat: 'Your portfolio leans Growth (62%). A bit more Value exposure would diversify your style risk — growth and value tend to outperform in different cycles.', rows: [['Growth', 62, 50, B], ['Value', 23, 35, E], ['Blend', 15, 15, C]] },
  'Geography': { sowhat: 'You have zero international exposure. Adding 5–10% global equity (e.g. a US index fund) reduces your dependence on the Indian market alone.', rows: [['India', 100, 90, B], ['International', 0, 10, E]] },
};
export const ALLOC_TABS = Object.keys(ALLOC);

// ── Goals ────────────────────────────────────────────────────────────────────
export const GOALS = [
  { icon: '🏖', name: 'Retirement', meta: '2045 · 19 yrs left', color: E, target: '₹3.2 Cr', current: '₹48.3 L', gap: '₹2.72 Cr', pct: 15, status: 'On Track' },
  { icon: '🎓', name: 'Children Education', meta: '2032 · 6 yrs left', color: B, target: '₹85 L', current: '₹12.4 L', gap: '₹72.6 L', pct: 15, status: 'Slightly behind' },
  { icon: '🏠', name: 'House Purchase', meta: '2029 · 3 yrs left', color: A, target: '₹40 L', current: '₹8.6 L', gap: '₹31.4 L', pct: 22, status: 'Needs more SIP' },
];

// ── Performance ──────────────────────────────────────────────────────────────
export const PERF_DATA: { series: string; color: string; vals: number[] }[] = [
  { series: 'Portfolio', color: E, vals: [2.1, 6.8, 11.2, 18.4, 21.6, 19.8, 16.8] },
  { series: 'NIFTY 50', color: O, vals: [1.2, 4.2, 8.1, 12.6, 15.2, 14.1, 12.4] },
  { series: 'Category Avg', color: '#94A3B8', vals: [1.6, 5.1, 9.4, 14.8, 17.1, 15.9, 13.8] },
];
export const PERF_PERIODS = ['1M', '3M', '6M', '1Y', '3Y', '5Y', 'Since Start'];

// ── Holdings ─────────────────────────────────────────────────────────────────
export type Holding = {
  name: string; cat: string; logo: string; color: string;
  value: number; invested: number;
  score: number; // internal seed — renders as BandRing + strength word, NOT the number
  status: string; xirr: number; risk: string;
};
export const HOLDINGS: Holding[] = [
  { name: 'HDFC NIFTY Smallcap 250 Index', cat: 'Index / Small Cap Index', logo: 'H', color: B, value: 533110, invested: 500000, score: 84, status: 'In Form', xirr: 16.6, risk: 'High' },
  { name: 'Axis Small Cap Fund', cat: 'Equity / Small Cap', logo: 'A', color: R, value: 427829, invested: 340000, score: 88, status: 'On Track', xirr: 13.8, risk: 'High' },
  { name: 'Parag Parikh Flexi Cap', cat: 'Equity / Flexi Cap', logo: 'P', color: N, value: 892400, invested: 620000, score: 93, status: 'In Form', xirr: 18.5, risk: 'Mod. High' },
  { name: 'Invesco India Smallcap', cat: 'Equity / Small Cap', logo: 'I', color: C, value: 370380, invested: 310000, score: 82, status: 'In Form', xirr: 12.4, risk: 'High' },
  { name: 'ICICI Pru Bluechip', cat: 'Equity / Large Cap', logo: 'I', color: O, value: 684000, invested: 560000, score: 86, status: 'On Track', xirr: 14.2, risk: 'Moderate' },
  { name: 'Mirae Asset ELSS Tax Saver', cat: 'ELSS', logo: 'M', color: V, value: 248000, invested: 210000, score: 85, status: 'On Track', xirr: 11.6, risk: 'Mod. High' },
  { name: 'Kotak Emerging Equity', cat: 'Equity / Mid Cap', logo: 'K', color: E, value: 421000, invested: 330000, score: 85, status: 'In Form', xirr: 13.4, risk: 'High' },
  { name: 'HDFC Mid Cap Fund IDCW', cat: 'Equity / Mid Cap', logo: 'H', color: R, value: 156100, invested: 168000, score: 68, status: 'Off Track', xirr: -2.1, risk: 'High' },
  { name: 'HDFC Corporate Bond', cat: 'Debt / Corporate Bond', logo: 'H', color: R, value: 169821, invested: 160000, score: 77, status: 'On Track', xirr: 7.6, risk: 'Low' },
];

// ── Top performers ────────────────────────────────────────────────────────────
export const TOP_PERF = [
  { cat: 'Best Fund', name: 'Parag Parikh Flexi', logo: 'P', color: N, val: 'Highest quality + consistency', sub: 'score: Strong' },
  { cat: 'Highest Return', name: 'Axis Small Cap', logo: 'A', color: R, val: '+25.8%', sub: 'Best absolute gain' },
  { cat: 'Best SIP', name: 'HDFC Smallcap Index', logo: 'H', color: B, val: '18.4% XIRR', sub: 'Top monthly-investor return' },
  { cat: 'Most Consistent', name: 'ICICI Bluechip', logo: 'I', color: O, val: '9/10 yrs', sub: 'Beat category 9 of 10 years' },
  { cat: 'Lowest Risk', name: 'HDFC Corp Bond', logo: 'H', color: R, val: '0.4% swings', sub: 'Smoothest ride' },
  { cat: 'Biggest Winner', name: 'Parag Parikh', logo: 'P', color: N, val: '+₹2.72 L', sub: 'Largest rupee gain' },
  { cat: 'Most Improved', name: 'Kotak Emerging', logo: 'K', color: E, val: '+11 ranks', sub: 'Climbed fastest this Q' },
  { cat: 'Tax Efficient', name: 'Mirae ELSS', logo: 'M', color: V, val: '80C saver', sub: 'Saves tax + grows' },
];

// ── Funds needing review ─────────────────────────────────────────────────────
export const UNDER_REVIEW = [
  { name: 'HDFC Mid Cap Fund IDCW', logo: 'H', color: R, reason: 'Ranks in bottom quartile of Mid Cap funds over 3 years. Returns −2.1% XIRR while category averages +13%. Manager changed 18 months ago.', tags: ['Bottom 25%', 'Off Track', '−2.1% XIRR'], action: 'Review', alt: 'Kotak Emerging Equity (Good rating)', altColor: O },
  { name: 'Invesco India Smallcap', logo: 'I', color: C, reason: 'Solid fund but overlaps 58% with your Axis Small Cap. You hold near-duplicate exposure across two funds and two fee structures.', tags: ['58% overlap', 'Duplicate risk', 'In Form'], action: 'Reduce', alt: 'Consolidate into Axis Small Cap', altColor: A },
];

// ── Overlap ──────────────────────────────────────────────────────────────────
export const OVERLAP = [
  { aName: 'Axis Small Cap', aLogo: 'A', aColor: R, bName: 'Invesco Smallcap', bLogo: 'I', bColor: C, pct: 58, verdict: 'Too Much Overlap', vColor: R, rec: 'These two funds hold 58% of the same stocks. Consolidate into Axis (higher-rated) to cut fees and duplicate risk.' },
  { aName: 'HDFC Smallcap Index', aLogo: 'H', aColor: B, bName: 'Axis Small Cap', bLogo: 'A', bColor: R, pct: 42, verdict: 'High Overlap', vColor: O, rec: 'An index and active small-cap fund overlap heavily. Decide: passive (cheaper) or active (Axis), not both at full weight.' },
  { aName: 'Parag Parikh Flexi', aLogo: 'P', aColor: N, bName: 'ICICI Bluechip', bLogo: 'I', bColor: O, pct: 31, verdict: 'Medium Overlap', vColor: A, rec: 'Some large-cap overlap, but Parag Parikh adds global stocks. This pairing is acceptable.' },
  { aName: 'Kotak Emerging', aLogo: 'K', aColor: E, bName: 'HDFC Mid Cap', bLogo: 'H', bColor: R, pct: 28, verdict: 'Healthy', vColor: E, rec: 'Low overlap — these two mid-cap funds complement rather than duplicate each other.' },
];

// ── Diversification ──────────────────────────────────────────────────────────
// Internal seed: 78 — renders as BandRing + strength word, NOT the number
export const DIV_SCORE = 78;
export const DIV_BARS = [
  { name: 'Sector', cur: 82, ideal: 85, tip: 'Well spread across 8 sectors. Healthcare could grow slightly.' },
  { name: 'Market Cap', cur: 58, ideal: 80, tip: 'Too concentrated in small & mid caps — add large caps.' },
  { name: 'AMC', cur: 84, ideal: 80, tip: 'Healthy spread across 7 fund houses.' },
  { name: 'Fund Style', cur: 66, ideal: 75, tip: 'Growth-tilted — add value exposure.' },
  { name: 'Geography', cur: 12, ideal: 60, tip: 'Almost entirely India — add 5–10% global.' },
];

// ── Risk ─────────────────────────────────────────────────────────────────────
// Portfolio Risk Score 71 — renders as 'Moderate-High' word, NOT the number
export const RISK_CARDS = [
  { label: 'Portfolio Risk', value: 'Moderate-High', desc: 'Based on your fund mix and volatility', color: A },
  { label: 'Biggest Historical Fall', value: '−34%', desc: 'In the 2020 crash', color: R },
  { label: 'Recovery Time', value: '11 months', desc: 'To regain peak', color: B },
  { label: 'Price Swings', value: '±14%', desc: 'Typical yearly range', color: A },
];
export const ADV_METRICS = [
  { name: 'Sharpe Ratio', value: '1.18', desc: 'Return per unit of risk', judge: 'Good (>1)' },
  { name: 'Sortino Ratio', value: '1.64', desc: 'Return per unit of downside', judge: 'Strong' },
  { name: 'Alpha', value: '+3.2%', desc: 'Excess return vs benchmark', judge: 'Positive' },
  { name: 'Beta', value: '1.12', desc: 'Sensitivity to market', judge: 'Slightly aggressive' },
  { name: 'Max Drawdown', value: '−34%', desc: 'Worst peak-to-trough', judge: 'High' },
  { name: 'Std Deviation', value: '16.4%', desc: 'How much returns vary', judge: 'Moderate-High' },
];

// ── Cost ─────────────────────────────────────────────────────────────────────
// Cost Efficiency 86 — renders as 'Good' word, NOT 86/100
export const COST_CARDS = [
  { value: '0.80%', label: 'Weighted Expense', color: E },
  { value: '₹38,660', label: 'Annual Cost', color: '#0F172A' },
  { value: '₹6.4 L', label: '10-Year Cost', color: O },
  { value: 'Good', label: 'Cost Efficiency', color: B }, // was "86/100" — compliance bridge
];

// ── AMC exposure ─────────────────────────────────────────────────────────────
// AMC Quality scores render as strength WORD, not raw number
export const AMC_LIST = [
  { name: 'HDFC', logo: 'H', color: R, pct: 22, qualityScore: 90, qualityWord: 'Excellent' },
  { name: 'Axis', logo: 'A', color: R, pct: 17, qualityScore: 86, qualityWord: 'Good' },
  { name: 'Nippon', logo: 'N', color: E, pct: 14, qualityScore: 84, qualityWord: 'Good' },
  { name: 'Mirae', logo: 'M', color: V, pct: 12, qualityScore: 88, qualityWord: 'Excellent' },
  { name: 'ICICI', logo: 'I', color: O, pct: 11, qualityScore: 87, qualityWord: 'Excellent' },
  { name: 'Kotak', logo: 'K', color: E, pct: 9, qualityScore: 85, qualityWord: 'Good' },
  { name: 'Invesco', logo: 'I', color: C, pct: 8, qualityScore: 79, qualityWord: 'Fair' },
];

// ── Timeline ─────────────────────────────────────────────────────────────────
export const TIMELINE = [
  { date: 'Jun 2026', title: 'SIP invested', desc: '₹42,000 across 8 funds', color: E, icon: '↑' },
  { date: 'Apr 2026', title: 'Portfolio crossed ₹48 L', desc: 'New all-time high', color: B, icon: '★' },
  { date: 'Feb 2026', title: 'Added Kotak Emerging Equity', desc: 'New mid-cap position · ₹50,000', color: V, icon: '+' },
  { date: 'Nov 2025', title: 'Partial redemption', desc: '₹1.2 L from HDFC Mid Cap', color: O, icon: '↓' },
  { date: 'Aug 2025', title: 'Stepped up SIP', desc: '₹32,000 → ₹42,000 monthly', color: E, icon: '↑' },
  { date: 'Jan 2019', title: 'Started investing', desc: 'First SIP · ₹15,000', color: N, icon: '●' },
];

// ── Recommendations ──────────────────────────────────────────────────────────
export const RECS = [
  { title: 'Rebalance small-cap down', desc: 'Trim small-cap from 38% to 25% by moving ~₹6.3 L into your flexi-cap and large-cap funds. Reduces worst-case fall without hurting long-term returns much.', tags: [{ text: 'High impact', color: R }, { text: 'Lower risk 6%', color: B }] },
  { title: 'Consolidate overlapping funds', desc: 'Merge Invesco Smallcap into Axis Small Cap (58% overlap). One fewer fee, cleaner portfolio, same exposure.', tags: [{ text: 'Save ₹14,200/yr', color: E }, { text: 'Medium', color: A }] },
  { title: 'Add international exposure', desc: 'You have 0% global equity. Add 5–8% via a US index fund to reduce dependence on the Indian market.', tags: [{ text: 'Diversify', color: V }, { text: 'Medium', color: A }] },
  { title: 'Build a debt cushion', desc: 'Raise debt from 3.5% to 12%. A debt fund smooths the ride and gives you dry powder to deploy in corrections.', tags: [{ text: 'Lower volatility', color: B }, { text: 'Medium', color: A }] },
  { title: 'Replace HDFC Mid Cap IDCW', desc: 'Bottom-quartile for 3 years. Move to Kotak Emerging Equity (Good rating) for better risk-adjusted returns.', tags: [{ text: '+2.4%/yr', color: E }, { text: 'Review', color: O }] },
  { title: 'Move to direct/growth plans', desc: 'Confirm all funds are Direct plans. IDCW (dividend) plans are tax-inefficient for long-term wealth.', tags: [{ text: 'Tax efficient', color: E }, { text: 'Low', color: B }] },
];

// ── Projection ───────────────────────────────────────────────────────────────
export const PROJ: Record<string, { name: string; val: string; color: string }[]> = {
  '5 Years': [
    { name: 'Current SIP (₹42k)', val: '₹1.18 Cr', color: E },
    { name: '+10% SIP', val: '₹1.24 Cr', color: B },
    { name: '+20% SIP', val: '₹1.31 Cr', color: V },
    { name: '+50% SIP', val: '₹1.52 Cr', color: O },
  ],
  '10 Years': [
    { name: 'Current SIP (₹42k)', val: '₹2.84 Cr', color: E },
    { name: '+10% SIP', val: '₹3.06 Cr', color: B },
    { name: '+20% SIP', val: '₹3.28 Cr', color: V },
    { name: '+50% SIP', val: '₹3.94 Cr', color: O },
  ],
  '15 Years': [
    { name: 'Current SIP (₹42k)', val: '₹5.92 Cr', color: E },
    { name: '+10% SIP', val: '₹6.45 Cr', color: B },
    { name: '+20% SIP', val: '₹6.98 Cr', color: V },
    { name: '+50% SIP', val: '₹8.56 Cr', color: O },
  ],
  '20 Years': [
    { name: 'Current SIP (₹42k)', val: '₹11.4 Cr', color: E },
    { name: '+10% SIP', val: '₹12.6 Cr', color: B },
    { name: '+20% SIP', val: '₹13.8 Cr', color: V },
    { name: '+50% SIP', val: '₹17.4 Cr', color: O },
  ],
};
export const PROJ_TABS = Object.keys(PROJ);

// ── Opportunities (watchlist) ────────────────────────────────────────────────
export const WATCHLIST = [
  { name: 'Motilal Nasdaq 100 FOF', logo: 'M', color: V, why: 'You have zero international exposure. This adds clean US-tech diversification.', benefits: ['Fills geography gap', 'Lowers India-only risk', '+0.6 diversification score'] },
  { name: 'HDFC Balanced Advantage', logo: 'H', color: R, why: 'Auto-balances equity & debt. A smoother core holding to offset your small-cap swings.', benefits: ['Adds debt cushion', 'Reduces volatility ~3%', 'Good rating'] },
  { name: 'ICICI Pru Value Discovery', logo: 'I', color: O, why: 'Your portfolio is growth-tilted. This value fund balances your style risk.', benefits: ['Adds value exposure', 'Diversifies style', 'Good rating'] },
];

// ── AI Feed ──────────────────────────────────────────────────────────────────
export const AI_FEED = [
  'Your portfolio is **heavily tilted toward small caps (38%)** — great in rallies, but expect bigger falls in corrections.',
  '**Fund overlap increased** this month as your small-cap funds converged on the same winning stocks.',
  '**Healthcare exposure grew** to 15% — your funds added pharma names that are outperforming.',
  'Current **DMMI favors your portfolio** — the accumulation phase historically rewards your equity-heavy mix.',
  'Your **debt allocation remains low at 3.5%** — a small cushion would smooth your ride considerably.',
  '**SIP discipline is excellent** — 7 years of uninterrupted monthly investing puts you ahead of 80% of investors.',
];

// ── Report Center ────────────────────────────────────────────────────────────
export const REPORTS = [
  { icon: '📄', title: 'Portfolio Report', desc: 'Full PDF summary', color: B },
  { icon: '🧾', title: 'Tax Report', desc: 'Capital gains for ITR', color: E },
  { icon: '📊', title: 'Holdings Report', desc: 'Detailed fund breakdown', color: V },
  { icon: '🤖', title: 'AI Summary', desc: 'Plain-English review', color: O },
  { icon: '✉', title: 'Email Report', desc: 'Send to your inbox', color: C },
];

// ── FAQ ──────────────────────────────────────────────────────────────────────
export const FAQ: [string, string][] = [
  ['What is the Portfolio Score?', "A composite rating summarising your portfolio's overall health across diversification, risk, returns, cost, fund quality and fit. It's normalised so you can track it over time and compare against other DhanRadar investors."],
  ['How is overlap calculated?', 'We compare the actual stock holdings of any two funds and measure what percentage they share by weight. Above 50% means you\'re largely paying twice for the same exposure.'],
  ['Why is diversification important?', 'Diversification spreads your risk so one bad sector, stock or fund manager can\'t sink your whole portfolio. We score it across sectors, market caps, AMCs, styles and geography.'],
  ['What is DMMI suitability?', 'The DhanRadar Market Mood Index (DMMI) gauges overall market sentiment. "Suitability" tells you whether your specific portfolio mix is well-positioned for the current market phase, based on how similar portfolios behaved historically.'],
  ['How are recommendations generated?', 'We compare your current allocation, overlap, cost and risk against ideal targets for your profile, then surface the highest-impact fixes first — always explained in plain English with the expected benefit.'],
  ['Is my data safe?', "Your CAS is parsed securely and never shared. DhanRadar is a research platform — we don't execute trades or hold your money. We only analyse what you upload."],
];

// ── Benefits grid (empty state) ──────────────────────────────────────────────
export const BENEFITS = [
  { icon: '🎯', title: 'Portfolio Rating', desc: 'One composite rating for overall health', color: B },
  { icon: '🛡', title: 'Risk Analysis', desc: 'How much your portfolio can fall', color: R },
  { icon: '🔗', title: 'Overlap Detection', desc: 'Find funds holding the same stocks', color: V },
  { icon: '📈', title: 'Wealth Forecast', desc: 'See your money in 5, 10, 20 years', color: E },
  { icon: '🌡', title: 'DMMI Insights', desc: 'Is your mix right for this market?', color: A },
  { icon: '💡', title: 'Recommendations', desc: 'Exactly what to fix, in plain English', color: C },
  { icon: '🎓', title: 'Goal Tracking', desc: 'Are you on track for retirement?', color: T },
  { icon: '🧩', title: 'Diversification', desc: 'Spot gaps and concentration risk', color: P },
];

// ── Auto sync pills ──────────────────────────────────────────────────────────
export const AUTOSYNC_PILLS = ['Automatic updates', 'Daily tracking', 'Portfolio alerts', 'Performance monitoring', 'Goal monitoring'];

// suppress unused-variable warnings for palette vars used in data literals
void [O, V, C, N, P, T, G];
