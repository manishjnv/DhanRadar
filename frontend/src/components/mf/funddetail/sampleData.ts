/**
 * Fund Detail V3 — illustrative ("preview") data for the full 22-section layout.
 *
 * IMPORTANT: this is SAMPLE data so every V3 section renders fully while the
 * real per-scheme feeds/endpoints are built (founder call 2026-06-24: build all
 * UI now, wire data later). Sections fed by this module are flagged "Preview".
 * The page overlays REAL values from useFundDetail() where they exist
 * (scheme_name, amc_name, sebi_category, verb_label, confidence_band, rank,
 * returns, plan/option type, amc_level_aum).
 *
 * COMPLIANCE — deliberately scrubbed to the non-negotiables:
 *   - NO DhanRadar score number / grade / percentile / weight (non-neg #2).
 *     Anything that is the proprietary composite is expressed as an educational
 *     LABEL + confidence BAND, or a strength WORD (Strong/Good/Moderate/Soft).
 *   - NO advisory verbs (buy/sell/hold/avoid/caution/switch) anywhere — neither
 *     as strings nor as object keys (non-neg #1, ci_guards).
 *   - Returns %, AUM ₹Cr, NAV, expense %, SIP XIRR %, drawdown %, Sharpe/Sortino/
 *     Beta/Std-dev/tracking-error, riskometer band, tax figures and category P/E
 *     are FACTUAL data types — DOM-allowed (not the proprietary score).
 */
import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';

/** Strength word used wherever V3 showed a 0–100 module/score number. */
export type Strength = 'strong' | 'good' | 'moderate' | 'soft';
/** Traffic-light health state. */
export type Light = 'g' | 'y' | 'r';
/** Factual band used for decorative bar fills (no numeric meaning). */
export type Band3 = 'high' | 'medium' | 'low';

// Decorative data-viz palette (logos / charts) — NOT brand CTA tokens.
export const C = {
  blue: '#1E5EFF', emerald: '#00B386', amber: '#F5A623', red: '#E5484D',
  orange: '#F97316', cyan: '#00C2FF', navy: '#0B1F3A', slate: '#64748B',
} as const;

// ───────────────────────────────────────────────────────────────────────────
// S1 HERO — header facts (overlaid by real data where present)
// ───────────────────────────────────────────────────────────────────────────
export const FUND = {
  pills: ['Direct · Growth', 'Index · Small Cap', 'Launched Mar 2021'] as string[],
  riskBand: 'Very High Risk',
  nav: '₹18.42',
  navChg: '+0.68%',
  navAsOf: '23 Jun',
  aum: '₹1,840 Cr',
  expense: '0.20%',
  minSip: '₹100',
  minLump: '₹100',
  /** hero badge word (educational, not advisory) */
  standing: 'Top Ranked',
  benchmark: 'Nifty Smallcap 250 TRI',
} as const;

// W2 (§10.1): HERO_FACTORS + STATUS_BADGES preview arrays retired — HeroSection
// and StatusRow now render the real `fund.factors`/`fund.signals` concepts
// (sectionsHero.tsx). Assessment-breakdown tiles whose source is still blocked
// (§18.1) — Cost Efficiency (TER coverage), Fund Flow (no source), Manager
// (signal not yet glued) — render as honest "no data yet" tiles.
export const NO_DATA_FACTOR_TILES: string[] = ['Cost Efficiency', 'Fund Flow', 'Manager'];

// ───────────────────────────────────────────────────────────────────────────
// S2 VERDICT — educational assessment (label + band, NOT "Strong Buy")
// ───────────────────────────────────────────────────────────────────────────
export const VERDICT = {
  tag: 'Our Educational Read',
  summary:
    'A low-cost, passive way to track India’s small-cap segment. Best understood as a long-horizon SIP exposure — not money you may need within five years.',
} as const;

// ───────────────────────────────────────────────────────────────────────────
// S3 SMART ENTRY TIMING — category valuation context (factual market data)
// ───────────────────────────────────────────────────────────────────────────
export const ENTRY = {
  /** meter marker position 0–100 (left=cheap, right=expensive) + band word */
  markerPct: 38,
  markerWord: 'Fair',
  ticks: ['Cheap', 'Fair', 'Neutral', 'Rich', 'Expensive'],
  pe: '28.4',
  peAvg: '26.1',
  context:
    'Category valuation is modestly above its 5-year average — fair, not a bargain.',
  meaning:
    'Valuations look reasonable but not cheap. A steady SIP averages your entry price; a lumpsum can be split into 3–4 monthly tranches to smooth timing.',
} as const;

// ───────────────────────────────────────────────────────────────────────────
// S4 PORTFOLIO FIT
// ───────────────────────────────────────────────────────────────────────────
export const FIT = {
  match: 'Strong Fit',
  matchSub: 'for a moderate-aggressive profile · 10-yr horizon',
  currentPct: 8,
  afterPct: 12,
  recLow: 10,
  recHigh: 15,
  stats: [
    { v: '+ Diversifying', l: 'Diversification impact', tone: 'emerald' as const },
    { v: '9%',  l: 'Overlap with your holdings', tone: 'ink' as const },
    { v: 'Strong', l: 'Portfolio benefit', tone: 'emerald' as const },
  ],
  meaning:
    'Adding this lifts your small-cap weight into the typically-recommended band and only ~9% overlaps your existing funds — so it adds diversification, not duplication.',
} as const;

// ───────────────────────────────────────────────────────────────────────────
// S5 MY INVESTMENT (personal preview)
// ───────────────────────────────────────────────────────────────────────────
export const MINE = {
  folio: 'Folio 1290845 / 22',
  currentValue: '₹2,84,620',
  pl: '+₹64,620 (29.4%) overall',
  plToday: '▲ ₹1,940 today',
  xirr: '21.8%',
  grid: [
    { l: 'Invested',        v: '₹2,20,000' },
    { l: 'Units held',      v: '15,452.8' },
    { l: 'Avg NAV',         v: '₹14.24' },
    { l: 'Current NAV',     v: '₹18.42' },
    { l: 'First invested',  v: '12 Apr 2022' },
    { l: 'Portfolio weight', v: '11.4%' },
    { l: 'Return contribution', v: '+3.8%' },
    { l: 'Post-tax exit value', v: '₹2,84,620' },
  ],
} as const;

// ───────────────────────────────────────────────────────────────────────────
// S6 MARKET MOOD ANALYSIS (regime WORD only, never a number)
// ───────────────────────────────────────────────────────────────────────────
export const MOOD = {
  word: 'Optimistic',
  fill: 0.64,
  sub: 'Current market mood',
  intro:
    'Here is how this fund has historically behaved across market phases at the current mood:',
  phases: [
    { name: 'Recovery markets', tag: 'best phase', val: '+38% avg', best: true,  tone: 'emerald' as const },
    { name: 'Bull markets',     tag: '',          val: '+29% avg', best: false, tone: 'emerald' as const },
    { name: 'Fear markets',     tag: '',          val: '−21% avg', best: false, tone: 'red' as const },
    { name: 'Euphoria',         tag: '',          val: '+11% avg', best: false, tone: 'amber' as const },
  ],
  stats: [
    { v: '73%',      l: 'Hist. positive outcome in this phase', tone: 'ink' as const },
    { v: 'Elevated', l: 'Volatility at current mood', tone: 'amber' as const },
    { v: 'SIP-friendly', l: 'Phase character', tone: 'emerald' as const },
  ],
  meaning:
    'Small-cap index exposure has historically done best entering recovery phases. The mood is Optimistic (not Euphoric), with a 73% historically-positive read — a context where steady SIPs have smoothed the elevated volatility.',
} as const;

// ───────────────────────────────────────────────────────────────────────────
// S7 FUND HEALTH DASHBOARD (traffic light)
// ───────────────────────────────────────────────────────────────────────────
export const HEALTH: { name: string; light: Light; note: string }[] = [
  { name: 'Performance',    light: 'g', note: 'Tracks benchmark & category over 1/3/5Y' },
  { name: 'Risk',           light: 'y', note: 'Very-high volatility — expected for small-cap' },
  { name: 'Cost',           light: 'g', note: '0.20% expense — lowest in category' },
  { name: 'Fund Flows',     light: 'g', note: 'Net inflows 11 of last 12 months' },
  { name: 'Momentum',       light: 'g', note: 'Relative strength improving' },
  { name: 'Consistency',    light: 'g', note: 'Top quartile 4 of last 5 years' },
  { name: 'Valuation',      light: 'y', note: 'Category P/E slightly above 5-yr average' },
  { name: 'Manager Quality', light: 'g', note: 'Zero turnover · best-in-class tracking error' },
  { name: 'Portfolio Quality', light: 'g', note: 'Broad 250-stock diversification' },
];

// ───────────────────────────────────────────────────────────────────────────
// S8 WHAT CHANGED THIS MONTH (timeline) — score numbers scrubbed to words
// ───────────────────────────────────────────────────────────────────────────
export const CHANGES: { tone: 'up' | 'down' | 'info'; html: string; time: string }[] = [
  { tone: 'up',   html: 'Category <b>rank improved #5 → #3</b> on stronger 1-yr tracking.', time: '4 days ago' },
  { tone: 'up',   html: '<b>AUM grew ₹230 Cr</b> to ₹1,840 Cr — steady passive inflows.', time: '1 week ago' },
  { tone: 'info', html: '<b>Healthcare weight rose +1.4%</b> as the index rebalanced.', time: '2 weeks ago' },
  { tone: 'up',   html: '<b>Momentum strengthened</b> over the trailing six months.', time: '3 weeks ago' },
  { tone: 'down', html: 'Tracking error ticked up <b>0.18% → 0.21%</b> — still category-best.', time: '3 weeks ago' },
];

// ───────────────────────────────────────────────────────────────────────────
// S9 INVESTMENT SNAPSHOT (KPI grid, all factual)
// ───────────────────────────────────────────────────────────────────────────
export const SNAPSHOT: { l: string; v: string; p?: string; tone?: 'emerald'; tip: string }[] = [
  { l: 'NAV', v: '₹18.42', p: '▲ 0.68% today', tone: 'emerald', tip: 'Per-unit price of the fund.' },
  { l: 'Expense Ratio', v: '0.20%', p: 'Lowest in category', tone: 'emerald', tip: 'Annual fee as % of investment.' },
  { l: 'Exit Load', v: '1% < 1yr', p: 'Nil after 1 year', tip: 'Fee for redeeming within 1 year.' },
  { l: 'Benchmark', v: 'Nifty Smallcap 250', p: 'TRI', tip: 'The index this fund tracks.' },
  { l: 'Fund Size (AUM)', v: '₹1,840 Cr', p: '+₹230 Cr MoM', tone: 'emerald', tip: 'Total assets managed.' },
  { l: 'Tracking Error', v: '0.21%', p: 'Best-in-class', tone: 'emerald', tip: 'How tightly it follows the index.' },
  { l: 'Fund Age', v: '5.3 yrs', p: 'Since Mar 2021', tip: 'Time since launch.' },
  { l: 'Manager Tenure', v: '5.3 yrs', p: 'No changes', tone: 'emerald', tip: 'How long managers have run it.' },
  { l: 'Portfolio Turnover', v: '22%', p: 'Low (passive)', tone: 'emerald', tip: 'How often holdings change.' },
  { l: 'Min SIP', v: '₹100', p: 'Very accessible', tone: 'emerald', tip: 'Smallest monthly SIP.' },
  { l: 'Min Lumpsum', v: '₹100', tip: 'Smallest one-time investment.' },
  { l: 'Stamp Duty', v: '0.005%', p: 'On purchase', tip: 'Govt levy on buying units.' },
  { l: 'Lock-in', v: 'None', p: 'Open-ended', tip: 'No mandatory holding period.' },
  { l: 'Category Rank', v: '#3 / 18', p: '▲ from #5', tone: 'emerald', tip: 'Rank within small-cap index funds.' },
];

// ───────────────────────────────────────────────────────────────────────────
// S10 PERFORMANCE CENTER
// ───────────────────────────────────────────────────────────────────────────
export const RETURNS: { p: string; v: number | null }[] = [
  { p: '1M', v: 3.8 }, { p: '3M', v: 10.4 }, { p: '6M', v: 16.9 }, { p: '1Y', v: 24.8 },
  { p: '3Y', v: 27.9 }, { p: '5Y', v: 26.4 }, { p: '10Y', v: null }, { p: 'Launch', v: 22.1 },
];
export const RETURN_TABLE: { row: string; me: boolean; cells: string[] }[] = [
  { row: 'This fund',    me: true,  cells: ['24.8%', '27.9%', '26.4%', '22.1%'] },
  { row: 'Benchmark',    me: false, cells: ['24.2%', '27.4%', '25.9%', '21.6%'] },
  { row: 'Category avg', me: false, cells: ['22.1%', '25.2%', '23.8%', '19.4%'] },
];
export const RETURN_TABLE_HEAD = ['Period', '1Y', '3Y', '5Y', 'Launch'];
export const GROWTH = { invested: '₹10,000', value: '₹32,300', gain: '+223%', ranges: ['1Y', '3Y', '5Y', 'MAX'] };
export const SIP = {
  amounts: [
    { key: '10000', label: '₹10,000/mo', sub: '₹10,000/mo · 5 years · invested ₹6,00,000', val: '₹9,68,400', gain: '+₹3,68,400', xirr: '19.4% XIRR' },
    { key: '5000',  label: '₹5,000/mo',  sub: '₹5,000/mo · 5 years · invested ₹3,00,000',  val: '₹4,84,200', gain: '+₹1,84,200', xirr: '19.4% XIRR' },
    { key: '20000', label: '₹20,000/mo', sub: '₹20,000/mo · 5 years · invested ₹12,00,000', val: '₹19,36,800', gain: '+₹7,36,800', xirr: '19.4% XIRR' },
  ],
  tiles: [{ p: '3Y SIP', v: '19.4%' }, { p: '5Y SIP', v: '21.0%' }, { p: 'Since launch', v: '20.2%' }],
  meaning:
    'A ₹10,000 monthly SIP over 5 years turned ₹6.0L invested into ₹9.68L. SIP also lowered the effective entry price through the 2022 correction.',
};
export const ROLLING = {
  tiles: [{ p: '1Y rolling', v: '23.4%' }, { p: '3Y rolling', v: '26.8%' }, { p: '5Y rolling', v: '25.1%' }],
  head: ['Rolling avg', 'Fund', 'Bench', 'Category'],
  rows: [
    { row: '1Y', cells: ['23.4%', '22.9%', '20.8%'] },
    { row: '3Y', cells: ['26.8%', '26.2%', '24.1%'] },
    { row: '5Y', cells: ['25.1%', '24.6%', '22.4%'] },
  ],
  meaning:
    'Rolling returns test every holding period, not just lucky start dates. This fund tracked above its category in ~81% of rolling 3-year windows — strong consistency for an index fund.',
};
export const RANK = {
  cells: [
    { v: '#3', l: 'Current' }, { v: '#2', l: 'Best ever' },
    { v: '#4', l: 'Avg (3yr)' }, { v: 'Q1', l: 'Quartile', tone: 'emerald' as const },
  ],
  /** rank series (lower = better) for the trend chart */
  series: [6, 5, 5, 4, 4, 3, 4, 3, 3, 2, 3, 3],
  bands: [
    { name: 'Great',   on: true,  color: C.emerald },
    { name: 'Good',    on: false, color: '#84CC16' },
    { name: 'Average', on: false, color: C.amber },
    { name: 'Weak',    on: false, color: C.red },
  ],
  meaning:
    'Rank has held in the top 3–4 of 18 funds for two years and currently sits in the “Great” band — a dependable performer, not a one-year wonder.',
};
export const DRAWDOWN = {
  cells: [
    { v: '−26.8%', l: 'Worst fall (2022)', tone: 'red' as const },
    { v: '9 mo', l: 'Recovery time', tone: 'ink' as const },
    { v: '−14.2%', l: 'Current from peak', tone: 'red' as const },
  ],
  meaning:
    'Small-cap funds fall hard. The worst drop was −26.8%, recovered in 9 months. Only invest money you will not need during such dips.',
};
export const CONSISTENCY = {
  intro: 'Quartile finish each calendar year (Q1 = top 25% of category):',
  strip: [
    { y: '2021', q: 'Q1', tone: 'emerald' as const }, { y: '2022', q: 'Q2', tone: 'amber' as const },
    { y: '2023', q: 'Q1', tone: 'emerald' as const }, { y: '2024', q: 'Q1', tone: 'emerald' as const },
    { y: '2025', q: 'Q1', tone: 'emerald' as const },
  ],
  tiles: [
    { v: 'Q1', l: 'Last 3 yrs', tone: 'emerald' as const },
    { v: 'Strong', l: 'Consistency', tone: 'emerald' as const },
    { v: 'Top decile', l: 'Standing', tone: 'emerald' as const },
  ],
  meaning:
    'Finished top-quartile in 4 of the last 5 years. For a passive fund, that consistency is exactly what you want — low cost, reliably tracking a strong index.',
};

// W2 (§10.1): SCORE_MODULES preview array retired — ScoreBreakdownSection now
// renders real tiles from `fund.factors` + the NO_DATA_FACTOR_TILES list above.

// ───────────────────────────────────────────────────────────────────────────
// S12 RISK CENTER
// ───────────────────────────────────────────────────────────────────────────
export const RISK_SIMPLE: { v: string; l: string; tone: 'amber' | 'red' | 'emerald' | 'ink' }[] = [
  { v: 'Very High', l: 'Risk level', tone: 'amber' },
  { v: '−26.8%', l: 'Worst fall', tone: 'red' },
  { v: '9 mo', l: 'Recovery time', tone: 'ink' },
  { v: '+34%', l: 'Upside (good yr)', tone: 'emerald' },
  { v: '−24%', l: 'Downside (bad yr)', tone: 'red' },
  { v: '19.1%', l: 'Volatility (std dev)', tone: 'ink' },
];
/** Advanced risk analytics — factual stats + a decorative band fill (no %). */
export const RISK_ADV: { name: string; value: string; band: Band3; tip: string }[] = [
  { name: 'Sharpe Ratio',      value: '1.18',     band: 'high',   tip: 'Risk-adjusted return' },
  { name: 'Sortino Ratio',     value: '1.64',     band: 'high',   tip: 'Downside-adjusted return' },
  { name: 'Alpha',             value: '+0.6%',    band: 'medium', tip: 'Excess vs benchmark' },
  { name: 'Beta',              value: '0.99',     band: 'high',   tip: 'Moves with the index' },
  { name: 'Tracking Error',    value: '0.21%',    band: 'high',   tip: 'Index-tracking tightness' },
  { name: 'Std Deviation',     value: '19.1%',    band: 'medium', tip: 'Volatility' },
  { name: 'Max Drawdown',      value: '−26.8%', band: 'medium', tip: 'Worst peak-to-trough' },
  { name: 'Upside Capture',    value: '99%',      band: 'high',   tip: 'Of index gains captured' },
  { name: 'Downside Capture',  value: '98%',      band: 'medium', tip: 'Of index falls absorbed' },
  { name: 'Portfolio Turnover', value: '22%',     band: 'high',   tip: 'Trading frequency' },
];
export const RISK_MEANING =
  'Expect a roller-coaster: a strong year could gain ~34%, a weak one could lose ~24%. The Sharpe of 1.18 indicates the volatility has, over time, been reasonably compensated.';

// ───────────────────────────────────────────────────────────────────────────
// S13 HOLDINGS
// ───────────────────────────────────────────────────────────────────────────
export const HOLD_STOCKS: { name: string; ticker: string; sector: string; wt: number; chg: number }[] = [
  { name: 'Suzlon Energy',         ticker: 'SUZ', sector: 'Industrials', wt: 1.9, chg: 0.2 },
  { name: 'BSE Ltd',               ticker: 'BSE', sector: 'Financials',  wt: 1.7, chg: 0.4 },
  { name: 'Multi Commodity Exch',  ticker: 'MCX', sector: 'Financials',  wt: 1.5, chg: -0.1 },
  { name: 'Cochin Shipyard',       ticker: 'COC', sector: 'Industrials', wt: 1.4, chg: 0.3 },
  { name: 'Glenmark Pharma',       ticker: 'GLN', sector: 'Healthcare',  wt: 1.3, chg: 0.1 },
  { name: 'Hindustan Copper',      ticker: 'HCP', sector: 'Materials',   wt: 1.2, chg: -0.2 },
  { name: 'Authum Invest',         ticker: 'AUT', sector: 'Financials',  wt: 1.1, chg: 0.0 },
  { name: 'Cyient',                ticker: 'CYI', sector: 'Technology',  wt: 1.1, chg: 0.2 },
];
export const HOLD_SECTORS: { name: string; wt: number; color: string }[] = [
  { name: 'Financial Services', wt: 24.6, color: C.blue },
  { name: 'Industrials',        wt: 18.9, color: C.cyan },
  { name: 'Healthcare',         wt: 12.4, color: C.emerald },
  { name: 'Materials',          wt: 11.8, color: C.amber },
  { name: 'Consumer',           wt: 10.2, color: C.orange },
  { name: 'Technology',         wt: 8.1,  color: C.navy },
  { name: 'Others',             wt: 14.0, color: C.slate },
];
export const HOLD_CAP: { name: string; wt: number; color: string }[] = [
  { name: 'Small Cap', wt: 94, color: C.blue }, { name: 'Mid Cap', wt: 3, color: C.cyan }, { name: 'Cash', wt: 3, color: C.slate },
];
export const HOLD_ASSET: { name: string; wt: number; color: string }[] = [
  { name: 'Equity', wt: 97, color: C.emerald }, { name: 'Cash & equiv.', wt: 3, color: C.slate },
];
export const HOLD_CAP_NOTE = 'A true small-cap fund — 94% in small-caps by design, tracking the Nifty Smallcap 250.';
export const STYLE_BOX = { hotIndex: 7, caption: 'Small-cap · Blend' }; // bottom-middle of 3×3

// ───────────────────────────────────────────────────────────────────────────
// S14 FUND FLOW INTELLIGENCE
// ───────────────────────────────────────────────────────────────────────────
export const FLOW = {
  ranges: ['3M', '6M', '1Y'],
  cells: [
    { v: '₹2,840 Cr', l: 'Inflows (1Y)', tone: 'emerald' as const },
    { v: '₹1,210 Cr', l: 'Outflows (1Y)', tone: 'red' as const },
    { v: '+₹1,630 Cr', l: 'Net flows (1Y)', tone: 'emerald' as const },
  ],
  /** monthly net flow ₹Cr (one negative month) */
  series: [120, 168, 96, -40, 180, 142, 88, 210, 150, 176, 132, 198],
  badge: 'Net inflows positive',
  badgeNote: 'Net inflows positive in 11 of the last 12 months.',
  meaning:
    'Consistent net inflows signal growing investor trust and keep the fund’s tracking tight. No sign of a redemption rush that could force the index fund to sell.',
};

// ───────────────────────────────────────────────────────────────────────────
// S15 FUND MANAGER — manager "score" replaced with strength word
// ───────────────────────────────────────────────────────────────────────────
export const MANAGER = {
  initials: 'NA',
  name: 'Nirman Morakhia & Arun Agarwal',
  sub: 'Co-managing since launch · passive / index desk · 8 funds',
  stats: [
    { v: '5.3y',   l: 'Tenure' },
    { v: '0.21%',  l: 'Avg tracking err', tone: 'emerald' as const },
    { v: 'Strong', l: 'Manager quality', tone: 'emerald' as const },
    { v: '0',      l: 'Mgr changes' },
  ],
  meaning:
    'For an index fund, “manager skill” = keeping tracking error tiny. This desk has held it at a category-best ~0.21% with zero turnover since launch.',
};

// ───────────────────────────────────────────────────────────────────────────
// S16 AMC QUALITY — ratings/scores replaced with descriptors/bands
// ───────────────────────────────────────────────────────────────────────────
export const AMC = {
  initial: 'H',
  est: 'Est. 2000 · one of India’s largest fund houses',
  stats: [
    { v: 'Well-regarded', l: 'AMC standing' },
    { v: '₹6.8L Cr',      l: 'Total AUM' },
    { v: '26 yrs',        l: 'In business' },
    { v: 'Strong',        l: 'Trust signal', tone: 'emerald' as const },
  ],
  bars: [
    { l: 'Investor confidence',      band: 'high' as Band3 },
    { l: 'Operational stability',    band: 'high' as Band3 },
    { l: 'Fund house strength',      band: 'high' as Band3 },
    { l: 'Risk management',          band: 'high' as Band3 },
    { l: 'Compliance track record',  band: 'high' as Band3 },
  ],
  meaning:
    'You are with one of India’s most established, financially stable fund houses — strong operational systems mean fewer surprises and reliable execution.',
};

// ───────────────────────────────────────────────────────────────────────────
// S17 TAX CENTER (factual calculator defaults)
// ───────────────────────────────────────────────────────────────────────────
export const TAX = {
  defaultAmount: 284620,
  costBasis: 220000,
  ltcgExempt: 125000,
  ltcgRate: 0.125,
  stcgRate: 0.20,
  meaning:
    'A ₹64,620 long-term gain sits within the ₹1.25L/yr LTCG exemption — redeeming now would attract zero tax. A holding under 1 year would instead be taxed at 20% STCG. Estimate only.',
};

// ───────────────────────────────────────────────────────────────────────────
// S18 TRANSACTION HISTORY (kind = sip | lumpsum; no advisory key names)
// ───────────────────────────────────────────────────────────────────────────
export const TXNS: { date: string; kind: 'sip' | 'lumpsum'; amount: string; nav: string; units: string }[] = [
  { date: '23 May 2026', kind: 'sip',     amount: '₹10,000', nav: '₹18.10', units: '552.5' },
  { date: '23 Apr 2026', kind: 'sip',     amount: '₹10,000', nav: '₹17.42', units: '574.0' },
  { date: '23 Mar 2026', kind: 'sip',     amount: '₹10,000', nav: '₹16.88', units: '592.4' },
  { date: '18 Mar 2026', kind: 'lumpsum', amount: '₹50,000', nav: '₹16.75', units: '2985.1' },
  { date: '23 Feb 2026', kind: 'sip',     amount: '₹10,000', nav: '₹16.20', units: '617.3' },
  { date: '23 Jan 2026', kind: 'sip',     amount: '₹10,000', nav: '₹15.94', units: '627.4' },
];
export const TXN_TOTAL = 22;

// ───────────────────────────────────────────────────────────────────────────
// S19 ALTERNATIVES (label/band instead of score number)
// ───────────────────────────────────────────────────────────────────────────
export const ALTERNATIVES: {
  tag: string; tagTone: 'emerald' | 'royal' | 'amber'; name: string; amc: string;
  label: Label; band: ConfidenceBand; ret: string; expense: string; risk: string;
}[] = [
  { tag: 'Higher historical return', tagTone: 'emerald', name: 'Sample Small Cap Active A', amc: 'Sample AMC Two',  label: 'in_form',  band: 'high',   ret: '29.1%', expense: '0.68%', risk: 'Very High' },
  { tag: 'Lower risk profile',       tagTone: 'royal',   name: 'Sample Balanced Advantage A', amc: 'Sample AMC Eight', label: 'on_track', band: 'high',   ret: '16.2%', expense: '0.74%', risk: 'Moderate' },
  { tag: 'Lower cost',               tagTone: 'amber',   name: 'Sample Smallcap 250 Index B', amc: 'Sample AMC Ten',  label: 'on_track', band: 'high',   ret: '24.4%', expense: '0.18%', risk: 'Very High' },
];

// ───────────────────────────────────────────────────────────────────────────
// S20 SIMILAR FUNDS (carousel)
// ───────────────────────────────────────────────────────────────────────────
export const SIMILAR: { name: string; amc: string; label: Label; band: ConfidenceBand; ret: string; risk: string }[] = [
  { name: 'Sample Smallcap 250 Index B', amc: 'Sample AMC Ten',      label: 'on_track', band: 'high',   ret: '24.4%', risk: 'Very High' },
  { name: 'Sample Smallcap 250 Index C', amc: 'Sample AMC Eleven',   label: 'on_track', band: 'medium', ret: '23.9%', risk: 'Very High' },
  { name: 'Sample Smallcap Index D',     amc: 'Sample AMC Two',      label: 'on_track', band: 'high',   ret: '24.1%', risk: 'Very High' },
  { name: 'Sample Smallcap Active E',    amc: 'Sample AMC Twelve',   label: 'off_track', band: 'low',   ret: '25.6%', risk: 'Very High' },
  { name: 'Sample Smallcap Index F',     amc: 'Sample AMC Four',     label: 'in_form',  band: 'high',   ret: '24.6%', risk: 'Very High' },
];

// ───────────────────────────────────────────────────────────────────────────
// S21 FAQ
// ───────────────────────────────────────────────────────────────────────────
export const FAQ: { q: string; a: string; open?: boolean }[] = [
  { q: 'What is NAV?', open: true, a: 'NAV (Net Asset Value) is the per-unit price of the fund — the total value of all its holdings divided by the number of units. You transact at the day’s NAV. This fund’s NAV is ₹18.42.' },
  { q: 'What is the Expense Ratio?', a: 'The annual fee the fund charges, as a % of your investment. At 0.20%, you pay ₹20/year per ₹10,000 invested — among the lowest in the category because this is a passive index fund.' },
  { q: 'What is Exit Load?', a: 'A fee for redeeming early. This fund charges 1% within 1 year and nothing after — so it rewards staying invested for the long term.' },
  { q: 'How is this taxed?', a: 'As an equity fund: gains within 1 year are STCG (20%); gains after 1 year are LTCG (12.5%), with the first ₹1.25L of LTCG each year tax-free. Use the Tax Center above to estimate yours.' },
  { q: 'When is SIP vs lumpsum usually discussed?', a: 'For small-cap index funds, a disciplined monthly SIP over 7+ years is commonly discussed because it averages your entry price through the inevitable ups and downs. See Smart Entry Timing above for the current educational read.' },
];

// W2 (§10.1): STICKY preview object retired — StickyBar's "Top reason" is now
// the real first contributing signal (sectionsHero.tsx); its stats row already
// came from getStickyCategoryStats(), not this object.
