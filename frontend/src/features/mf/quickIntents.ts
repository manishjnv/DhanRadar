/**
 * Shared quick-intent chip registry — Phase C chip consolidation
 * (docs/features/leaderboard-interactivity-plan.md, founder 2026-08-16:
 * "what do all these filter buttons do?").
 *
 * One vocabulary, consumed by every chip surface (today: Explore hero row +
 * Quick Discovery row + "Try:" row). A chip is a saved query — a real category
 * filter, a real /mf/funds sort, or a real page/anchor — or it does not exist.
 * No decorative labels, no advisory wording, no promises of data we don't have
 * (see the plan's Phase C audit for the vocabulary this replaces).
 */

export type QuickIntentBacking =
  /** /mf/funds ?category= — full SEBI category string. */
  | { kind: 'category'; category: string }
  /** /mf/funds ?sort=&sort_dir= — sort MUST be one of the API's supported keys
   *  (rank/return_3m/return_6m/return_1y/return_3y/return_5y/max_drawdown). */
  | { kind: 'sort'; sort: string; dir: 'asc' | 'desc' }
  /** A real page or in-page anchor. */
  | { kind: 'href'; href: string };

export interface QuickIntent {
  id: string;
  label: string;
  icon?: string;
  /** One-line "how this list is built" — active-chip caption + chip title attr. */
  rule: string;
  backing: QuickIntentBacking;
}

export const QUICK_INTENTS: QuickIntent[] = [
  { id: 'top_rated', label: 'Top Rated', icon: '⭐', rule: 'DhanRadar rank, best first', backing: { kind: 'sort', sort: 'rank', dir: 'desc' } },
  { id: 'returns_3y', label: 'Highest 3Y Returns', icon: '📈', rule: '3-year return, highest first', backing: { kind: 'sort', sort: 'return_3y', dir: 'desc' } },
  { id: 'smallest_falls', label: 'Smallest Falls', icon: '🛡', rule: 'Smallest worst-fall (drawdown) first', backing: { kind: 'sort', sort: 'max_drawdown', dir: 'desc' } },
  { id: 'steady_starters', label: 'Steady Starters', icon: '❤️', rule: 'Published rule: large-cap & hybrid, label On Track or better, steadiest 1-year windows', backing: { kind: 'href', href: '/mf/leaderboard#sip' } },
  { id: 'lowest_cost', label: 'Lowest Cost', icon: '💸', rule: 'Lowest expense ratio boards', backing: { kind: 'href', href: '/mf/leaderboard#value' } },
  { id: 'best_sip', label: 'Best SIP Boards', icon: '💰', rule: '3Y/5Y SIP XIRR leader boards', backing: { kind: 'href', href: '/mf/leaderboard#sip' } },
  { id: 'trending', label: 'Trending', icon: '🔥', rule: 'Biggest recent rank moves', backing: { kind: 'href', href: '/mf/leaderboard#trending' } },
  { id: 'tax_elss', label: 'Tax Saving ELSS', icon: '🏦', rule: 'ELSS category', backing: { kind: 'category', category: 'Equity Scheme - ELSS' } },
  { id: 'index_funds', label: 'Index Funds', icon: '📊', rule: 'Index-funds category', backing: { kind: 'category', category: 'Other Scheme - Index Funds' } },
  { id: 'retirement', label: 'Retirement', icon: '🎯', rule: 'Retirement solution category', backing: { kind: 'category', category: 'Solution Oriented Scheme - Retirement Fund' } },
  { id: 'small_cap', label: 'Small Cap', rule: 'Small-cap category', backing: { kind: 'category', category: 'Equity Scheme - Small Cap Fund' } },
  { id: 'large_cap', label: 'Large Cap', rule: 'Large-cap category', backing: { kind: 'category', category: 'Equity Scheme - Large Cap Fund' } },
  { id: 'flexi_cap', label: 'Flexi Cap', rule: 'Flexi-cap category', backing: { kind: 'category', category: 'Equity Scheme - Flexi Cap Fund' } },
];
