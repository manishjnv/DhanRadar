/**
 * Fund Detail page — /mf/fund/[isin]  (SSR core, V3 redesign)
 *
 * Server Component wrapper (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §18.6 —
 * targeted SSR core, not a full rewrite of all 22 sections). Fetches
 * `fund.head` server-side so crawlers get real content in the initial HTML
 * response — page <title>/description, JSON-LD structured data, and a small
 * server-rendered summary block — then hands the SAME payload to the existing
 * 'use client' FundDetailClientView as `initialFundHead` so its
 * useFundDetail() hook does not re-fetch on mount (no double fetch).
 *
 * FundDetailClientView.tsx carries the full 22-section client view UNCHANGED
 * (moved here verbatim during this migration — see that file's own header).
 *
 * BUILD-TIME TRAP (docs/rca/README.md G8): Next.js prerenders dynamic-segment
 * pages at `next build` by default, including generateMetadata's own fetch —
 * and the backend is not reachable during CI's `next build` (mocks-off job).
 * `force-dynamic` below is therefore mandatory, not optional — the same proven
 * fix already shipped on frontend/src/app/learn/tax/[slug]/page.tsx. It opts
 * this route OUT of static generation entirely, so neither generateMetadata
 * nor the page body ever run at build time — only at real request time.
 *
 * Caching: `force-dynamic` does NOT force every fetch in the route to
 * `no-store` — an individual fetch's own `next: { revalidate: N }` option is
 * still honored (verified against this Next.js version's fetch-cache
 * semantics: vercel/next.js test/e2e/app-dir/app-static/app/
 * force-dynamic-fetch-cache/revalidate/page.js — "should infer a fetch cache
 * of 'force-cache' when force-dynamic is used on a fetch with revalidate").
 * So `fetchFundHeadServer` (features/mf/server-api.ts) caches its own fetch
 * for ~1h (`next: { revalidate: 3600 }`) while this route still renders per
 * request — repeat requests within the hour reuse the cached backend response
 * instead of re-hitting the backend every time. Confirmed via `npm run build`
 * (no backend running) that this combination does NOT reintroduce the G8
 * ECONNREFUSED trap — force-dynamic means the route is never touched at build.
 *
 * No `generateStaticParams` — 14k ISINs must never be attempted at build
 * time; every fund page renders on-demand.
 *
 * COMPLIANCE: non-neg #1 (no advisory verbs), #2 (no numeric DhanRadar score —
 * JSON-LD/metadata/summary block carry standard facts only: NAV, returns %,
 * category, plan type, rank ordinal, and the educational label WORD).
 */

import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { fetchFundHeadServer } from '@/features/mf/server-api';
import { buildFundMetadataText, buildFundJsonLd, FUND_NOT_FOUND_METADATA } from '@/features/mf/fundMetadata';
import { fundDisplayTitle, fundVariantTags } from '@/features/mf/explorer-format';
import { EDU_LABELS } from '@/lib/displayLabel';
import FundDetailClientView from '@/components/mf/funddetail/FundDetailClientView';

// Mandatory — see file header ("BUILD-TIME TRAP").
export const dynamic = 'force-dynamic';

export async function generateMetadata({
  params,
}: {
  params: { isin: string };
}): Promise<Metadata> {
  const fund = await fetchFundHeadServer(params.isin);
  if (!fund) return FUND_NOT_FOUND_METADATA;

  const { title, description } = buildFundMetadataText(fund);
  return {
    title,
    description,
    openGraph: { title, description, type: 'website', siteName: 'DhanRadar' },
  };
}

export default async function FundDetailPage({
  params,
}: {
  params: { isin: string };
}) {
  // Next.js dedupes identical fetch() calls (same URL + options) made during a
  // single request across generateMetadata and the page body, so this does not
  // double-hit the backend.
  const fund = await fetchFundHeadServer(params.isin);
  if (!fund) notFound();

  const jsonLd = buildFundJsonLd(fund, params.isin);
  const labelWord = fund.verb_label ? EDU_LABELS[fund.verb_label] : null;
  // Founder rule 2026-07-11: short title everywhere; variant facts as tags.
  // The full legal scheme_name stays in JSON-LD/metadata + the h1 tooltip.
  const displayTitle = fundDisplayTitle(fund);
  const variantTags = fundVariantTags(fund);

  return (
    <>
      {/* JSON-LD — factual fund entity only (compliance non-neg #1/#2: no
          score, no advisory verb; see features/mf/fundMetadata.ts). */}
      <script
        type="application/ld+json"
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* Server-rendered summary — real content in the initial HTML response,
          verifiable via `curl` without JS execution. Plain text label WORD
          only (never the ScoreRing/numeric component). Passed INTO the client
          view so it renders inside the shell's scroll area and scrolls away
          with the page — rendered here (outside MaybeShell/AppShell) it sat
          pinned above the app chrome and never scrolled. */}
      <FundDetailClientView
        initialFundHead={fund}
        ssrSummary={
          <div className="mb-4 rounded-2xl border border-line bg-surface-2 p-3">
            <h1 className="text-h3 text-ink" title={fund.scheme_name}>{displayTitle}</h1>
            {variantTags.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1.5" title={fund.scheme_name}>
                {variantTags.map((t) => (
                  <span key={t} className="rounded-full border border-line bg-surface px-2 py-0.5 text-caption text-ink-secondary">
                    {t}
                  </span>
                ))}
              </div>
            )}
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-small text-ink-secondary">
              {fund.nav_latest != null && (
                <span>NAV ₹{fund.nav_latest.toFixed(2)}{fund.nav_date ? ` (as of ${fund.nav_date})` : ''}</span>
              )}
              {fund.return_1y_pct != null && <span>1Y return {fund.return_1y_pct.toFixed(1)}%</span>}
              {fund.return_3y_pct != null && <span>3Y return {fund.return_3y_pct.toFixed(1)}%</span>}
              {labelWord && <span>DhanRadar educational read: {labelWord}</span>}
            </div>
          </div>
        }
      />
    </>
  );
}
