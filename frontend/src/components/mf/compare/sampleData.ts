/**
 * Fund Comparison V3 — illustrative sample data + compliance mappings.
 *
 * This is the ONLY place raw comparison numbers live. The DOM never renders a
 * DhanRadar-computed numeric score (non-neg #2) — instead every computed score
 * is mapped here to a STRENGTH word (Strong/Good/Moderate/Soft) or a Label/band,
 * and only those qualitative tokens cross into the section components.
 *
 * Factual, published fund metrics (returns, NAV, AUM, expense ratio, P/E, ROE,
 * Sharpe, tax, holdings, flows) are NOT computed by DhanRadar and ARE allowed in
 * the DOM as plain facts — same line the Fund Detail V3 page draws.
 *
 * Founder rule 2026-06-24: build the full UI now with illustrative "Preview"
 * data; wire real feeds later. No API / routing / permission changes.
 */
import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';
import type { Strength } from '@/components/mf/funddetail/sampleData';

// ───────────────────────────────────────────────────────────────────────────
// Fund identity (accent colours are decorative, kept from the V3 mockup)
// ───────────────────────────────────────────────────────────────────────────
export interface CompareFund {
  key: string;
  name: string;
  short: string;
  cat: string;
  amc: string;
  logo: string;
  color: string;          // accent (decorative)
  topGradient: string;    // header gradient (decorative)
  /** Compliance: educational label + band instead of a 0–100 score. */
  label: Label;
  band: ConfidenceBand;
  assessWord: string;     // qualitative read shown in the hero ring meta
  nav: string;
  navc: string;
  aum: string;
  exp: string;
  age: string;
  mgr: string;
  badges: string[];
  isTopMatch?: boolean;
}

export const FUNDS: CompareFund[] = [
  {
    key: 'bandhan', name: 'Bandhan Small Cap Fund', short: 'Bandhan', cat: 'Small Cap · Direct',
    amc: 'Bandhan MF', logo: 'B', color: '#1E5EFF', topGradient: 'linear-gradient(135deg,#0B1F3A,#1E5EFF)',
    label: 'in_form', band: 'high', assessWord: 'Strong all-round',
    nav: '48.92', navc: '+0.70%', aum: '9,420 Cr', exp: '0.42%', age: '6.3 yrs', mgr: 'Manish Nigam',
    badges: ['Best Overall', 'Best SIP', 'Best Fit'], isTopMatch: true,
  },
  {
    key: 'nippon', name: 'Nippon India Small Cap', short: 'Nippon', cat: 'Small Cap · Direct',
    amc: 'Nippon MF', logo: 'N', color: '#00B386', topGradient: 'linear-gradient(135deg,#064E3B,#00B386)',
    label: 'in_form', band: 'high', assessWord: 'Highest raw returns',
    nav: '178.40', navc: '+0.92%', aum: '58,200 Cr', exp: '0.68%', age: '12.4 yrs', mgr: 'Samir Rachh',
    badges: ['Highest Return', 'Best Lumpsum', 'Largest AMC'],
  },
  {
    key: 'quant', name: 'Quant Small Cap Fund', short: 'Quant', cat: 'Small Cap · Direct',
    amc: 'Quant MF', logo: 'Q', color: '#8B5CF6', topGradient: 'linear-gradient(135deg,#4C1D95,#8B5CF6)',
    label: 'on_track', band: 'medium', assessWord: 'Most aggressive',
    nav: '256.40', navc: '+1.24%', aum: '24,180 Cr', exp: '0.64%', age: '9.1 yrs', mgr: 'Ankit Pande',
    badges: ['Most Aggressive', 'Best Momentum'],
  },
];

export const TOP_MATCH = FUNDS.find((f) => f.isTopMatch)!;

// Map an internal 0–100 score to a compliant STRENGTH word (no number leaks).
export function toStrength(score: number): Strength {
  if (score >= 88) return 'strong';
  if (score >= 78) return 'good';
  if (score >= 65) return 'moderate';
  return 'soft';
}

// ───────────────────────────────────────────────────────────────────────────
// S2 — Educational read (was "Comparison Winner / Recommended Choice")
// ───────────────────────────────────────────────────────────────────────────
export const EDU_READ = {
  fund: 'Bandhan Small Cap Fund',
  band: 'high' as ConfidenceBand,
  why: [
    'Most consistent — top quartile in 5 of the last 6 years',
    "Lower expense ratio (0.42% vs Quant's 0.64%)",
    'Better downside protection in 2022 (−24% vs −31%)',
    'Stronger, more stable fund-manager record',
    'Broadest diversification (252 stocks)',
  ],
  notFor: [
    'If you want the absolute highest upside — Quant leads there',
    'If you already own a Nippon small-cap (high overlap)',
    'If you want the lowest possible volatility',
  ],
  bestAt: [
    ['Best for SIP', 'Bandhan'],
    ['Best lumpsum', 'Nippon'],
    ['Most conservative', 'Bandhan'],
    ['Most aggressive', 'Quant'],
  ] as [string, string][],
};

// ───────────────────────────────────────────────────────────────────────────
// S3 — Scoreboard: 12 modules → strength words (winner = highest internal score)
// ───────────────────────────────────────────────────────────────────────────
export const SCOREBOARD: { metric: string; scores: number[] }[] = [
  { metric: 'Overall', scores: [92, 94, 88] },
  { metric: 'Performance', scores: [93, 95, 97] },
  { metric: 'Consistency', scores: [90, 86, 74] },
  { metric: 'Risk (lower hits = better)', scores: [76, 72, 58] },
  { metric: 'Momentum', scores: [88, 84, 96] },
  { metric: 'Valuation', scores: [71, 68, 52] },
  { metric: 'Cost Efficiency', scores: [88, 72, 75] },
  { metric: 'Fund Flow', scores: [95, 90, 82] },
  { metric: 'Manager Quality', scores: [88, 86, 80] },
  { metric: 'Portfolio Quality', scores: [85, 82, 73] },
  { metric: 'Tax Efficiency', scores: [90, 90, 90] },
  { metric: 'SIP Quality', scores: [92, 86, 84] },
];

// ───────────────────────────────────────────────────────────────────────────
// S4 — Who each fund suits (was "Who Should Buy Which Fund")
// ───────────────────────────────────────────────────────────────────────────
export const PERSONAS: { ico: string; name: string; tone: string; best: string; why: string }[] = [
  { ico: '🌱', name: 'New investor', tone: '#00B386', best: 'Bandhan', why: 'Smoothest ride — least likely to unsettle a first-timer.' },
  { ico: '🛡️', name: 'Conservative', tone: '#1E5EFF', best: 'Bandhan', why: 'Best downside protection of the three.' },
  { ico: '🚀', name: 'Aggressive', tone: '#8B5CF6', best: 'Quant', why: 'Highest upside & momentum, if you can hold through dips.' },
  { ico: '👴', name: 'Near retirement', tone: '#1E5EFF', best: 'Bandhan', why: 'Consistency matters more than max return near a goal.' },
  { ico: '🧑', name: 'Young, long horizon', tone: '#8B5CF6', best: 'Quant', why: 'A long horizon can absorb volatility for higher growth.' },
  { ico: '💎', name: 'Large portfolio', tone: '#00B386', best: 'Nippon', why: 'Scale, liquidity and the longest track record.' },
  { ico: '🔁', name: 'Long-term SIP', tone: '#00B386', best: 'Bandhan', why: 'Best rolling-return consistency for disciplined SIPs.' },
  { ico: '💰', name: 'Lump-sum', tone: '#00B386', best: 'Nippon', why: 'Strongest record deploying large amounts at once.' },
];

// ───────────────────────────────────────────────────────────────────────────
// S5 — Decision matrix (reasons are factual, not numeric scores)
// ───────────────────────────────────────────────────────────────────────────
export const MATRIX: { ico: string; q: string; win: string; val: string }[] = [
  { ico: '📈', q: 'Want highest return?', win: 'Quant', val: 'best raw returns' },
  { ico: '🛡️', q: 'Want lowest risk?', win: 'Bandhan', val: 'best downside capture' },
  { ico: '🔁', q: 'Want best SIP fit?', win: 'Bandhan', val: 'best consistency' },
  { ico: '💸', q: 'Want lowest cost?', win: 'Bandhan', val: '0.42% expense' },
  { ico: '👔', q: 'Want strongest manager?', win: 'Bandhan', val: 'most stable record' },
  { ico: '🧩', q: 'Want best diversification?', win: 'Bandhan', val: '252 stocks' },
  { ico: '⬇️', q: 'Want downside protection?', win: 'Bandhan', val: '−24% vs −31%' },
  { ico: '🧾', q: 'Want best tax efficiency?', win: 'All equal', val: 'same LTCG' },
  { ico: '🎯', q: 'Want best portfolio fit?', win: 'Bandhan', val: 'only 9% overlap' },
];

// ───────────────────────────────────────────────────────────────────────────
// Generic comparison tables (factual data — allowed in DOM)
// type: 'hi' winner = max, 'low' winner = min |abs|, undefined = no winner
// ───────────────────────────────────────────────────────────────────────────
export type Row = { label: string; vals: (string | number | null)[]; win?: 'hi' | 'low'; tone?: 'pos' | 'neg' };

export const DMMI: Row[] = [
  { label: 'Fear markets', vals: ['−24%', '−28%', '−34%'], tone: 'neg' },
  { label: 'Recovery (best)', vals: ['+38%', '+41%', '+52%'], tone: 'pos' },
  { label: 'Neutral', vals: ['+14%', '+13%', '+11%'], tone: 'pos' },
  { label: 'Bull markets', vals: ['+29%', '+31%', '+38%'], tone: 'pos' },
  { label: 'Euphoria', vals: ['+11%', '+9%', '+6%'], tone: 'pos' },
  { label: 'Hit-rate now', vals: ['73%', '71%', '64%'], win: 'hi' },
];

export const PERF: Row[] = [
  { label: '1M', vals: [5.8, 6.1, 7.2], win: 'hi' },
  { label: '3M', vals: [14.2, 15.1, 18.4], win: 'hi' },
  { label: '6M', vals: [21.4, 22.8, 28.1], win: 'hi' },
  { label: '1Y', vals: [24.6, 26.2, 31.8], win: 'hi' },
  { label: '3Y', vals: [28.4, 29.1, 33.6], win: 'hi' },
  { label: '5Y', vals: [26.1, 27.4, 30.2], win: 'hi' },
  { label: '10Y', vals: [null, 21.8, null], win: 'hi' },
  { label: 'Since launch', vals: [22.8, 24.1, 26.9], win: 'hi' },
];

export const ROLLING: Row[] = [
  { label: '1Y avg', vals: ['23.1%', '24.0%', '27.2%'], win: 'hi' },
  { label: '3Y avg', vals: ['27.6%', '28.2%', '31.1%'], win: 'hi' },
  { label: '5Y avg', vals: ['25.2%', '26.1%', '28.4%'], win: 'hi' },
  { label: 'Beat category %', vals: ['78%', '74%', '68%'], win: 'hi' },
  { label: 'Beat benchmark %', vals: ['71%', '69%', '72%'], win: 'hi' },
];

export const RANKT: Row[] = [
  { label: 'Current rank', vals: ['#2', '#1', '#5'], win: 'low' },
  { label: 'Average rank (3Y)', vals: ['#3', '#2', '#6'], win: 'low' },
  { label: 'Best rank', vals: ['#1', '#1', '#1'] },
  { label: 'Worst rank', vals: ['#5', '#4', '#14'], win: 'low' },
];

export const RANK_SERIES: Record<string, number[]> = {
  bandhan: [4, 3, 3, 2, 3, 2, 3, 2, 2, 2],
  nippon: [2, 2, 1, 1, 2, 1, 2, 1, 1, 1],
  quant: [8, 6, 5, 7, 4, 5, 3, 6, 5, 5],
};

export const RISK_HEAT: { label: string; vals: string[]; better: 'low' | 'hi' }[] = [
  { label: 'Worst fall', vals: ['−24%', '−28%', '−31%'], better: 'low' },
  { label: 'Recovery time', vals: ['8 mo', '9 mo', '11 mo'], better: 'low' },
  { label: 'Volatility', vals: ['18.6%', '19.8%', '22.4%'], better: 'low' },
  { label: 'Max drawdown', vals: ['−24.3%', '−28.1%', '−31.4%'], better: 'low' },
  { label: 'Downside capture', vals: ['92%', '98%', '108%'], better: 'low' },
  { label: 'Upside capture', vals: ['101%', '106%', '118%'], better: 'hi' },
];

export const ADV_RISK: Row[] = [
  { label: 'Sharpe', vals: ['1.24', '1.18', '1.12'], win: 'hi' },
  { label: 'Sortino', vals: ['1.78', '1.66', '1.54'], win: 'hi' },
  { label: 'Alpha', vals: ['+3.2%', '+2.8%', '+4.1%'], win: 'hi' },
  { label: 'Beta', vals: ['0.94', '0.98', '1.12'], win: 'low' },
  { label: 'Std deviation', vals: ['18.6%', '19.8%', '22.4%'], win: 'low' },
  { label: 'Treynor', vals: ['0.21', '0.19', '0.18'], win: 'hi' },
  { label: 'Tracking error', vals: ['2.1%', '2.4%', '3.6%'], win: 'low' },
  { label: 'Information ratio', vals: ['0.82', '0.74', '0.68'], win: 'hi' },
];

// S12 — Portfolio fit
export const FIT: { key: string; label: string; tone: string; best?: boolean; rows: [string, string][] }[] = [
  { key: 'bandhan', label: 'Best Fit', tone: '#00B386', best: true, rows: [['Overlap with your portfolio', '9%'], ['Diversification impact', '+12%'], ['Sector overlap', 'Low'], ['Portfolio risk change', '+0.4%'], ['Return impact', '+1.8%'], ['Illustrative weight', '8–12%']] },
  { key: 'nippon', label: 'Moderate Fit', tone: '#F5A623', rows: [['Overlap with your portfolio', '22%'], ['Diversification impact', '+6%'], ['Sector overlap', 'Medium'], ['Portfolio risk change', '+0.6%'], ['Return impact', '+1.9%'], ['Illustrative weight', '6–10%']] },
  { key: 'quant', label: 'Moderate Fit', tone: '#F5A623', rows: [['Overlap with your portfolio', '17%'], ['Diversification impact', '+8%'], ['Sector overlap', 'Medium'], ['Portfolio risk change', '+1.1%'], ['Return impact', '+2.4%'], ['Illustrative weight', '5–8%']] },
];

// S13 — Holdings
export const HOLD_STATS: Row[] = [
  { label: 'Common holdings (all 3)', vals: ['18', '18', '18'] },
  { label: 'Unique holdings', vals: ['142', '98', '64'] },
  { label: 'Total stocks', vals: ['252', '164', '78'] },
  { label: 'Top-10 weight', vals: ['42%', '46%', '58%'], win: 'low' },
  { label: 'Top-20 weight', vals: ['58%', '63%', '74%'], win: 'low' },
  { label: 'Concentration', vals: ['Low', 'Medium', 'High'] },
];

export const HOLDINGS: Record<string, [string, number, boolean][]> = {
  bandhan: [['Karur Vysya Bank', 2.4, true], ['Sona BLW', 2.2, false], ['Navin Fluorine', 2.1, true], ['Delhivery', 1.9, false], ['Cyient', 1.8, true]],
  nippon: [['Tube Investments', 3.1, true], ['Karur Vysya Bank', 2.8, true], ['Multi Commodity', 2.4, false], ['Navin Fluorine', 2.2, true], ['NLC India', 2.0, false]],
  quant: [['Reliance Inds', 4.2, false], ['Aegis Logistics', 3.8, false], ['Karur Vysya Bank', 3.4, true], ['Bikaji Foods', 3.1, false], ['RBL Bank', 2.9, false]],
};

export const FLOW: Row[] = [
  { label: 'Net inflows (1Y)', vals: ['+₹2,840 Cr', '+₹6,120 Cr', '+₹3,410 Cr'] },
  { label: 'AUM growth (1Y)', vals: ['+38%', '+24%', '+52%'], win: 'hi' },
  { label: 'Investor confidence', vals: ['Strong', 'Strong', 'Moderate'] },
  { label: 'Positive flow months', vals: ['12/12', '11/12', '10/12'], win: 'hi' },
  { label: 'Flow trend', vals: ['Strong Positive', 'Strong Positive', 'Positive'] },
];

// S15 — Managers (manager "score" → strength word)
export const MGRS: { key: string; name: string; init: string; tone: string; tag: string; best?: boolean; strengthScore: number; rows: [string, string][] }[] = [
  { key: 'bandhan', name: 'Manish Nigam', init: 'MN', tone: '#00B386', tag: 'Best stability', best: true, strengthScore: 88, rows: [['Experience', '18 yrs'], ['Tenure (this fund)', '6.3 yrs'], ['Funds managed', '4'], ['Yrs beating category', '5 / 6'], ['Manager changes', '0']] },
  { key: 'nippon', name: 'Samir Rachh', init: 'SR', tone: '#1E5EFF', tag: 'Highest alpha', strengthScore: 86, rows: [['Experience', '30 yrs'], ['Tenure (this fund)', '8.2 yrs'], ['Funds managed', '3'], ['Yrs beating category', '7 / 8'], ['Manager changes', '1']] },
  { key: 'quant', name: 'Ankit Pande', init: 'AP', tone: '#8B5CF6', tag: '', strengthScore: 80, rows: [['Experience', '12 yrs'], ['Tenure (this fund)', '4.5 yrs'], ['Funds managed', '6'], ['Yrs beating category', '3 / 5'], ['Manager changes', '2']] },
];

// S16 — AMC (rating/trust → strength via stars; trust number dropped)
export const AMC: Row[] = [
  { label: 'AMC rating', vals: ['★ 4.4', '★ 4.7', '★ 4.2'] },
  { label: 'AMC AUM', vals: ['₹1.4L Cr', '₹4.9L Cr', '₹0.9L Cr'] },
  { label: 'Years in business', vals: ['25', '30', '18'] },
  { label: 'Operational stability', vals: ['High', 'Very High', 'High'] },
  { label: 'Trust band', vals: ['Strong', 'Very Strong', 'Good'] },
];

// S17 — Cost (cost "score" → strength word)
export const COST: Row[] = [
  { label: 'Expense ratio', vals: ['0.42%', '0.68%', '0.64%'], win: 'low' },
  { label: 'Exit load', vals: ['1% <1yr', '1% <1yr', '1% <1yr'] },
  { label: 'Portfolio turnover', vals: ['38%', '42%', '118%'], win: 'low' },
  { label: 'Tracking error', vals: ['2.1%', '2.4%', '3.6%'], win: 'low' },
  { label: 'Cost efficiency', vals: ['Strong', 'Moderate', 'Good'] },
];

export const COST_VIS: [string, number, string][] = [
  ['Bandhan', 2.6, '#00B386'],
  ['Quant', 4.1, '#8B5CF6'],
  ['Nippon', 4.4, '#1E5EFF'],
];

// S18 — Tax (all identical, factual)
export const TAX: Row[] = [
  { label: 'Capital gain', vals: ['₹2,00,000', '₹2,00,000', '₹2,00,000'] },
  { label: 'LTCG exemption', vals: ['−₹1,25,000', '−₹1,25,000', '−₹1,25,000'] },
  { label: 'Taxable gain', vals: ['₹75,000', '₹75,000', '₹75,000'] },
  { label: 'LTCG tax @12.5%', vals: ['₹9,375', '₹9,375', '₹9,375'] },
  { label: 'Exit load', vals: ['₹0', '₹0', '₹0'] },
  { label: 'Post-tax value', vals: ['₹1,90,625', '₹1,90,625', '₹1,90,625'] },
];

// S19 — Valuation (val "score" → strength word; verdict band words)
export const VAL: Row[] = [
  { label: 'Portfolio P/E', vals: ['28.4', '29.1', '34.8'], win: 'low' },
  { label: 'Portfolio P/B', vals: ['4.1', '4.3', '5.6'], win: 'low' },
  { label: 'Earnings growth', vals: ['22%', '21%', '28%'], win: 'hi' },
  { label: 'ROE', vals: ['16.8%', '15.4%', '14.1%'], win: 'hi' },
  { label: 'ROCE', vals: ['18.2%', '17.1%', '15.6%'], win: 'hi' },
];
export const VAL_VERDICT: [string, string][] = [['Fair', '#00B386'], ['Fair', '#00B386'], ['Expensive', '#F5A623']];

// S20 — What changed
export const CHANGES: Record<string, ['up' | 'down' | 'info', string, string][]> = {
  bandhan: [['up', 'Category rank improved #3 → #2', '4 days ago'], ['up', 'Financial Services +3.2%', '2 weeks ago'], ['down', 'Top-10 concentration 48% → 42%', '3 weeks ago']],
  nippon: [['up', 'AUM crossed ₹58,000 Cr', '1 week ago'], ['info', 'Added Tube Investments (new top holding)', '2 weeks ago'], ['up', 'Net inflows ₹620 Cr', '1 month ago']],
  quant: [['up', 'Momentum picked up sharply', '5 days ago'], ['down', 'Turnover rose to 118%', '2 weeks ago'], ['info', 'Rotated into Reliance (4.2%)', '3 weeks ago']],
};

// S21 — Alternatives (score → strength word)
export const ALTS: { tag: string; tone: string; name: string; amc: string; strengthScore: number; ret: string; exp: string }[] = [
  { tag: 'Higher Return', tone: '#8B5CF6', name: 'Tata Small Cap', amc: 'Tata MF', strengthScore: 88, ret: '30.1%', exp: '0.31%' },
  { tag: 'Lower Risk', tone: '#1E5EFF', name: 'SBI Small Cap', amc: 'SBI MF', strengthScore: 86, ret: '24.2%', exp: '0.69%' },
  { tag: 'Best Value', tone: '#00B386', name: 'HSBC Small Cap', amc: 'HSBC MF', strengthScore: 84, ret: '25.6%', exp: '0.70%' },
];

// S22 — AI insights
export const AI_INSIGHTS: string[] = [
  '**Bandhan** delivers similar returns to Nippon with noticeably lower volatility.',
  '**Quant** generates the highest upside but the deepest drawdowns — momentum-driven.',
  '**Nippon** has the strongest long-term SIP history and the deepest track record.',
  '**Bandhan** fits your portfolio best — its 9% overlap is the lowest of the three.',
  '**Quant** runs 118% turnover — higher hidden costs and tax churn than the others.',
  '**All three** beat the small-cap category over 1, 3 and 5 years — the category is in form.',
];

// S23 — FAQ
export const FAQ: [string, string][] = [
  ['Why is one fund read more strongly than another?', 'The DhanRadar educational read blends 12 factors — not just returns. Bandhan reads strongest on the balance of consistency, cost, downside protection, manager stability and diversification, even though Quant has higher raw returns.'],
  ['Why does risk differ between them?', 'Quant runs a high-momentum, concentrated book — bigger swings both ways. Bandhan holds 252 stocks with a quality tilt, so it has historically fallen less in corrections.'],
  ['Why are SIP returns different from lump-sum?', 'SIP averages your entry price over time, so funds that fell harder (like Quant in 2022) can show strong SIP XIRR because more units were bought cheaply during the dip.'],
  ['Why does the expense ratio matter?', "It's an annual drag on returns that compounds. A 0.22% difference looks tiny but works out to roughly ₹2.1 L on ₹10 L over 15 years."],
  ['How should a first-time small-cap investor read this?', 'Educationally, Bandhan has shown the smoothest ride and the most consistency, which historically makes a first-time small-cap investor less likely to panic-sell in a dip. This is context, not advice.'],
];

// S24 — Sticky read summary (band words / ranges, no numeric score)
export const STICKY = {
  name: 'Bandhan Small Cap',
  band: 'high' as ConfidenceBand,
  meta: 'High confidence · strongest on our factor blend',
  stats: [
    ['Very High', 'Risk'],
    ['16–22%', 'Illustrative range'],
    ['Long', 'Suggested horizon'],
    ['Stagger ×4', 'Lump-sum'],
  ] as [string, string][],
};

// SIP center — invested + value(₹'000s) + XIRR per fund, keyed amount_duration
export const SIPDATA: Record<string, [number, number[], number[]]> = {
  '1000_3': [36000, [46.2, 46.8, 48.1], [18.2, 19.0, 20.4]],
  '1000_5': [60000, [98.4, 99.6, 104.2], [19.8, 20.4, 22.1]],
  '1000_10': [120000, [312.0, 328.0, 358.0], [18.6, 19.4, 21.2]],
  '1000_15': [180000, [742.0, 788.0, 872.0], [17.9, 18.6, 20.1]],
  '5000_3': [180000, [231, 234, 240], [18.2, 19.0, 20.4]],
  '5000_5': [300000, [492, 498, 521], [19.8, 20.4, 22.1]],
  '5000_10': [600000, [1560, 1640, 1790], [18.6, 19.4, 21.2]],
  '5000_15': [900000, [3710, 3940, 4360], [17.9, 18.6, 20.1]],
  '10000_3': [360000, [462, 468, 481], [18.2, 19.0, 20.4]],
  '10000_5': [600000, [984, 996, 1042], [19.8, 20.4, 22.1]],
  '10000_10': [1200000, [3120, 3280, 3580], [18.6, 19.4, 21.2]],
  '10000_15': [1800000, [7420, 7880, 8720], [17.9, 18.6, 20.1]],
  '25000_3': [900000, [1155, 1170, 1203], [18.2, 19.0, 20.4]],
  '25000_5': [1500000, [2460, 2490, 2605], [19.8, 20.4, 22.1]],
  '25000_10': [3000000, [7800, 8200, 8950], [18.6, 19.4, 21.2]],
  '25000_15': [4500000, [18550, 19700, 21800], [17.9, 18.6, 20.1]],
};

export const SIP_AMOUNTS = [
  { key: '1000', label: '₹1k' },
  { key: '5000', label: '₹5k' },
  { key: '10000', label: '₹10k' },
  { key: '25000', label: '₹25k' },
];
export const SIP_DURATIONS = [
  { key: '3', label: '3Y' },
  { key: '5', label: '5Y' },
  { key: '10', label: '10Y' },
  { key: '15', label: '15Y' },
];

export function fmtCr(thousands: number): string {
  const rupees = thousands * 1000;
  if (rupees >= 10000000) return '₹' + (rupees / 10000000).toFixed(2) + ' Cr';
  if (rupees >= 100000) return '₹' + (rupees / 100000).toFixed(2) + ' L';
  return '₹' + Math.round(rupees).toLocaleString('en-IN');
}
