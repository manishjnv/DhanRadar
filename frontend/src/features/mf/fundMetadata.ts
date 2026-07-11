/**
 * fundMetadata — pure title / description / JSON-LD builders for the Fund
 * Detail SSR core (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §18.6). Deliberately
 * dependency-free of `next` so `generateMetadata` in page.tsx stays a thin
 * wrapper and this logic is unit-testable without Next.js's request context.
 *
 * Compliance (non-neg #1/#2): NEVER emit a numeric DhanRadar score / factor
 * weight / fair-value here — only standard facts (NAV in ₹, returns in %,
 * category, plan type, rank ordinal) and the educational label WORD (never the
 * raw snake_case enum, never an advisory verb).
 */
import { EDU_LABELS } from '@/lib/displayLabel';
import { fundDisplayTitle, optionDisplay } from './explorer-format';
import type { FundHead } from './types';

/**
 * Production site origin — the domain already referenced in the OpenAPI spec
 * examples (frontend/src/types/api.ts). Overridable via NEXT_PUBLIC_SITE_URL
 * for preview/staging deployments.
 */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://dhanradar.com').replace(/\/$/, '');

export interface FundMetadataText {
  title: string;
  description: string;
}

/** Minimal, factual not-found metadata — unknown ISIN / 404 from the backend. */
export const FUND_NOT_FOUND_METADATA: FundMetadataText = {
  title: 'Fund not found — DhanRadar',
  description: "This fund isn't in our database yet. Browse the DhanRadar Fund Explorer to find it.",
};

function fmtPct(v: number | null): string | null {
  if (v == null) return null;
  const sign = v > 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}%`;
}

function fmtNav(v: number | null): string | null {
  if (v == null) return null;
  return `\u20B9${v.toFixed(2)}`;
}

/** Label WORD for a given `verb_label` — never the raw enum, never advisory. */
function labelWord(fund: FundHead): string | null {
  return fund.verb_label ? (EDU_LABELS[fund.verb_label] ?? null) : null;
}

/** Build the page <title>/<meta description> from REAL fetched fund.head data. */
export function buildFundMetadataText(fund: FundHead): FundMetadataText {
  // Short display title (founder rule 2026-07-11) + compact plan/option so the
  // per-ISIN variants of one scheme still get distinct browser-tab titles.
  // The full legal scheme_name stays in the description + JSON-LD for
  // exact-name searches.
  const variant = [
    fund.plan_type ? (fund.plan_type === 'direct' ? 'Direct' : 'Regular') : null,
    optionDisplay(fund),
  ].filter(Boolean).join(' \u00b7 ');
  const title = `${fundDisplayTitle(fund)}${variant ? ` (${variant})` : ''} \u2014 NAV, returns, DhanRadar read`;

  const parts: string[] = [];
  const category = fund.sebi_category ?? fund.category;
  if (category) parts.push(category);

  const nav = fmtNav(fund.nav_latest);
  if (nav) parts.push(`NAV ${nav}${fund.nav_date ? ` (as of ${fund.nav_date})` : ''}`);

  const r1y = fmtPct(fund.return_1y_pct);
  if (r1y) parts.push(`1Y return ${r1y}`);

  const r3y = fmtPct(fund.return_3y_pct);
  if (r3y) parts.push(`3Y return ${r3y}`);

  const word = labelWord(fund);
  if (word) parts.push(`DhanRadar educational read: ${word}`);

  const description =
    parts.length > 0
      ? `${fund.scheme_name} \u2014 ${parts.join(' \u00B7 ')}. Educational fund data from DhanRadar, not investment advice.`
      : `${fund.scheme_name} \u2014 mutual fund data and educational read from DhanRadar, not investment advice.`;

  return { title, description };
}

/** One schema.org PropertyValue entry for the JSON-LD `additionalProperty` list. */
interface PropertyValue {
  '@type': 'PropertyValue';
  name: string;
  value: string | number;
}

/**
 * Schema.org JSON-LD describing the fund as a factual entity. Compliance-
 * sensitive surface (re-read twice before changing): only standard facts reach
 * this object — NAV, returns %, expense ratio, category, rank ordinal, and the
 * educational label WORD. No unified score, no factor weight, no fair value, no
 * advisory verb. `FinancialProduct` is the closest standard schema.org type;
 * numeric facts that have no dedicated schema.org property (NAV, returns,
 * rank) are carried as named `PropertyValue` entries rather than inventing a
 * custom vocabulary.
 */
export function buildFundJsonLd(fund: FundHead, isin: string): Record<string, unknown> {
  const category = fund.sebi_category ?? fund.category ?? undefined;
  const word = labelWord(fund);

  const additionalProperty: PropertyValue[] = [];
  if (fund.nav_latest != null) {
    additionalProperty.push({ '@type': 'PropertyValue', name: 'NAV (INR)', value: fund.nav_latest });
  }
  if (fund.return_1y_pct != null) {
    additionalProperty.push({ '@type': 'PropertyValue', name: '1-Year Return (%)', value: fund.return_1y_pct });
  }
  if (fund.return_3y_pct != null) {
    additionalProperty.push({ '@type': 'PropertyValue', name: '3-Year Return (%)', value: fund.return_3y_pct });
  }
  if (fund.expense_ratio_pct != null) {
    additionalProperty.push({ '@type': 'PropertyValue', name: 'Expense Ratio (%)', value: fund.expense_ratio_pct });
  }
  if (fund.category_rank != null && fund.category_total != null) {
    additionalProperty.push({
      '@type': 'PropertyValue',
      name: 'Category Rank',
      value: `${fund.category_rank} of ${fund.category_total}`,
    });
  }
  if (word) {
    additionalProperty.push({ '@type': 'PropertyValue', name: 'DhanRadar Educational Read', value: word });
  }

  return {
    '@context': 'https://schema.org',
    '@type': 'FinancialProduct',
    name: fund.scheme_name,
    alternateName: fundDisplayTitle(fund),
    category,
    ...(fund.amc_name ? { provider: { '@type': 'Organization', name: fund.amc_name } } : {}),
    url: `${SITE_URL}/mf/fund/${isin}`,
    additionalProperty,
  };
}
