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
 * "and" → "&", "10 year" → "10Y", and drop a trailing " Fund" (a mid-string
 * "Fund" is preserved, e.g. "Gilt Fund with 10Y constant duration").
 */
export function formatCategoryLabel(name: string): string {
  return name
    .replace(/\band\b/gi, '&')
    .replace(/\b10\s*years?\b/gi, '10Y')
    .replace(/\s+Fund$/i, '')
    .trim();
}

/**
 * Structural subset of FundHead / FundExplorerItem / search results — the
 * fields needed to build a display title + variant tags for any fund surface.
 */
export interface FundNamingFields {
  scheme_name: string;
  fund_name_short?: string | null;
  sebi_category?: string | null;
  plan_type?: 'direct' | 'regular' | null;
  option_type?: 'growth' | 'idcw' | 'dividend_reinvest' | 'dividend_payout' | null;
  idcw_frequency?: 'daily' | 'weekly' | 'fortnightly' | 'monthly' | 'quarterly' | 'half_yearly' | 'annual' | null;
}

/**
 * Canonical short display title for a fund — founder rule 2026-07-11: the UI
 * never shows the raw AMFI scheme name as a title. Variant facts (plan/option/
 * category) render as tags next to it (fundVariantTags); the full legal
 * scheme_name stays available for tooltips and SEO metadata.
 */
export function fundDisplayTitle(f: FundNamingFields): string {
  return f.fund_name_short ?? cleanSchemeName(f.scheme_name);
}

const OPTION_WORD: Record<string, string> = {
  growth: 'Growth',
  idcw: 'IDCW',
  dividend_reinvest: 'Div Reinvest',
  dividend_payout: 'Div Payout',
};

const FREQ_WORD: Record<string, string> = {
  daily: 'Daily',
  weekly: 'Weekly',
  fortnightly: 'Fortnightly',
  monthly: 'Monthly',
  quarterly: 'Quarterly',
  half_yearly: 'Half-yearly',
  annual: 'Annual',
};

/** "IDCW · Daily" / "Growth" / null — option chip text for a fund. */
export function optionDisplay(f: FundNamingFields): string | null {
  if (!f.option_type) return null;
  const word = OPTION_WORD[f.option_type] ?? null;
  if (!word) return null;
  const freq = f.option_type === 'idcw' && f.idcw_frequency ? FREQ_WORD[f.idcw_frequency] : null;
  return freq ? `${word} · ${freq}` : word;
}

/**
 * Factual variant tags rendered next to/under the short title, in order:
 * asset class ("Debt"), category ("Banking & PSU"), plan ("Direct"),
 * option ("IDCW · Daily"). All standard facts — no scores, no advice.
 */
export function fundVariantTags(f: FundNamingFields): string[] {
  const tags: string[] = [];
  if (f.sebi_category) {
    // "Debt Scheme - Banking and PSU Fund" → "Debt" + "Banking & PSU"
    const m = f.sebi_category.match(/^(.*?)\s+Scheme\s*-\s*(.*)$/i);
    if (m) {
      tags.push(m[1].trim(), formatCategoryLabel(m[2]));
    } else {
      tags.push(formatCategoryLabel(f.sebi_category));
    }
  }
  if (f.plan_type) tags.push(f.plan_type === 'direct' ? 'Direct' : 'Regular');
  const opt = optionDisplay(f);
  if (opt) tags.push(opt);
  return tags.filter((t) => t.length > 0);
}

/**
 * Shorten a long AMC / fund-house name for the compact row:
 * "… Asset Management [Company] [Private] [Limited]" → "… AMC"
 * (e.g. "ITI Asset Management Limited" → "ITI AMC"). Names that already use
 * "AMC" or a different legal form are left unchanged.
 */
export function shortenAmcName(name: string): string {
  return name
    .replace(
      /\bAsset Management(\s+(Company|Co\.?))?(\s+(Private|Pvt\.?))?(\s+(Limited|Ltd\.?))?\b/gi,
      'AMC',
    )
    .replace(/\s{2,}/g, ' ')
    .trim();
}
