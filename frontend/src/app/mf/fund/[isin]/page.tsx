'use client';

/**
 * Fund Detail page — /mf/fund/[isin]  (V3 redesign)
 *
 * Public educational destination view of a single mutual fund, rebuilt to the
 * approved FundDetailPageV3 mockup (22 sections, responsive desktop + mobile).
 * Resolved from the SEBI category list (uses the `category` URL param set by
 * FundExplorerTable row navigation). No auth required — wrapped in <MaybeShell>
 * so anonymous visitors/crawlers get clean standalone chrome (no app sidebar =
 * the V3 destination model) and logged-in users keep the workspace shell.
 *
 * DATA: real values from useFundDetail() drive identity / assessment / rank /
 * AMC-AUM. The rich sections (performance, holdings, manager, tax, flows, …)
 * render illustrative PREVIEW data (flagged "Preview") while the per-scheme
 * feeds are built — founder call 2026-06-24: build all UI now, wire data later.
 * NO API / routing / permission changes.
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
import { useFundDetail } from '@/features/mf/api';
import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';

import {
  HeroSection, StatusRow, VerdictSection, EntryTimingSection,
  MoodSection, ScoreBreakdownSection, StickyBar, type FundHead,
} from '@/components/mf/funddetail/sectionsHero';
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
    <div className="mx-auto w-full max-w-[1320px] flex flex-col gap-6">
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
    <div className="mx-auto w-full max-w-[1320px] flex flex-col gap-6">
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
function FundDetailView() {
  const params = useParams<{ isin: string }>();
  const searchParams = useSearchParams();
  const isin = params.isin;
  const category = searchParams.get('category');

  const { data: fund, isLoading } = useFundDetail(isin, category);
  const backHref = category ? `/mf/explore?category=${encodeURIComponent(category)}` : '/mf/explore';

  if (!category) return <FundNotFound backHref={backHref} />;
  if (isLoading) return <FundDetailSkeleton />;
  if (!fund) return <FundNotFound backHref={backHref} />;

  const planLabel =
    fund.plan_type === 'direct' ? 'Direct' : fund.plan_type === 'regular' ? 'Regular' : null;
  const optionLabel =
    fund.option_type === 'growth' ? 'Growth'
    : fund.option_type === 'idcw' ? 'IDCW'
    : fund.option_type === 'dividend_reinvest' ? 'Div Reinvest'
    : fund.option_type === 'dividend_payout' ? 'Div Payout'
    : null;

  const head: FundHead = {
    name: fund.scheme_name,
    amc: fund.amc_name,
    category: fund.sebi_category,
    label: fund.verb_label as Label,
    band: (fund.confidence_band ?? null) as ConfidenceBand | null,
    rank: fund.category_rank,
    total: fund.category_total,
    planOption: [planLabel, optionLabel].filter(Boolean) as string[],
    aumCr: fund.amc_level_aum_crore,
  };

  return (
    <div className="mx-auto w-full max-w-[1320px] pb-24">
      <div className="mb-4">
        <Link href={backHref} className="mb-3 inline-flex w-fit items-center gap-1 rounded text-small text-ink-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
          ← Back to Fund Explorer
        </Link>
        <Crumb category={fund.sebi_category} name={fund.scheme_name} />
      </div>

      {/* S1 — Hero + status */}
      <HeroSection head={head} />
      <StatusRow />

      {/* S2 — Educational verdict */}
      <Section><SectionHeader index="02" title="DhanRadar Educational Read" tag="Assessment" /><VerdictSection head={head} /></Section>

      {/* S3 — Smart entry timing */}
      <Section><SectionHeader index="03" title="Smart Entry Timing" tag="DhanRadar" info="Category valuation context" /><EntryTimingSection /></Section>

      {/* S4 — Portfolio fit */}
      <Section><SectionHeader index="04" title="Portfolio Fit" tag="Exclusive" /><PortfolioFitSection /></Section>

      {/* S5 — My investment */}
      <Section><SectionHeader index="05" title="My Investment" info="Preview — upload your CAS to see real holdings" /><MyInvestmentSection /></Section>

      {/* S6 — Market mood */}
      <Section><SectionHeader index="06" title="Market Mood Analysis" tag="DMMI" /><MoodSection /></Section>

      {/* S7 — Fund health */}
      <Section><SectionHeader index="07" title="Fund Health Dashboard" info="Traffic-light read" /><FundHealthSection /></Section>

      {/* S8 — What changed */}
      <Section><SectionHeader index="08" title="What Changed This Month" tag="AI" /><WhatChangedSection /></Section>

      {/* S9 — Snapshot */}
      <Section><SectionHeader index="09" title="Investment Snapshot" /><SnapshotSection /></Section>

      {/* S10 — Performance center */}
      <Section><SectionHeader index="10" title="Performance Center" info="vs Nifty Smallcap 250 TRI · Category" /><PerformanceSection /></Section>

      {/* S11 — Assessment breakdown (band rings, no numbers) */}
      <Section><SectionHeader index="11" title="DhanRadar Assessment Breakdown" info="8 modules · vs 18 peers" /><ScoreBreakdownSection /></Section>

      {/* S12 — Risk center */}
      <Section><SectionHeader index="12" title="Risk Center" /><RiskCenterSection /></Section>

      {/* S13 — Holdings */}
      <Section><SectionHeader index="13" title="Portfolio Holdings" info="250 stocks · as of 31 May 2026" /><HoldingsSection /></Section>

      {/* S14 — Fund flow */}
      <Section><SectionHeader index="14" title="Fund Flow Intelligence" /><FundFlowSection /></Section>

      {/* S15 — Fund manager */}
      <Section><SectionHeader index="15" title="Fund Manager" /><ManagerSection /></Section>

      {/* S16 — AMC quality */}
      <Section><SectionHeader index="16" title="AMC Quality Center" /><AmcSection amcName={fund.amc_name ?? undefined} /></Section>

      {/* S17 — Tax center */}
      <Section><SectionHeader index="17" title="Tax Center" info="FY 2026-27 · equity taxation" /><TaxSection /></Section>

      {/* S18 — Transactions */}
      <Section><SectionHeader index="18" title="Transaction History" info="Preview" /><TransactionsSection /></Section>

      {/* S19 — Alternatives */}
      <Section><SectionHeader index="19" title="Alternatives" info="Hand-picked by goal" /><AlternativesSection /></Section>

      {/* S20 — Similar funds */}
      <Section><SectionHeader index="20" title="Similar Funds" info="Swipe →" /><SimilarSection /></Section>

      {/* S21 — FAQ */}
      <Section><SectionHeader index="21" title="Frequently Asked" /><FaqSection /></Section>

      {/* Disclosure (non-neg #9) */}
      <div className="mt-7 rounded-2xl border border-line bg-surface-2 p-4">
        <DisclosureBundle notAdvice="For education only — not investment advice. Rankings, assessments, and the figures shown (many illustrative previews while data feeds are built) are educational signals derived from factual data, not recommendations to buy, sell, or hold any fund. Mutual fund investments are subject to market risks; read all scheme-related documents carefully. Past performance does not indicate future returns." />
      </div>

      {/* S22 — Sticky decision bar */}
      <StickyBar head={head} />
    </div>
  );
}

export default function FundDetailPage() {
  return (
    <MaybeShell maxWidth="full">
      <React.Suspense fallback={<FundDetailSkeleton />}>
        <FundDetailView />
      </React.Suspense>
    </MaybeShell>
  );
}
