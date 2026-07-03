/**
 * Portfolio-section display formatters — pure, unit-tested helpers.
 */

// Longer phrases first so the alternation consumes "Asset Management Company" whole rather
// than stopping at "Asset Management" and leaving "Company" as punctuation leftover.
const AMC_SUFFIX_RE =
  /\s*[-,]?\s*\b(Asset Management Company|Asset Management|Investment Managers?|Mutual Fund|Trustee(?:\s+Company)?|Private|Pvt\.?|Limited|Ltd\.?|Company|Co\.?)\b\.?/gi;

/**
 * Bare fund-house brand name for the hero-style owner chip — strips every legal/product
 * suffix ("Asset Management Company", "Mutual Fund", "Trustee", "Private"/"Pvt",
 * "Limited"/"Ltd") down to the recognizable brand: "HDFC Asset Management Company Limited" →
 * "HDFC", "ICICI Prudential Asset Management Company Ltd" → "ICICI Prudential".
 *
 * Distinct from `shortenAmcName` (features/mf/explorer-format.ts), which keeps a trailing
 * "AMC" tag for the compact fund-explorer row instead of a bare name. Falls back to the
 * original name if stripping would empty it.
 */
export function shortAmcName(name: string): string {
  const stripped = name
    .replace(AMC_SUFFIX_RE, '')
    .replace(/\s{2,}/g, ' ')
    .replace(/[\s,.\-–—]+$/, '')
    .trim();
  return stripped.length > 0 ? stripped : name;
}
