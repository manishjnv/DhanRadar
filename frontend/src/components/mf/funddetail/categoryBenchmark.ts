/**
 * Category → benchmark map (item 3, 2026-07 — category-appropriate chart
 * overlays on the fund detail Returns tab).
 *
 * Matches against `sebi_category` (the canonical SEBI leaf string, e.g.
 * "Equity Scheme - Large Cap Fund" — see backend/dhanradar/mf/taxonomy.py).
 * Rules are checked in order, most-specific first ("Large & Mid Cap" before
 * bare "Mid Cap", so a Large & Mid fund doesn't fall into the midcap rule).
 *
 * Only benchmarks that survived the live Yahoo-symbol verification in
 * `dhanradar.tasks.mf.BENCHMARK_REGISTRY` are used here. Nifty Smallcap 250
 * has NO working Yahoo symbol (every candidate returned a snapshot-only stub,
 * not a real historical series) — Small Cap funds fall back to nifty50, same
 * as every other unmapped category (Debt / Hybrid / Index / etc.).
 */

export interface BenchmarkMeta {
  key: 'nifty50' | 'nifty100' | 'nifty500' | 'nifty_midcap_150';
  displayName: string;
}

const NIFTY50: BenchmarkMeta = { key: 'nifty50', displayName: 'Nifty 50' };
const NIFTY100: BenchmarkMeta = { key: 'nifty100', displayName: 'Nifty 100' };
const NIFTY500: BenchmarkMeta = { key: 'nifty500', displayName: 'Nifty 500' };
const NIFTY_MIDCAP_150: BenchmarkMeta = { key: 'nifty_midcap_150', displayName: 'Nifty Midcap 150' };

const RULES: ReadonlyArray<readonly [RegExp, BenchmarkMeta]> = [
  [/large\s*&\s*mid|large\s+and\s+mid/i, NIFTY100],
  [/large\s*cap/i, NIFTY100],
  [/mid\s*cap/i, NIFTY_MIDCAP_150],
  [/small\s*cap/i, NIFTY50], // nifty_smallcap_250 unverified — fallback nifty50
  [/flexi\s*cap|multi\s*cap|elss|value|focused|contra|dividend\s*yield/i, NIFTY500],
];

/** Returns the category-appropriate benchmark, falling back to Nifty 50 for
 * Debt/Hybrid/Index/other categories and any unrecognized or missing string. */
export function benchmarkForCategory(sebiCategory: string | null | undefined): BenchmarkMeta {
  if (!sebiCategory) return NIFTY50;
  for (const [pattern, meta] of RULES) {
    if (pattern.test(sebiCategory)) return meta;
  }
  return NIFTY50;
}
