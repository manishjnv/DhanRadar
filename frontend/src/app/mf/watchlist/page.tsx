'use client';

/**
 * Watchlist Monitor — /mf/watchlist  (V1)
 *
 * Public educational destination for tracking a shortlist of mutual funds,
 * built 1:1 to the approved WatchlistPageV1 desktop + mobile mockups. Two
 * states: empty (get-started CTA) and dashboard (full 15-section monitor).
 * Reached from the workspace nav or directly by URL — no auth required, wrapped
 * in <MaybeShell> so anonymous visitors get clean standalone chrome and
 * logged-in users keep the workspace shell (same flat-route + MaybeShell +
 * Suspense model as Portfolio V1 / Fund Detail V3 / Leaderboard V1).
 *
 * PURE-UI build: every section renders illustrative PREVIEW data from
 * components/mf/watchlist/sampleData.ts; the real watchlist pipeline (save /
 * track / alerts / compare / export) is wired in a later session (founder call
 * 2026-06-25 — build all UI now, wire later).
 *
 * Compliance bridges honoured:
 *   1. No raw DhanRadar composite score in DOM — BandRing + strength WORD only.
 *   2. Educational verdict / momentum labels only — no advisory verbs.
 */

import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  AiCardsGrid, HeroSection, FilterSection, FundsSection, ChangedSection,
  OpportunitiesSection, DmmiSection, PerfSection, LeaderboardSection,
  AlertsSection, SimilarSection, StatsSection, DiscoverySection,
  RecentlyViewedSection, FaqSection, EmptyHero, BenefitsGrid,
  CompareTray, StickyBar,
} from '@/components/mf/watchlist/sections';
import { AI_SUMMARY, INSIGHTS } from '@/components/mf/watchlist/sampleData';

// ── Skeleton ─────────────────────────────────────────────────────────────────
function WatchlistSkeleton() {
  return (
    <div className="flex w-full flex-col gap-6">
      <Skeleton className="h-5 w-64 rounded-full" />
      <Skeleton className="h-44 rounded-3xl" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-72 rounded-2xl" />)}
      </div>
    </div>
  );
}

type PageState = 'empty' | 'dash';

function WatchlistView() {
  const [pageState, setPageState] = React.useState<PageState>('dash');
  const [selected, setSelected] = React.useState<Set<number>>(() => new Set());

  const toggle = React.useCallback((i: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else if (next.size < 4) next.add(i);
      return next;
    });
  }, []);
  const clear = React.useCallback(() => setSelected(new Set()), []);

  return (
    <div className="w-full pb-32">
      {/* Breadcrumb + state toggle */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <nav className="flex flex-wrap items-center gap-1.5 text-caption text-ink-muted" aria-label="Breadcrumb">
          <Link href="/mf/explore" className="hover:text-ink">Watchlist</Link>
          <span className="text-ink-faint">›</span>
          <span className="font-semibold text-ink-secondary">{pageState === 'empty' ? 'Get Started' : 'My Watchlist'}</span>
          {pageState === 'dash' && (
            <>
              <span className="text-ink-faint">·</span>
              <span className="text-ink-faint">8 funds tracked</span>
            </>
          )}
        </nav>
        <div className="flex rounded-xl border border-line bg-surface-2 p-1">
          {(['empty', 'dash'] as PageState[]).map((s) => (
            <button key={s} type="button" onClick={() => setPageState(s)}
              className={cn('whitespace-nowrap rounded-lg px-3 py-1.5 text-[11.5px] font-semibold transition-colors focus-visible:outline-none',
                pageState === s ? 'bg-surface text-ink shadow-sm' : 'text-ink-muted hover:text-ink')}>
              {s === 'empty' ? 'Empty' : 'Watchlist'}
            </button>
          ))}
        </div>
      </div>

      {/* ── EMPTY STATE ──────────────────────────────────────────────────────── */}
      {pageState === 'empty' && (
        <div className="flex flex-col gap-6">
          <EmptyHero onViewSample={() => setPageState('dash')} />
          <section>
            <SectionHeader title="What you'll get" />
            <BenefitsGrid />
          </section>
        </div>
      )}

      {/* ── DASHBOARD STATE ──────────────────────────────────────────────────── */}
      {pageState === 'dash' && (
        <div className="flex flex-col gap-6">
          <HeroSection />

          <section>
            <SectionHeader index="01" title="AI Watchlist Summary" tag="DhanRadar AI" />
            <AiCardsGrid items={AI_SUMMARY} />
          </section>

          <section>
            <SectionHeader index="02" title="Filter & Sort" info="Category · AMC · risk · strength · DMMI fit · momentum" />
            <FilterSection />
          </section>

          <section>
            <SectionHeader index="03" title="Watchlist Funds" info="8 funds · tap ⇄ to shortlist" />
            <FundsSection selected={selected} onToggle={toggle} />
          </section>

          <section>
            <SectionHeader index="04" title="What Changed" info="Since last week" />
            <ChangedSection />
          </section>

          <section>
            <SectionHeader index="05" title="Best Opportunities" info="In your watchlist" />
            <OpportunitiesSection />
          </section>

          <section>
            <SectionHeader index="06" title="DMMI Watchlist Analysis" tag="DhanRadar Mood" />
            <DmmiSection />
          </section>

          <section>
            <SectionHeader index="07" title="Watchlist Performance" info="vs category & benchmark" />
            <PerfSection />
          </section>

          <section>
            <SectionHeader index="08" title="Watchlist Leaderboard" info="Ranked by strength" />
            <LeaderboardSection />
          </section>

          <section>
            <SectionHeader index="09" title="Smart Alerts" info="6 new" />
            <AlertsSection />
          </section>

          <section>
            <SectionHeader index="10" title="Similar Funds Worth Watching" tag="Recommended" />
            <SimilarSection />
          </section>

          <section>
            <SectionHeader index="11" title="Watchlist Insights" tag="AI" />
            <AiCardsGrid items={INSIGHTS} />
          </section>

          <section>
            <SectionHeader index="12" title="Watchlist Statistics" />
            <StatsSection />
          </section>

          <section>
            <SectionHeader index="13" title="Discover More" info="Add to your watchlist" />
            <DiscoverySection />
          </section>

          <section>
            <SectionHeader index="14" title="Recently Viewed" />
            <RecentlyViewedSection />
          </section>

          <section>
            <SectionHeader index="15" title="Watchlist FAQ" />
            <FaqSection />
          </section>

          <p className="mx-auto max-w-[880px] text-center text-caption text-ink-faint leading-relaxed">
            DhanRadar is a research &amp; analytics platform, not an investment advisor. Watchlist data shown is illustrative. Mutual fund investments are subject to market risks; read all scheme-related documents carefully. Past performance does not guarantee future returns.
          </p>

          <div className="rounded-2xl border border-line bg-surface-2 p-4">
            <DisclosureBundle notAdvice="For education only — not investment advice. All watchlist values, strength bands, and labels shown are illustrative preview data; the real watchlist pipeline will be wired in a later session. Mutual fund investments are subject to market risks. Past performance does not indicate future returns." />
          </div>

          <CompareTray selected={selected} onClear={clear} />
          <StickyBar />
        </div>
      )}
    </div>
  );
}

export default function WatchlistPage() {
  return (
    <MaybeShell maxWidth="full">
      <React.Suspense fallback={<WatchlistSkeleton />}>
        <WatchlistView />
      </React.Suspense>
    </MaybeShell>
  );
}
