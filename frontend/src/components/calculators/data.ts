/**
 * Calculator Hub V1 — static preview data.
 *
 * Ported from the approved CalculatorHubV1 desktop + mobile mockups
 * (docs/ui-system/html/CalculatorHubV1*.html). This is a PURE-UI build: every
 * value here is illustrative preview seed data so the page renders fully while
 * the real calculator engines / search / filtering are wired in a later session
 * (founder call: build all UI now, wire logic later). NOTHING here is a
 * DhanRadar-computed fund score — these are plain calculator-style illustrations.
 *
 * The mockup's 10-colour icon palette is reconciled DOWN to the six brand
 * accents (navy/royal/emerald/cyan/amber/red) per the brand-guide rule; there is
 * no violet/orange/pink/teal token in the design system.
 */

// ── Brand accent palette (the only colours used for icon tints) ──────────────
export type Accent = 'royal' | 'emerald' | 'amber' | 'cyan' | 'red' | 'navy';

export const ACCENT_HEX: Record<Accent, string> = {
  royal: '#1E5EFF',
  emerald: '#00B386',
  amber: '#F5A623',
  cyan: '#00C2FF',
  red: '#E5484D',
  navy: '#0B1F3A',
};

/** Inline tint for an icon tile: 10%-alpha background + solid foreground. */
export function accentTile(a: Accent): { background: string; color: string } {
  const hex = ACCENT_HEX[a];
  return { background: `${hex}1A`, color: hex };
}

export type FeatureTag = 'Most Popular' | 'Popular' | 'Recommended' | 'New' | 'AI Recommended';

export const TAG_ACCENT: Record<FeatureTag, Accent> = {
  'Most Popular': 'royal',
  Popular: 'emerald',
  Recommended: 'royal',
  New: 'amber',
  'AI Recommended': 'cyan',
};

// ── Hero ─────────────────────────────────────────────────────────────────────
export const HERO = {
  title: 'Financial Calculators',
  subtitle:
    'Plan investments, estimate returns, calculate taxes, and achieve your financial goals — all in one place, understandable in under a minute.',
  searchPlaceholder: 'Search 50+ calculators — SIP, tax, retirement, loan…',
  searchPlaceholderMobile: 'Search SIP, tax, retirement…',
  stats: [
    { label: 'Total Calculators', value: '52' },
    { label: 'Categories', value: '8' },
    { label: 'Most Popular', value: 'SIP Calculator', small: true },
    { label: 'Featured', value: 'FIRE Planner', small: true },
  ] as { label: string; value: string; small?: boolean }[],
};

// Hero quick-category chips
export const HERO_CATS: { emoji: string; label: string }[] = [
  { emoji: '📈', label: 'Mutual Fund' },
  { emoji: '🧾', label: 'Tax' },
  { emoji: '🏖', label: 'Retirement' },
  { emoji: '🎯', label: 'Goal Planning' },
  { emoji: '🏠', label: 'Loan' },
  { emoji: '💰', label: 'General Finance' },
];

// ── S1 Featured calculators ──────────────────────────────────────────────────
export type Featured = {
  emoji: string;
  name: string;
  desc: string;
  tag: FeatureTag;
  accent: Accent;
};

export const FEATURED: Featured[] = [
  { emoji: '📈', name: 'SIP Calculator', desc: 'Grow wealth with monthly investing', tag: 'Most Popular', accent: 'royal' },
  { emoji: '📈', name: 'SIP + Lumpsum', desc: 'Upfront amount + monthly SIP', tag: 'New', accent: 'royal' },
  { emoji: '💵', name: 'Lumpsum Calculator', desc: 'One-time investment growth', tag: 'Popular', accent: 'emerald' },
  { emoji: '🏖', name: 'Retirement Planner', desc: 'Plan your retirement corpus', tag: 'Recommended', accent: 'royal' },
  { emoji: '🔥', name: 'FIRE Calculator', desc: 'Retire early & independent', tag: 'New', accent: 'amber' },
  { emoji: '🎯', name: 'Goal SIP Calculator', desc: 'SIP needed for any goal', tag: 'AI Recommended', accent: 'cyan' },
  { emoji: '💸', name: 'SWP Calculator', desc: 'Regular income from investments', tag: 'Popular', accent: 'emerald' },
  { emoji: '🧾', name: 'Capital Gains Tax', desc: 'LTCG & STCG on mutual funds', tag: 'Recommended', accent: 'red' },
  { emoji: '🎓', name: 'Education Planner', desc: "Save for your child's future", tag: 'Popular', accent: 'red' },
  { emoji: '🏠', name: 'Home Down Payment', desc: 'Plan your house purchase', tag: 'Recommended', accent: 'amber' },
  { emoji: '📊', name: 'Step-up SIP', desc: 'Increase SIP every year', tag: 'New', accent: 'royal' },
];

// ── S2 Categories ────────────────────────────────────────────────────────────
export type Category = { emoji: string; name: string; count: string; accent: Accent };

export const CATEGORIES: Category[] = [
  { emoji: '📈', name: 'Mutual Fund', count: '12 calculators', accent: 'royal' },
  { emoji: '🧾', name: 'Tax', count: '9 calculators', accent: 'amber' },
  { emoji: '🎯', name: 'Goal Planning', count: '8 calculators', accent: 'royal' },
  { emoji: '🏖', name: 'Retirement', count: '5 calculators', accent: 'emerald' },
  { emoji: '🏠', name: 'Loan', count: '4 calculators', accent: 'cyan' },
  { emoji: '🛡', name: 'Insurance', count: '3 calculators', accent: 'emerald' },
  { emoji: '⚖', name: 'Investment Compare', count: '4 calculators', accent: 'red' },
  { emoji: '💰', name: 'General Finance', count: '9 calculators', accent: 'amber' },
];

// ── S3 All calculators + filter chips ────────────────────────────────────────
export const FILTER_CHIPS = [
  'All', 'SIP', 'Lumpsum', 'Tax', 'Retirement', 'Inflation', 'Goal', 'Loan', 'FIRE', 'Beginner', 'Advanced',
];

export type CalcMini = { emoji: string; name: string; category: string; accent: Accent };

export const ALL_CALCS: CalcMini[] = [
  { emoji: '📈', name: 'SIP Calculator', category: 'Mutual Fund', accent: 'royal' },
  { emoji: '💵', name: 'Lumpsum', category: 'Mutual Fund', accent: 'emerald' },
  { emoji: '📈', name: 'SIP + Lumpsum', category: 'Mutual Fund', accent: 'royal' },
  { emoji: '💸', name: 'SWP', category: 'Mutual Fund', accent: 'emerald' },
  { emoji: '🔄', name: 'STP', category: 'Mutual Fund', accent: 'cyan' },
  { emoji: '⏰', name: 'SIP Delay', category: 'Mutual Fund', accent: 'amber' },
  { emoji: '📊', name: 'SIP Top-up', category: 'Mutual Fund', accent: 'royal' },
  { emoji: '🎯', name: 'Goal SIP', category: 'Mutual Fund', accent: 'royal' },
  { emoji: '💹', name: 'Future Value', category: 'Mutual Fund', accent: 'emerald' },
  { emoji: '📉', name: 'Inflation-Adjusted Return', category: 'Mutual Fund', accent: 'red' },
  { emoji: '📈', name: 'CAGR', category: 'Mutual Fund', accent: 'royal' },
  { emoji: '🧮', name: 'XIRR', category: 'Mutual Fund', accent: 'royal' },
  { emoji: '💰', name: 'Fund Return', category: 'Mutual Fund', accent: 'emerald' },
  { emoji: '🧾', name: 'Capital Gains Tax', category: 'Tax', accent: 'amber' },
  { emoji: '📋', name: 'STCG', category: 'Tax', accent: 'red' },
  { emoji: '📑', name: 'LTCG', category: 'Tax', accent: 'amber' },
  { emoji: '✅', name: 'Post-Tax Return', category: 'Tax', accent: 'emerald' },
  { emoji: '💸', name: 'Exit Load', category: 'Tax', accent: 'amber' },
  { emoji: '🌾', name: 'Tax Harvesting', category: 'Tax', accent: 'emerald' },
  { emoji: '💵', name: 'Dividend Tax', category: 'Tax', accent: 'royal' },
  { emoji: '📊', name: 'Portfolio Tax', category: 'Tax', accent: 'royal' },
  { emoji: '📤', name: 'Redemption Planner', category: 'Tax', accent: 'cyan' },
  { emoji: '🎓', name: 'Education Planner', category: 'Goal', accent: 'red' },
  { emoji: '💍', name: 'Marriage Planner', category: 'Goal', accent: 'red' },
  { emoji: '🏠', name: 'House Purchase', category: 'Goal', accent: 'amber' },
  { emoji: '🚗', name: 'Car Purchase', category: 'Goal', accent: 'cyan' },
  { emoji: '✈', name: 'Vacation Planner', category: 'Goal', accent: 'emerald' },
  { emoji: '🆘', name: 'Emergency Fund', category: 'Goal', accent: 'red' },
  { emoji: '👶', name: 'Child Education', category: 'Goal', accent: 'royal' },
  { emoji: '🎯', name: 'Goal Planner', category: 'Goal', accent: 'royal' },
  { emoji: '🏖', name: 'Retirement Planner', category: 'Retirement', accent: 'emerald' },
  { emoji: '🔥', name: 'FIRE Calculator', category: 'Retirement', accent: 'amber' },
  { emoji: '💵', name: 'Passive Income', category: 'Retirement', accent: 'emerald' },
  { emoji: '🏦', name: 'Corpus Calculator', category: 'Retirement', accent: 'royal' },
  { emoji: '🏠', name: 'Home Loan EMI', category: 'Loan', accent: 'cyan' },
  { emoji: '💳', name: 'Prepayment', category: 'Loan', accent: 'royal' },
  { emoji: '⚖', name: 'Loan Comparison', category: 'Loan', accent: 'royal' },
  { emoji: '💰', name: 'Interest Savings', category: 'Loan', accent: 'emerald' },
  { emoji: '🏦', name: 'FD Calculator', category: 'General', accent: 'amber' },
  { emoji: '💰', name: 'RD Calculator', category: 'General', accent: 'emerald' },
  { emoji: '🛡', name: 'PPF', category: 'General', accent: 'royal' },
  { emoji: '👔', name: 'EPF', category: 'General', accent: 'emerald' },
  { emoji: '📊', name: 'NPS', category: 'General', accent: 'royal' },
  { emoji: '🎯', name: 'Savings Goal', category: 'General', accent: 'amber' },
  { emoji: '💎', name: 'Net Worth', category: 'General', accent: 'navy' },
  { emoji: '📐', name: 'Rule of 72 / 114', category: 'General', accent: 'cyan' },
  { emoji: '🛡', name: 'Term Cover', category: 'Insurance', accent: 'emerald' },
  { emoji: '🏥', name: 'Health Cover', category: 'Insurance', accent: 'cyan' },
  { emoji: '❤️', name: 'Human Life Value', category: 'Insurance', accent: 'red' },
  { emoji: '⚖', name: 'SIP vs Lumpsum', category: 'Investment Compare', accent: 'royal' },
  { emoji: '⚖', name: 'FD vs Debt Fund', category: 'Investment Compare', accent: 'emerald' },
  { emoji: '⚖', name: 'Old vs New Regime', category: 'Investment Compare', accent: 'amber' },
  { emoji: '⚖', name: 'Rent vs Buy', category: 'Investment Compare', accent: 'cyan' },
  { emoji: '⚖', name: 'Direct vs Regular', category: 'Investment Compare', accent: 'red' },
];

// Difficulty tag backing the "Beginner" / "Advanced" filter chips. Beginner = the
// everyday, single-concept calculators a first-time investor reaches for; every
// other calculator (tax, returns-math, withdrawal/transfer, insurance, NPS,
// comparisons, multi-phase planners) counts as Advanced. Adjust freely — it only
// drives the two chips, nothing compliance-bearing.
export const BEGINNER_CALCS = new Set<string>([
  'SIP Calculator', 'Lumpsum', 'SIP + Lumpsum', 'SIP Top-up', 'Goal SIP', 'Future Value',
  'Education Planner', 'Marriage Planner', 'House Purchase', 'Car Purchase', 'Vacation Planner',
  'Emergency Fund', 'Child Education', 'Goal Planner', 'Home Loan EMI',
  'FD Calculator', 'RD Calculator', 'PPF', 'EPF', 'Savings Goal', 'Net Worth', 'Rule of 72 / 114',
]);

// ── S4 Learn the basics ──────────────────────────────────────────────────────
export const LEARN: { emoji: string; q: string; a: string }[] = [
  { emoji: '📈', q: 'What is CAGR?', a: 'The average yearly growth rate of your investment, smoothed over time.' },
  { emoji: '🧮', q: 'What is XIRR?', a: 'Your true return when you invest at different times, like monthly SIPs.' },
  { emoji: '💸', q: 'What is SWP?', a: 'A way to withdraw a fixed amount regularly from your investments.' },
  { emoji: '🔄', q: 'What is STP?', a: 'Moving money gradually from one fund to another, in steps.' },
  { emoji: '📉', q: 'What is Inflation?', a: 'The slow rise in prices that reduces what your money can buy.' },
];

// ── S5 FAQ ───────────────────────────────────────────────────────────────────
export const FAQ: { q: string; a: string }[] = [
  {
    q: 'Are these calculators accurate?',
    a: 'They give realistic estimates based on the numbers you enter, assuming a steady annual return. Real markets go up and down, so treat results as a guide, not a guarantee.',
  },
  {
    q: 'What return should I assume?',
    a: 'For equity mutual funds, 11–13% is a reasonable long-term assumption. For debt, 6–8%. The calculator lets you adjust this to be conservative or optimistic.',
  },
  {
    q: 'What is a step-up SIP?',
    a: 'Increasing your SIP amount every year (say by 10%) as your income grows. It dramatically boosts your final corpus — try the toggle to see the difference.',
  },
  {
    q: 'Do calculations account for tax?',
    a: 'The investment calculators show pre-tax growth. Use the dedicated Capital Gains and Post-Tax calculators to see your actual take-home returns.',
  },
  {
    q: 'Can I save or export my results?',
    a: 'Yes — every calculator has Export (PDF/image) and Share buttons so you can save a plan or send it to your advisor.',
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// SIP DETAIL — static default-state seed data (25,000 / 12% / 15 yrs, no step-up)
// Numbers precomputed from the mockup's SIP formula so the inert shell stays
// internally consistent. The sliders below are static placeholders; nothing
// recalculates (calculator engine is a later session).
// ─────────────────────────────────────────────────────────────────────────────

// Full 15-point yearly series — seed for the static growth chart & table.
export const SIP_SERIES: { year: number; invested: number; value: number }[] = (() => {
  const monthly = 25000;
  const r = 12 / 100 / 12;
  let bal = 0;
  let invested = 0;
  const out: { year: number; invested: number; value: number }[] = [];
  for (let y = 1; y <= 15; y++) {
    for (let m = 0; m < 12; m++) {
      bal = bal * (1 + r) + monthly;
      invested += monthly;
    }
    out.push({ year: y, invested, value: bal });
  }
  return out;
})();

export const SIP_DEFAULTS = {
  monthly: '₹25,000',
  monthlyRangeMin: '₹500',
  monthlyRangeMax: '₹2,00,000',
  growth: '12%',
  growthRangeMin: '1%',
  growthRangeMax: '30%',
  years: '15 yrs',
  yearsRangeMin: '1 yr',
  yearsRangeMax: '40 yrs',
  sipPresets: ['₹5K', '₹10K', '₹25K', '₹50K', '₹1.0 L'],
  growthPresets: ['8%', '10%', '12%', '15%'],
  yearPresets: ['5y', '10y', '15y', '20y', '30y'],
};

export const SIP_KPIS = {
  future: '₹1.25 Cr',
  futureSub: 'From ₹25,000/month over 15 years',
  invested: '₹45.0 L',
  profit: '₹79.9 L',
  multiplier: '2.8×',
  profitPct: 64,
};

export const SIP_WHATIF: { name: string; val: string; result: string; delta: string; up: boolean }[] = [
  { name: 'Increase SIP by ₹5,000', val: '₹30,000/mo', result: '₹1.50 Cr', delta: '+₹25.0 L vs now', up: true },
  { name: 'Invest 5 years longer', val: '20 yrs', result: '₹2.47 Cr', delta: '+₹1.22 Cr vs now', up: true },
  { name: 'Earn 2% more', val: '14%', result: '₹1.51 Cr', delta: '+₹26.6 L vs now', up: true },
  { name: 'Start step-up SIP', val: '+10%/yr', result: '₹2.15 Cr', delta: '+₹90.1 L vs now', up: true },
  { name: 'Earn 2% less', val: '10%', result: '₹1.04 Cr', delta: '−₹21.3 L vs now', up: false },
  { name: 'Inflation @6%', val: 'real value', result: '₹52.1 L', delta: '−₹72.8 L vs now', up: false },
];

// AI insight strings (educational illustrations on the user's own inputs — not
// fund advice). **bold** spans are rendered by RichText.
export const SIP_AI: string[] = [
  '**Increasing your SIP by ₹5,000** could grow your corpus by **₹25.0 L** — often easier than chasing higher returns.',
  '**Starting one year earlier** adds **₹19.0 L**, which beats earning 1% more return (**₹12.5 L**). Time matters most.',
  '**Inflation at 6%** means your ₹1.25 Cr will buy what **₹52.1 L** buys today. Plan for real, not nominal, wealth.',
  '**A 10% yearly step-up** turns this into **₹2.15 Cr** — an extra **₹90.1 L** just by growing your SIP with your income.',
];

export const SIP_TABLE: { year: number; invested: string; wealth: string; profit: string; mult: string }[] = [
  { year: 1, invested: '₹3.0 L', wealth: '₹3.2 L', profit: '+₹17K', mult: '1.06×' },
  { year: 2, invested: '₹6.0 L', wealth: '₹6.7 L', profit: '+₹74K', mult: '1.12×' },
  { year: 4, invested: '₹12.0 L', wealth: '₹15.3 L', profit: '+₹3.3 L', mult: '1.28×' },
  { year: 6, invested: '₹18.0 L', wealth: '₹26.2 L', profit: '+₹8.2 L', mult: '1.45×' },
  { year: 8, invested: '₹24.0 L', wealth: '₹40.0 L', profit: '+₹16.0 L', mult: '1.67×' },
  { year: 10, invested: '₹30.0 L', wealth: '₹57.5 L', profit: '+₹27.5 L', mult: '1.92×' },
  { year: 12, invested: '₹36.0 L', wealth: '₹79.8 L', profit: '+₹43.8 L', mult: '2.22×' },
  { year: 14, invested: '₹42.0 L', wealth: '₹1.08 Cr', profit: '+₹66.0 L', mult: '2.57×' },
  { year: 15, invested: '₹45.0 L', wealth: '₹1.25 Cr', profit: '+₹79.9 L', mult: '2.78×' },
];

export const SIP_RELATED: { emoji: string; name: string; desc: string; accent: Accent }[] = [
  { emoji: '🎯', name: 'Goal SIP', desc: 'SIP for a target', accent: 'royal' },
  { emoji: '🧾', name: 'Capital Gains Tax', desc: 'Tax on returns', accent: 'amber' },
  { emoji: '💸', name: 'SWP', desc: 'Income in retirement', accent: 'emerald' },
  { emoji: '🏖', name: 'Retirement Planner', desc: 'Plan your corpus', accent: 'emerald' },
];

export const SIP_DETAIL = {
  title: 'SIP Calculator',
  sub: 'See how your monthly investment grows into wealth over time.',
  emoji: '📈',
};

export const DISCLAIMER_HUB =
  'DhanRadar is a research & analytics platform, not an investment advisor. Calculations are illustrative estimates. Markets carry risk.';

export const DISCLAIMER_CALC =
  'Calculations are estimates for illustration only and assume a constant annual return, which real markets do not provide. DhanRadar is a research & analytics platform, not an investment advisor. Mutual fund investments are subject to market risks.';
