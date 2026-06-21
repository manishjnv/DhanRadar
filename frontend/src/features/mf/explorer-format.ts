/**
 * Fund Explorer display formatters — pure, unit-tested helpers.
 *
 * Kept separate from the components so the row-height + category-label logic can
 * be exercised directly in tests (no DOM render needed).
 */

/**
 * Strip the trailing plan/option suffix that AMFI bakes into a scheme name
 * (e.g. "ITI Banking & PSU Debt Fund - Regular Plan - Growth Option"). That
 * suffix is already shown as compact chips, so repeating it wastes a whole row
 * line. Falls back to the original name if stripping would empty it.
 */
const PLAN_OPT_SUFFIX =
  /\s*[-–—]\s*(regular|direct)(\s+plan)?\b.*$|\s*[-–—]\s*(growth|idcw|dividend|income distribution|payout|reinvest)\b.*$/i;

export function cleanSchemeName(name: string): string {
  const cleaned = name.replace(PLAN_OPT_SUFFIX, '').trim();
  return cleaned.length > 0 ? cleaned : name;
}

/**
 * Shorten a SEBI category display name for the compact filter:
 * "and" → "&" and drop a trailing " Fund" (a mid-string "Fund" is preserved,
 * e.g. "Gilt Fund with 10 year constant duration" is left intact).
 */
export function formatCategoryLabel(name: string): string {
  return name.replace(/\band\b/gi, '&').replace(/\s+Fund$/i, '').trim();
}
