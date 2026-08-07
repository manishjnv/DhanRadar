/**
 * Invest wizard route — /mf/invest/[isin]  (Server Component wrapper)
 *
 * Mirrors the SSR pattern in app/mf/fund/[isin]/page.tsx: fetch fund.head
 * server-side via fetchFundHeadServer, then hand it to the 'use client'
 * wizard as `initialFundHead` so it never re-fetches on mount.
 *
 * `force-dynamic` is mandatory here too (docs/rca/README.md G8 — Next.js
 * would otherwise try to prerender this dynamic segment at `next build`,
 * when the backend is unreachable).
 *
 * Admin-gated: the real boundary is RequireAdmin() on every
 * /admin/bse-uat/* backend endpoint this wizard calls; InvestWizard also
 * gates client-side (notFound()) for a same UX as /admin/*.
 */

import { notFound } from 'next/navigation';
import { fetchFundHeadServer } from '@/features/mf/server-api';
import InvestWizard from '@/components/mf/invest/InvestWizard';
import type { FundHeadExt } from '@/components/mf/invest/parts';

export const dynamic = 'force-dynamic';

export default async function InvestPage({
  params,
}: {
  params: { isin: string };
}) {
  const fund = await fetchFundHeadServer(params.isin);
  if (!fund) notFound();

  // server-api.ts's FundHead does not yet declare min_lumpsum_amount /
  // min_sip_amount / exit_load_pct / exit_load_days / risk_o_meter — extend
  // locally rather than edit that shared file (task instruction).
  const fundExt = fund as unknown as FundHeadExt;

  return <InvestWizard isin={params.isin} initialFundHead={fundExt} />;
}
