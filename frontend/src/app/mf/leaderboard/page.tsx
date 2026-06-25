'use client';

/**
 * Rankings & Leaderboards page — /mf/leaderboard  (V1)
 *
 * Public educational discovery destination that ranks India's mutual funds across
 * 17 leaderboard sections, built 1:1 to the approved LeaderboardPageV1 desktop +
 * mobile mockups. Reached from "Leaderboard" in the left workspace nav. No auth
 * required — wrapped in <MaybeShell> so anonymous visitors get clean standalone
 * chrome and logged-in users keep the workspace shell (same V3 destination model
 * as Fund Detail / Fund Comparison).
 *
 * PURE-UI build: every section renders illustrative PREVIEW data (see
 * components/mf/leaderboard/sampleData.ts); the real ranking feed is wired in a
 * later session (founder call 2026-06-24 — build all UI now, wire data later). No
 * API / routing / permission / business-logic changes.
 *
 * The two deploy-gating compliance bridges are honoured exactly as the sister V3
 * pages do (educational labels in place of advisory verbs; band rings / strength
 * words in place of the raw DhanRadar score). Everything else is 1:1 with design.
 */

import * as React from 'react';
import Link from 'next/link';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  Anchor, HeroSection, CatNav, DiscoverSection, Top100Section, ChampionsSection,
  PerformanceSection, SipSection, RiskSection, ValueSection, IntelligenceSection,
  MarketSection, FlowsSection, ImprovedSection, ManagersSection, AmcSection,
  RatingsSection, AiInsightsSection, FaqSection, FilterSheet, TrendingSection,
} from '@/components/mf/leaderboard/sections';

function LeaderboardSkeleton() {
  return (
    <div className="flex w-full flex-col gap-6">
      <Skeleton className="h-5 w-64 rounded-full" />
      <Skeleton className="h-52 rounded-3xl" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
      </div>
      <Skeleton className="h-80 rounded-2xl" />
    </div>
  );
}

function Crumb() {
  return (
    <nav className="mb-3.5 flex flex-wrap items-center gap-1.5 text-caption text-ink-muted" aria-label="Breadcrumb">
      <Link href="/mf/explore" className="hover:text-ink">Mutual Funds</Link>
      <span className="text-ink-faint">›</span>
      <span className="font-semibold text-ink-secondary">Rankings &amp; Leaderboards</span>
    </nav>
  );
}

function LeaderboardView() {
  const [filterOpen, setFilterOpen] = React.useState(false);
  return (
    <div className="w-full pb-24">
      <div className="mb-4 flex items-start justify-between gap-3">
        <Crumb />
        <button
          type="button"
          onClick={() => setFilterOpen(true)}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-caption font-semibold text-ink-secondary hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 md:hidden"
          aria-label="Filter rankings"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 5 H21 L14 13 V20 L10 18 V13 Z" /></svg>
          Filters
        </button>
      </div>

      {/* S1 — Hero */}
      <HeroSection />

      {/* Sticky category nav */}
      <CatNav />

      {/* S2 — Discover */}
      <Anchor>
        <SectionHeader index="01" title="Discover" info="jump to what you’re looking for" />
        <DiscoverSection />
      </Anchor>

      {/* S3 — Top 100 */}
      <Anchor id="top100">
        <SectionHeader index="02" title="DhanRadar Top 100" tag="Flagship" info="the best funds in India, ranked" />
        <Top100Section />
      </Anchor>

      {/* S4 — Category Champions */}
      <Anchor id="champions">
        <SectionHeader index="03" title="Category Champions" info="the best fund in every category" />
        <ChampionsSection />
      </Anchor>

      {/* S5 — Performance */}
      <Anchor id="performance">
        <SectionHeader index="04" title="Performance Leaderboards" info="highest returns by period" />
        <PerformanceSection />
      </Anchor>

      {/* S6 — SIP */}
      <Anchor id="sip">
        <SectionHeader index="05" title="SIP Leaderboards" info="best for monthly investors" />
        <SipSection />
      </Anchor>

      {/* S7 — Risk */}
      <Anchor id="risk">
        <SectionHeader index="06" title="Risk Leaderboards" info="safest & steadiest funds" />
        <RiskSection />
      </Anchor>

      {/* S8 — Value */}
      <Anchor id="value">
        <SectionHeader index="07" title="Value Leaderboards" info="best return for the cost" />
        <ValueSection />
      </Anchor>

      {/* S9 — Intelligence */}
      <Anchor id="intelligence">
        <SectionHeader index="08" title="DhanRadar Intelligence" tag="Proprietary" info="our unique rankings" />
        <IntelligenceSection />
      </Anchor>

      {/* S10 — Current Market */}
      <Anchor id="market">
        <SectionHeader index="09" title="Current Market Leaders" tag="DMMI" info="what fits today’s market" />
        <MarketSection />
      </Anchor>

      {/* S11 — Fund Flows */}
      <Anchor id="flows">
        <SectionHeader index="10" title="Fund Flow Leaders" info="where the money is moving" />
        <FlowsSection />
      </Anchor>

      {/* S12 — Most Improved */}
      <Anchor id="improved">
        <SectionHeader index="11" title="Most Improved & Future Stars" info="funds on the rise" />
        <ImprovedSection />
      </Anchor>

      {/* S13 — Managers */}
      <Anchor id="managers">
        <SectionHeader index="12" title="Best Fund Managers" info="the people behind the returns" />
        <ManagersSection />
      </Anchor>

      {/* S14 — AMCs */}
      <Anchor id="amc">
        <SectionHeader index="13" title="Best AMCs" info="the most trusted fund houses" />
        <AmcSection />
      </Anchor>

      {/* S15 — Trusted Ratings */}
      <Anchor id="ratings">
        <SectionHeader index="14" title="Trusted Across Agencies" info="funds rated highly by everyone" />
        <RatingsSection />
      </Anchor>

      {/* S16 — Trending */}
      <Anchor id="trending">
        <SectionHeader index="15" title="Trending Now" info="biggest movers this week" />
        <TrendingSection />
      </Anchor>

      {/* S17 — AI Insights */}
      <Anchor>
        <SectionHeader index="16" title="AI Insights" tag="DhanRadar AI" />
        <AiInsightsSection />
      </Anchor>

      {/* S18 — FAQ */}
      <Anchor>
        <SectionHeader index="17" title="Rankings FAQ" />
        <FaqSection />
      </Anchor>

      {/* Disclosure (educational boundary) */}
      <div className="mt-7 rounded-2xl border border-line bg-surface-2 p-4">
        <DisclosureBundle notAdvice="For education only — not investment advice. These rankings, scores, third-party ratings and the figures shown (many illustrative previews while data feeds are built) are educational signals derived from factual data, not recommendations to buy, sell, or hold any fund. Mutual fund investments are subject to market risks; read all scheme-related documents carefully. Past performance does not indicate future returns." />
      </div>

      <FilterSheet open={filterOpen} onClose={() => setFilterOpen(false)} />
    </div>
  );
}

export default function LeaderboardPage() {
  return (
    <MaybeShell maxWidth="full">
      <React.Suspense fallback={<LeaderboardSkeleton />}>
        <LeaderboardView />
      </React.Suspense>
    </MaybeShell>
  );
}
