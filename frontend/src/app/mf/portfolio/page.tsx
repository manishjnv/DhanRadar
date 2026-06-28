'use client';

/**
 * Portfolio Command Center — /mf/portfolio  (V1)
 *
 * Public educational destination for CAS-upload portfolio analysis, built 1:1
 * to the approved PortfolioPageV1 mockup. Two states: empty (upload CTA) and
 * dashboard (full 21-section analysis). Reached from the workspace nav or
 * directly by URL. No auth required — wrapped in <MaybeShell> so anonymous
 * visitors get clean standalone chrome and logged-in users keep the workspace
 * shell (same flat-route + MaybeShell + Suspense model as Fund Detail V3 /
 * Fund Comparison V3 / Leaderboard V1).
 *
 * PURE-UI build: every section renders illustrative PREVIEW data from
 * components/mf/portfolio/sampleData.ts; the real CAS-upload pipeline is wired
 * in a later session (founder call 2026-06-25 — build all UI now, wire later).
 *
 * Compliance bridges honoured:
 *   1. No raw DhanRadar composite score in DOM — BandRing + strength WORD only.
 *   2. Educational status labels only — no advisory verbs.
 */

import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  EmptyHero, BenefitsGrid, AutoSyncBanner,
  HeroSection, HealthSection, ActionSection, DmmiSection, AllocSection,
  GoalSection, PerfSection, HoldingsSection, TopPerfSection, UnderReviewSection,
  OverlapSection, DivSection, RiskSection, CostSection, AmcSection,
  TimelineSection, RecSection, ProjSection, OpportunitiesSection,
  AiSection, ReportSection, FaqSection,
} from '@/components/mf/portfolio/sections';
import { useLatestPortfolio } from '@/features/mf/api';

// ── Skeleton ─────────────────────────────────────────────────────────────────
function PortfolioSkeleton() {
  return (
    <div className="flex w-full flex-col gap-6">
      <Skeleton className="h-5 w-64 rounded-full" />
      <Skeleton className="h-52 rounded-3xl" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
      </div>
      <Skeleton className="h-64 rounded-2xl" />
    </div>
  );
}

// ── Page state ────────────────────────────────────────────────────────────────
type PageState = 'empty' | 'dash';

// ── Main view ─────────────────────────────────────────────────────────────────
function PortfolioView() {
  const [pageState, setPageState] = React.useState<PageState>('dash');
  // Resolve the user's active portfolio id. 404 = no portfolio yet (show empty state).
  const { data: latestPortfolio } = useLatestPortfolio();
  const portfolioId = latestPortfolio?.portfolio_id ?? '';

  return (
    <div className="w-full pb-32">
      {/* Breadcrumb + state toggle */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <nav className="flex flex-wrap items-center gap-1.5 text-caption text-ink-muted" aria-label="Breadcrumb">
          <Link href="/mf/explore" className="hover:text-ink">Mutual Funds</Link>
          <span className="text-ink-faint">›</span>
          <span className="font-semibold text-ink-secondary">
            {pageState === 'empty' ? 'Get Started' : 'Command Center'}
          </span>
          {pageState === 'dash' && (
            <>
              <span className="text-ink-faint">·</span>
              <span className="text-ink-faint">Updated 25 Jun 2026, 6:00 PM</span>
            </>
          )}
        </nav>
        {/* State toggle */}
        <div className="flex rounded-xl border border-line bg-surface-2 p-1">
          {(['empty', 'dash'] as PageState[]).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setPageState(s)}
              className={cn(
                'whitespace-nowrap rounded-lg px-3 py-1.5 text-[11.5px] font-semibold transition-colors focus-visible:outline-none',
                pageState === s ? 'bg-surface text-ink shadow-sm' : 'text-ink-muted hover:text-ink',
              )}
            >
              {s === 'empty' ? 'Empty' : 'Dashboard'}
            </button>
          ))}
        </div>
      </div>

      {/* ── EMPTY STATE ──────────────────────────────────────────────────────── */}
      {pageState === 'empty' && (
        <div className="flex flex-col gap-5">
          <EmptyHero onViewSample={() => setPageState('dash')} />
          <section className="mt-2">
            <SectionHeader title="What you'll unlock" />
            <BenefitsGrid />
          </section>
          <AutoSyncBanner />
        </div>
      )}

      {/* ── DASHBOARD STATE ───────────────────────────────────────────────────── */}
      {pageState === 'dash' && (
        <div className="flex flex-col gap-6">
          {/* S1 Hero */}
          <HeroSection portfolioId={portfolioId} />

          {/* S01 Portfolio Health */}
          <section>
            <SectionHeader index="01" title="Portfolio Health" info="10 checks · green / yellow / red" />
            <HealthSection />
          </section>

          {/* S02 Action Center */}
          <section>
            <SectionHeader index="02" title="Action Center" tag="Needs attention" info="5 items" />
            <ActionSection />
          </section>

          {/* S03 DMMI */}
          <section>
            <SectionHeader index="03" title="DMMI Portfolio Analysis" tag="DhanRadar Mood" />
            <DmmiSection />
          </section>

          {/* S04 Allocation */}
          <section>
            <SectionHeader index="04" title="Allocation Center" info="Current vs recommended" />
            <AllocSection />
          </section>

          {/* S05 Goals */}
          <section>
            <SectionHeader index="05" title="Goal Tracker" />
            <GoalSection />
          </section>

          {/* S06 Performance */}
          <section>
            <SectionHeader index="06" title="Performance Center" info="vs benchmark & category" />
            <PerfSection />
          </section>

          {/* S07 Holdings */}
          <section>
            <SectionHeader index="07" title="Fund Holdings" />
            <HoldingsSection portfolioId={portfolioId} />
          </section>

          {/* S08 Top Performers */}
          <section>
            <SectionHeader index="08" title="Top Performers" />
            <TopPerfSection />
          </section>

          {/* S09 Funds Needing Review */}
          <section>
            <SectionHeader index="09" title="Funds Needing Review" info="2 funds" />
            <UnderReviewSection />
          </section>

          {/* S10 Overlap */}
          <section>
            <SectionHeader index="10" title="Fund Overlap Analysis" tag="Differentiator" />
            <OverlapSection />
          </section>

          {/* S11 Diversification */}
          <section>
            <SectionHeader index="11" title="Diversification Center" info="Current vs ideal" />
            <DivSection />
          </section>

          {/* S12 Risk */}
          <section>
            <SectionHeader index="12" title="Risk Center" info="In plain English" />
            <RiskSection portfolioId={portfolioId} />
          </section>

          {/* S13 Cost */}
          <section>
            <SectionHeader index="13" title="Cost Analysis" info="What fees cost you" />
            <CostSection />
          </section>

          {/* S14 AMC */}
          <section>
            <SectionHeader index="14" title="AMC Exposure" info="Concentration & quality" />
            <AmcSection />
          </section>

          {/* S15 Timeline */}
          <section>
            <SectionHeader index="15" title="Portfolio Timeline" info="Key events" />
            <TimelineSection />
          </section>

          {/* S16 Recommendations */}
          <section>
            <SectionHeader index="16" title="Recommendations" tag="Decision support" />
            <RecSection />
          </section>

          {/* S17 Projection */}
          <section>
            <SectionHeader index="17" title="Future Wealth Projection" info="If you stay the course" />
            <ProjSection />
          </section>

          {/* S18 Opportunities */}
          <section>
            <SectionHeader index="18" title="Opportunities to Improve" tag="Recommended funds" />
            <OpportunitiesSection />
          </section>

          {/* S19 AI Feed */}
          <section>
            <SectionHeader index="19" title="AI Insights Feed" tag="DhanRadar AI" />
            <AiSection />
          </section>

          {/* S20 Report Center */}
          <section>
            <SectionHeader index="20" title="Report Center" tag="Premium" />
            <ReportSection />
          </section>

          {/* S21 FAQ */}
          <section>
            <SectionHeader index="21" title="Portfolio FAQ" />
            <FaqSection />
          </section>

          {/* Closing disclaimer */}
          <p className="mx-auto max-w-[880px] text-center text-caption text-ink-faint leading-relaxed">
            DhanRadar is a research &amp; analytics platform, not an investment advisor. Portfolio data shown is illustrative and based on an uploaded CAS. Mutual fund investments are subject to market risks; read all scheme-related documents carefully. Past performance does not guarantee future returns.
          </p>

          {/* Disclosure bundle */}
          <div className="rounded-2xl border border-line bg-surface-2 p-4">
            <DisclosureBundle notAdvice="For education only — not investment advice. All portfolio values, scores, and projections shown are illustrative preview data; the real CAS-upload pipeline will be wired in a later session. Mutual fund investments are subject to market risks. Past performance does not indicate future returns." />
          </div>
        </div>
      )}

      {/* Sticky action bar (dashboard only) */}
      {pageState === 'dash' && <StickyBar />}
    </div>
  );
}

// ── Sticky action bar ─────────────────────────────────────────────────────────
function StickyBar() {
  return (
    <div
      className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded-[16px] shadow-xl max-w-[calc(100%-1.25rem)]"
      style={{ background: 'rgba(11,31,58,.97)', backdropFilter: 'blur(12px)' }}
    >
      {/* Actions scroll horizontally inside the bar so nothing clips on narrow screens */}
      <div className="flex items-center gap-1.5 overflow-x-auto px-3 py-2.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {(
          [
            { label: '⬆ Upload Latest CAS', primary: true },
            { label: '↻ Refresh' },
            { label: '📄 Generate Report' },
            { label: '⬇ Export' },
            { label: '⚡ Auto Sync', soon: true },
          ] as { label: string; primary?: boolean; soon?: boolean }[]
        ).map(({ label, primary, soon }) => (
          <button
            key={label}
            type="button"
            className={cn(
              'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-xl border px-3.5 py-2 text-small font-semibold text-white transition-colors focus-visible:outline-none',
              primary ? 'border-royal bg-royal' : 'border-white/14 bg-white/10 hover:bg-white/20',
              soon && 'opacity-65',
            )}
          >
            {label}
            {soon && (
              <span className="ml-1 rounded-[5px] bg-violet px-1 py-px text-[8px] font-bold uppercase text-white">
                Soon
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Page export ───────────────────────────────────────────────────────────────
export default function PortfolioPage() {
  return (
    <MaybeShell maxWidth="full">
      <React.Suspense fallback={<PortfolioSkeleton />}>
        <PortfolioView />
      </React.Suspense>
    </MaybeShell>
  );
}
