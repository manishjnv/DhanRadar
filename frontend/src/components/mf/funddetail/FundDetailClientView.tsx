'use client';

/**
 * FundDetailClientView — the original Fund Detail page component (V3 redesign),
 * moved out of app/mf/fund/[isin]/page.tsx during the SSR-core migration
 * (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §18.6). `page.tsx` is now a Server
 * Component wrapper that fetches `fund.head` server-side (title/description/
 * JSON-LD) and renders
 * this component, passing the same payload down as `initialFundHead` so
 * useFundDetail() does not re-fetch on mount.
 *
 * Everything below (all 22 sections, hooks, 'use client') is UNCHANGED from
 * the pre-SSR-core version — this file is a pure move, plus the
 * `initialFundHead` prop threaded through to useFundDetail().
 *
 * Public educational destination view of a single mutual fund, rebuilt to the
 * approved FundDetailPageV3 mockup (22 sections, responsive desktop + mobile).
 * Fetches by ISIN alone (W0, FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §17) — the
 * `category` URL param (set by FundExplorerTable row navigation) is read only
 * for the "back to Explorer" link, never required to load. No auth required —
 * wrapped in <MaybeShell> so anonymous visitors/crawlers get clean standalone
 * chrome (no app sidebar = the V3 destination model) and logged-in users keep
 * the workspace shell.
 *
 * DATA: real values from useFundDetail() drive identity / assessment / rank /
 * NAV / expense ratio / AMC-AUM / period returns (W0). W1 wires Performance
 * Center (returns/rolling/rank-trend), Risk Center, Holdings, Manager, AMC
 * facts, Alternatives and Similar to real per-concept endpoints; W2 adds
 * SIP/Drawdowns/Consistency (Performance Center), rolling-3Y, and Fund Health
 * (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §17). A later wave (2026-07-06, "wire
 * remaining 6") wires Snapshot (S9, real KPI grid) and AMC Quality (S16, real
 * fact-line) to real data, wires Market Mood (S6) to the real GET /market/mood,
 * and turns Smart Entry Timing (S3), Tax Center (S17, labeled example inputs)
 * and FAQ (S21, interpolated real facts) honest — no source-blocked section
 * shows a fabricated number, only a factual explainer + the standard no-data
 * state. Market Cap/Asset Mix/Style Box, Fund Flow, Transactions, Portfolio
 * Fit, What Changed, and Assessment Breakdown still render illustrative
 * PREVIEW data or an honest empty-state while their feeds are built (W2/W3) —
 * founder call 2026-06-24: build all UI now, wire data later.
 *
 * COMPLIANCE: non-neg #1 (no advisory verbs — educational labels only),
 * #2 (no numeric score in DOM — band rings + strength words),
 * #4 (confidence as band word), #9 (NOT_ADVICE disclosure bundle).
 */

import * as React from 'react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { Skeleton } from '@/components/ui/Skeleton';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { fundDisplayTitle, optionDisplay } from '@/features/mf/explorer-format';
import { LiveBadge } from '@/components/mf/funddetail/parts';
import { useFundDetail, useFundComposition, useFundFactors, useLatestPortfolio } from '@/features/mf/api';
import { usePortfolioHoldings } from '@/features/portfolio/api';
import type { FundHead as ApiFundHead } from '@/features/mf/types';
import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';

import {
  HeroSection, StatusRow, VerdictSection, EntryTimingSection,
  MoodSection, ScoreBreakdownSection, StickyBar, type FundHead,
} from '@/components/mf/funddetail/sectionsHero';
import { benchmarkForCategory } from '@/components/mf/funddetail/categoryBenchmark';
import {
  PortfolioFitSection, MyInvestmentSection, FundHealthSection, WhatChangedSection,
} from '@/components/mf/funddetail/sectionsA';
import {
  SnapshotSection, PerformanceSection, RiskCenterSection,
} from '@/components/mf/funddetail/sectionsB';
import {
  HoldingsSection, FundFlowSection, ManagerSection, AmcSection,
} from '@/components/mf/funddetail/sectionsC';
import {
  TaxSection, TransactionsSection, AlternativesSection, SimilarSection, FaqSection,
} from '@/components/mf/funddetail/sectionsD';

// ---------------------------------------------------------------------------
// Loading + not-found
// ---------------------------------------------------------------------------
function FundDetailSkeleton() {
  return (
    <div className="w-full flex flex-col gap-6">
      <Skeleton className="h-5 w-64 rounded-full" />
      <Skeleton className="h-56 rounded-3xl" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Skeleton className="h-40 rounded-2xl" />
        <Skeleton className="h-40 rounded-2xl" />
      </div>
      <Skeleton className="h-48 rounded-2xl" />
    </div>
  );
}

function FundNotFound({ backHref }: { backHref: string }) {
  return (
    <div className="w-full flex flex-col gap-6">
      <Link href={backHref} className="inline-flex w-fit items-center gap-1 rounded text-small text-ink-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
        ← Back to Fund Explorer
      </Link>
      <div className="rounded-2xl border border-line bg-surface-2 p-10 text-center">
        <p className="text-small font-medium text-ink">Fund not found</p>
        <p className="mt-1 text-caption text-ink-muted">This fund isn&apos;t in our database yet — browse from the Fund Explorer to find it.</p>
        <Link href="/mf/explore" className="mt-4 inline-block rounded text-small font-medium text-royal underline underline-offset-2 transition-colors hover:text-royal/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
          Go to Fund Explorer →
        </Link>
      </div>
    </div>
  );
}

// Breadcrumb (V3 destination chrome — links only, no routing change)
function Crumb({ category, name }: { category: string; name: string }) {
  return (
    <nav className="flex flex-wrap items-center gap-1.5 text-caption text-ink-muted" aria-label="Breadcrumb">
      <Link href="/mf/explore" className="hover:text-ink">Mutual Funds</Link>
      <span className="text-ink-faint">›</span>
      <Link href={`/mf/explore?category=${encodeURIComponent(category)}`} className="hover:text-ink">{category}</Link>
      <span className="text-ink-faint">›</span>
      <span className="font-semibold text-ink-secondary">{name}</span>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Main view
// ---------------------------------------------------------------------------
function FundDetailView({ initialFundHead }: { initialFundHead?: ApiFundHead }) {
  const params = useParams<{ isin: string }>();
  const searchParams = useSearchParams();
  const isin = params.isin;
  const category = searchParams.get('category');

  const { data: fund, isLoading } = useFundDetail(isin, category, initialFundHead);
  const { data: compositionEnv } = useFundComposition(isin);
  const { data: factorsResp } = useFundFactors(isin);
  const backHref = category ? `/mf/explore?category=${encodeURIComponent(category)}` : '/mf/explore';

  // P1 (My Investment / Transactions / Tax seed) — 404 on /mf/portfolio/latest = anonymous or no
  // CAS yet; portfolioId stays '' and every personal section below renders its own upload-CAS
  // empty state (never hidden). Holdings are fetched ONCE here and dedup via the shared TanStack
  // cache with MyInvestmentSection's own identical call (same pattern as useFundComposition above).
  const { data: latestPortfolio } = useLatestPortfolio();
  const portfolioId = latestPortfolio?.portfolio_id ?? '';
  const { data: holdingsEnv } = usePortfolioHoldings(portfolioId);
  const myHolding = holdingsEnv?.data?.holdings.find((h) => h.isin === isin) ?? null;

  if (isLoading) return <FundDetailSkeleton />;
  if (!fund) return <FundNotFound backHref={backHref} />;

  const planLabel =
    fund.plan_type === 'direct' ? 'Direct' : fund.plan_type === 'regular' ? 'Regular' : null;
  // "IDCW · Daily" etc. — shared helper appends the payout frequency.
  const optionLabel = optionDisplay(fund);

  const head: FundHead = {
    // Founder rule 2026-07-11: short title everywhere; full name = tooltip only.
    name: fundDisplayTitle(fund),
    fullName: fund.scheme_name,
    amc: fund.amc_name,
    category: fund.sebi_category ?? 'Mutual Fund',
    // null verb_label (unranked fund, W0 gate: any ISIN loads) → the label set's own
    // "not yet rated" value — never a fabricated educational read.
    label: (fund.verb_label ?? 'insufficient_data') as Label,
    band: (fund.confidence_band ?? null) as ConfidenceBand | null,
    rank: fund.category_rank,
    total: fund.category_total,
    planOption: [planLabel, optionLabel].filter(Boolean) as string[],
    aumCr: fund.amc_level_aum_crore,
    navLatest: fund.nav_latest,
    navDate: fund.nav_date,
    navChangePct: fund.nav_change_pct,
    expenseRatioPct: fund.expense_ratio_pct,
    return3mPct: fund.return_3m_pct,
    return6mPct: fund.return_6m_pct,
    return1yPct: fund.return_1y_pct,
    return3yPct: fund.return_3y_pct,
    return5yPct: fund.return_5y_pct,
    launchDate: fund.launch_date,
    fundAumCr: fund.aum_crore,
    fundAumAsOf: fund.aum_as_of,
  };

  // S10 header info line — category-appropriate benchmark (item 3, 2026-07);
  // ReturnsTab (sectionsB.tsx) falls back to Nifty 50 if the mapped
  // benchmark's series is empty, but the header caption always names the
  // category's intended benchmark.
  const benchmarkMeta = benchmarkForCategory(head.category);

  // S13 header info line — real when composition data exists (dedups against
  // HoldingsSection's own useFundComposition call via the shared query cache).
  // "All N disclosed" (Block 0.11, ADR-0033-B) — every constituent row SEBI's
  // monthly disclosure publishes is already captured (no top-10-per-scheme cap
  // anywhere in the pipeline), so "Top N" would misleadingly imply a partial
  // subset even when N is the fund's true full holdings count.
  const composition = compositionEnv?.data;
  const holdingsInfo = composition && composition.holdings.length > 0
    ? `All ${composition.holdings.length} disclosed holdings${composition.coverage.weight_covered_pct != null ? ` · ${composition.coverage.weight_covered_pct}% of assets` : ''}${composition.as_of_month ? ` · as of ${new Date(composition.as_of_month).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })}` : ''}`
    : 'Holdings not disclosed for this fund house yet';

  // W2 (§10.1) — real factor bands + signal words; every field null/empty until
  // the fund is ranked (§14.1 no-suppress: sections render their own no-data state).
  const factors = factorsResp?.factors?.data?.factors ?? null;
  const contributing = factorsResp?.signals?.data?.contributing ?? [];
  const contradicting = factorsResp?.signals?.data?.contradicting ?? [];
  const topReason = contributing[0] ?? null;

  return (
    <div className="w-full pb-24">
      <div className="mb-4">
        <Link href={backHref} className="mb-3 inline-flex w-fit items-center gap-1 rounded text-small text-ink-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
          ← Back to Fund Explorer
        </Link>
        <Crumb category={head.category} name={head.name} />
      </div>

      {/* S1 — Hero + status */}
      <HeroSection head={head} factors={factors} />
      <StatusRow contributing={contributing} />

      {/* S2 — Educational verdict */}
      <Section><SectionHeader index="02" title="DhanRadar Educational Read" tag="Assessment" badge={<LiveBadge />} />{/* dev-verify */}<VerdictSection head={head} signals={{ contributing, contradicting }} /></Section>

      {/* S3 — Smart entry timing */}
      <Section><SectionHeader index="03" title="Smart Entry Timing" tag="DhanRadar" info="Category valuation context" /><EntryTimingSection /></Section>

      {/* S4 — Portfolio fit */}
      <Section><SectionHeader index="04" title="Portfolio Fit" tag="Exclusive" badge={<LiveBadge />} />{/* dev-verify */}<PortfolioFitSection portfolioId={portfolioId} isin={isin} /></Section>

      {/* S5 — My investment (P1 — real data) */}
      <Section><SectionHeader index="05" title="My Investment" info="Your own numbers for this fund" badge={<LiveBadge />} />{/* dev-verify */}<MyInvestmentSection portfolioId={portfolioId} isin={isin} /></Section>

      {/* S6 — Market mood */}
      <Section><SectionHeader index="06" title="Market Mood Analysis" tag="DMMI" badge={<LiveBadge />} />{/* dev-verify */}<MoodSection /></Section>

      {/* S7 — Fund health */}
      <Section><SectionHeader index="07" title="Fund Health Dashboard" info="Traffic-light read" badge={<LiveBadge />} />{/* dev-verify */}<FundHealthSection isin={isin} /></Section>

      {/* S8 — What changed */}
      <Section><SectionHeader index="08" title="What Changed This Month" tag="AI" badge={<LiveBadge />} />{/* dev-verify */}<WhatChangedSection isin={isin} /></Section>

      {/* S9 — Snapshot */}
      <Section><SectionHeader index="09" title="Investment Snapshot" badge={<LiveBadge />} />{/* dev-verify */}<SnapshotSection head={head} isin={isin} /></Section>

      {/* S10 — Performance center */}
      <Section><SectionHeader index="10" title="Performance Center" info={`vs ${benchmarkMeta.displayName} · price index, excludes dividends`} badge={<LiveBadge />} />{/* dev-verify */}<PerformanceSection head={head} isin={isin} /></Section>

      {/* S11 — Assessment breakdown (band rings, no numbers) */}
      <Section><SectionHeader index="11" title="DhanRadar Assessment Breakdown" info="How confident the read is — by dimension" badge={<LiveBadge />} />{/* dev-verify */}<ScoreBreakdownSection factors={factors} /></Section>

      {/* S12 — Risk center */}
      <Section><SectionHeader index="12" title="Risk Center" badge={<LiveBadge />} />{/* dev-verify */}<RiskCenterSection isin={isin} /></Section>

      {/* S13 — Holdings */}
      <Section><SectionHeader index="13" title="Portfolio Holdings" info={holdingsInfo} badge={<LiveBadge />} />{/* dev-verify */}<HoldingsSection isin={isin} /></Section>

      {/* S14 — Fund flow */}
      <Section><SectionHeader index="14" title="Fund Flow Intelligence" badge={<LiveBadge />} />{/* dev-verify */}<FundFlowSection isin={isin} /></Section>

      {/* S15 — Fund manager */}
      <Section><SectionHeader index="15" title="Fund Manager" badge={<LiveBadge />} />{/* dev-verify */}<ManagerSection isin={isin} /></Section>

      {/* S16 — AMC quality */}
      <Section><SectionHeader index="16" title="AMC Quality Center" badge={<LiveBadge />} />{/* dev-verify */}<AmcSection isin={isin} amcName={fund.amc_name ?? undefined} /></Section>

      {/* S17 — Tax center (P1 seed) */}
      <Section><SectionHeader index="17" title="Tax Center" info="FY 2026-27 · equity taxation" badge={<LiveBadge />} />{/* dev-verify */}<TaxSection seedValue={myHolding?.current_value} costBasis={myHolding?.invested_amount} /></Section>

      {/* S18 — Transactions (P1 — real data) */}
      <Section><SectionHeader index="18" title="Transaction History" info="Your own transactions for this fund" badge={<LiveBadge />} />{/* dev-verify */}<TransactionsSection portfolioId={portfolioId} isin={isin} /></Section>

      {/* S19 — Alternatives */}
      <Section><SectionHeader index="19" title="Alternatives" info="Same category, ranked nearby" badge={<LiveBadge />} />{/* dev-verify */}<AlternativesSection isin={isin} /></Section>

      {/* S20 — Similar funds */}
      <Section><SectionHeader index="20" title="Similar Funds" info="Swipe →" badge={<LiveBadge />} />{/* dev-verify */}<SimilarSection isin={isin} /></Section>

      {/* S21 — FAQ */}
      <Section><SectionHeader index="21" title="Frequently Asked" badge={<LiveBadge />} />{/* dev-verify */}<FaqSection head={head} /></Section>

      {/* Disclosure (non-neg #9) */}
      <div className="mt-7 rounded-2xl border border-line bg-surface-2 p-4">
        <p className="mb-3 text-small text-ink-secondary">
          DhanRadar doesn&apos;t sell funds or earn commissions. Everything here is education, not advice.
        </p>
        <DisclosureBundle notAdvice="For education only — not investment advice. Rankings, assessments, and the figures shown (many illustrative previews while data feeds are built) are educational signals derived from factual data, not recommendations to buy, sell, or hold any fund. Mutual fund investments are subject to market risks; read all scheme-related documents carefully. Past performance does not indicate future returns." />
      </div>

      {/* S22 — Sticky decision bar */}
      <StickyBar head={head} topReason={topReason} />
    </div>
  );
}

export default function FundDetailClientView({
  initialFundHead,
}: {
  initialFundHead?: ApiFundHead;
}) {
  return (
    <MaybeShell maxWidth="full">
      <React.Suspense fallback={<FundDetailSkeleton />}>
        <FundDetailView initialFundHead={initialFundHead} />
      </React.Suspense>
    </MaybeShell>
  );
}
