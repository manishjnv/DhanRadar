'use client';

/**
 * Fund Comparison page — /mf/compare  (V3)
 *
 * Public educational destination that compares up to 4 mutual funds side-by-side,
 * built to the approved FundComparisonPageV3 desktop + mobile mockups (24
 * sections, fully responsive). Reached from the "⇄ Compare" action on the Fund
 * Detail / Explorer surfaces. No auth required — wrapped in <MaybeShell> so
 * anonymous visitors get clean standalone chrome and logged-in users keep the
 * workspace shell (the V3 destination model, same as Fund Detail V3).
 *
 * DATA: this is a pure-UI build. Every section renders illustrative PREVIEW data
 * (see components/mf/compare/sampleData.ts) while the real comparison feed is
 * built in a later session — founder call 2026-06-24: build all UI now, wire data
 * later. NO API / routing / permission / business-logic changes.
 *
 * The two compliance gates that guard the deploy pipeline are honoured so CI can
 * ship the page: educational labels (no advisory verbs) + band rings / strength
 * words (no raw DhanRadar score in the DOM). Everything else is 1:1 with the
 * design and untouched for the functionality session.
 */

import * as React from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Skeleton } from '@/components/ui/Skeleton';
import { Preview } from '@/components/mf/compare/ui';
import {
  HeroSection, EduReadSection, ScoreboardSection, PersonaSection, MatrixSection,
  MoodSection, PerformanceSection, SipSection, RollingSection, RankingSection,
  RiskSection, FitSection, HoldingsSection, FlowSection, ManagerSection, AmcSection,
  CostSection, TaxSection, ValuationSection, ChangesSection, AltsSection,
  AiInsightsSection, FaqSection, StickyBar,
} from '@/components/mf/compare/sections';

function CompareSkeleton() {
  return (
    <div className="flex w-full flex-col gap-6">
      <Skeleton className="h-5 w-64 rounded-full" />
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
        <Skeleton className="h-72 rounded-2xl" />
        <Skeleton className="h-72 rounded-2xl" />
        <Skeleton className="h-72 rounded-2xl" />
      </div>
      <Skeleton className="h-44 rounded-3xl" />
    </div>
  );
}

function Crumb({ category, count }: { category: string; count: number }) {
  return (
    <nav className="mb-3.5 flex flex-wrap items-center gap-1.5 text-caption text-ink-muted" aria-label="Breadcrumb">
      <Link href="/mf/explore" className="hover:text-ink">Mutual Funds</Link>
      <span className="text-ink-faint">›</span>
      <Link href={`/mf/explore?category=${encodeURIComponent(category)}`} className="hover:text-ink">{category}</Link>
      <span className="text-ink-faint">›</span>
      <span className="font-semibold text-ink-secondary">Compare {count} funds</span>
    </nav>
  );
}

function CompareView() {
  const searchParams = useSearchParams();
  // Preview build: section data is illustrative; the URL just carries context.
  const category = searchParams.get('category') ?? 'Small Cap';
  const count = 3;

  return (
    <div className="w-full pb-24">
      <div className="mb-4">
        <Link href="/mf/explore" className="mb-3 inline-flex w-fit items-center gap-1 rounded text-small text-ink-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
          ← Back to Fund Explorer
        </Link>
        <Crumb category={category} count={count} />
      </div>

      {/* S1 — Hero comparison columns */}
      <SectionHeader index="01" title={`Comparing ${count} ${category} Funds`} info="Add up to 4" />
      <HeroSection />

      {/* S2 — DhanRadar educational read (was "Comparison Winner") */}
      <Section><SectionHeader index="02" title="DhanRadar Educational Read" tag="AI" /><EduReadSection /></Section>

      {/* S3 — Scoreboard */}
      <Section><SectionHeader index="03" title="Quick Comparison Scoreboard" info="12 modules · strongest highlighted" /><ScoreboardSection /></Section>

      {/* S4 — Who each fund suits */}
      <Section><SectionHeader index="04" title="Who Each Fund Suits" /><PersonaSection /></Section>

      {/* S5 — Decision matrix */}
      <Section><SectionHeader index="05" title="Smart Decision Matrix" tag="DhanRadar" /><MatrixSection /></Section>

      {/* S6 — Market mood */}
      <Section><SectionHeader index="06" title="Market Mood Comparison" tag="DMMI" info={<Preview />} /><MoodSection /></Section>

      {/* S7 — Performance */}
      <Section><SectionHeader index="07" title="Performance Center" info="Strongest highlighted per period" /><PerformanceSection /></Section>

      {/* S8 — SIP */}
      <Section><SectionHeader index="08" title="SIP Comparison Center" info={<Preview />} /><SipSection /></Section>

      {/* S9 — Rolling */}
      <Section><SectionHeader index="09" title="Rolling Returns Comparison" /><RollingSection /></Section>

      {/* S10 — Ranking */}
      <Section><SectionHeader index="10" title="Ranking Comparison" /><RankingSection /></Section>

      {/* S11 — Risk */}
      <Section><SectionHeader index="11" title="Risk Comparison Center" /><RiskSection /></Section>

      {/* S12 — Portfolio fit */}
      <Section><SectionHeader index="12" title="Portfolio Fit Comparison" tag="Exclusive" info={<Preview />} /><FitSection /></Section>

      {/* S13 — Holdings */}
      <Section><SectionHeader index="13" title="Portfolio Holdings Comparison" info={<Preview />} /><HoldingsSection /></Section>

      {/* S14 — Fund flow */}
      <Section><SectionHeader index="14" title="Fund Flow Intelligence" info={<Preview />} /><FlowSection /></Section>

      {/* S15 — Managers */}
      <Section><SectionHeader index="15" title="Fund Manager Comparison" /><ManagerSection /></Section>

      {/* S16 — AMC */}
      <Section><SectionHeader index="16" title="AMC Quality Comparison" /><AmcSection /></Section>

      {/* S17 — Cost */}
      <Section><SectionHeader index="17" title="Cost Comparison" info="Impact on ₹10 L over time" /><CostSection /></Section>

      {/* S18 — Tax */}
      <Section><SectionHeader index="18" title="Tax Comparison" info="On ₹2 L gain · >1yr" /><TaxSection /></Section>

      {/* S19 — Valuation */}
      <Section><SectionHeader index="19" title="Valuation Comparison" info={<Preview />} /><ValuationSection /></Section>

      {/* S20 — What changed */}
      <Section><SectionHeader index="20" title="What Changed Recently" tag="AI" /><ChangesSection /></Section>

      {/* S21 — Alternatives */}
      <Section><SectionHeader index="21" title="Better Alternatives" info="If none of these fit" /><AltsSection /></Section>

      {/* S22 — AI insights */}
      <Section><SectionHeader index="22" title="AI Insights Center" tag="AI" /><AiInsightsSection /></Section>

      {/* S23 — FAQ */}
      <Section><SectionHeader index="23" title="Frequently Asked" /><FaqSection /></Section>

      {/* Disclosure (educational boundary) */}
      <div className="mt-7 rounded-2xl border border-line bg-surface-2 p-4">
        <DisclosureBundle notAdvice="For education only — not investment advice. This comparison, its educational read, and the figures shown (many illustrative previews while data feeds are built) are educational signals derived from factual data, not recommendations to buy, sell, or hold any fund. Mutual fund investments are subject to market risks; read all scheme-related documents carefully. Past performance does not indicate future returns." />
      </div>

      {/* S24 — Sticky decision bar */}
      <StickyBar />
    </div>
  );
}

export default function FundComparePage() {
  return (
    <MaybeShell maxWidth="full">
      <React.Suspense fallback={<CompareSkeleton />}>
        <CompareView />
      </React.Suspense>
    </MaybeShell>
  );
}
