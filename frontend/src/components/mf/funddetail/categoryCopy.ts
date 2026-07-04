/**
 * Static per-category-class educational copy (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md
 * §16.2 "Per-category About this category explainer", §5 row 22 sticky-bar copy, W1).
 *
 * Copy is DATA, not JSX — plain, factual, descriptive, never advisory (non-neg #1).
 * Reused across every fund sharing a category/class, so this is the ONE place the
 * wording lives (§15 "define once in the copy registry").
 */

export type CategoryClass = 'equity' | 'debt' | 'hybrid' | 'other';

/** Coarse classifier from the raw SEBI category string (e.g. "Equity Scheme - Flexi Cap Fund"). */
export function classifyCategory(sebiCategory: string | null | undefined): CategoryClass {
  const c = (sebiCategory ?? '').toLowerCase();
  if (c.includes('debt') || c.includes('gilt') || c.includes('liquid') || c.includes('income') || c.includes('money market')) {
    return 'debt';
  }
  if (c.includes('hybrid')) return 'hybrid';
  if (c.includes('equity') || c.includes('elss')) return 'equity';
  return 'other';
}

// ── S2 Verdict — "About this category" (checked before the class fallback) ────────
const SUB_CATEGORY_COPY: [needle: string, copy: string][] = [
  ['flexi cap', 'Flexi cap funds can invest across large, mid and small companies, giving the manager freedom to move between them as conditions change.'],
  ['large cap', "Large cap funds mostly hold India's biggest, most established companies — historically steadier than mid or small caps."],
  ['mid cap', 'Mid cap funds hold mid-sized companies — more growth potential than large caps, with more price swings along the way.'],
  ['small cap', 'Small cap funds hold smaller, younger companies — the highest growth potential among equity categories, and the sharpest swings.'],
  ['elss', 'ELSS funds are equity funds with a 3-year lock-in that also qualify for a tax deduction under Section 80C.'],
  ['index', 'Index funds simply track a market index rather than picking stocks — cost is usually the main thing that separates one from another.'],
  ['liquid', 'Liquid funds hold very short-term money-market instruments, aiming for stability and easy access over growth.'],
  ['gilt', 'Gilt funds hold only government bonds, so credit risk is minimal — their price still moves with interest rates.'],
  ['corporate bond', 'Corporate bond funds hold bonds issued by companies — the extra yield over government bonds comes with some credit risk.'],
  ['aggressive hybrid', 'Aggressive hybrid funds mix equity and debt, usually 65–80% equity, aiming for equity-like growth with some debt cushioning.'],
];

const CLASS_FALLBACK_COPY: Record<CategoryClass, string> = {
  equity: 'Equity funds invest mainly in company shares — historically strong long-term growth potential among mutual fund categories, with the most year-to-year price movement.',
  debt: 'Debt funds invest mainly in bonds and money-market instruments — generally steadier than equity, with returns tied to interest rates and credit quality.',
  hybrid: 'Hybrid funds mix equity and debt in one portfolio, aiming to balance growth potential with some cushioning against swings.',
  other: 'This category covers a specialised or less common mandate — the scheme documents describe exactly what it invests in.',
};

/** One or two plain sentences describing what this fund's category typically invests in. */
export function getCategoryAboutCopy(sebiCategory: string | null | undefined): string {
  const c = (sebiCategory ?? '').toLowerCase();
  const hit = SUB_CATEGORY_COPY.find(([needle]) => c.includes(needle));
  return hit ? hit[1] : CLASS_FALLBACK_COPY[classifyCategory(sebiCategory)];
}

// ── S22 Sticky bar — per-category-class descriptive stats (never advisory) ────────
export interface StickyCategoryStats {
  horizon: string;
  phase: string;
  approach: string;
}

const STICKY_STATS: Record<CategoryClass, StickyCategoryStats> = {
  equity: {
    horizon: 'Often discussed for 5+ year horizons',
    phase: 'Moves with the stock market',
    approach: 'SIPs are commonly discussed for smoothing entry',
  },
  debt: {
    horizon: 'Often discussed for shorter horizons',
    phase: 'Moves mainly with interest rates',
    approach: 'Lumpsum entry is commonly discussed here',
  },
  hybrid: {
    horizon: 'Often discussed for 3–5 year horizons',
    phase: 'Moves with both stocks and bonds',
    approach: 'SIP or lumpsum are both commonly discussed',
  },
  other: {
    horizon: 'Horizon depends on the specific mandate',
    phase: 'Depends on the specific mandate',
    approach: 'The scheme documents describe the usual approach',
  },
};

export function getStickyCategoryStats(sebiCategory: string | null | undefined): StickyCategoryStats {
  return STICKY_STATS[classifyCategory(sebiCategory)];
}
