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
 * DATA (docs/features/leaderboard-data-backend.md, this session): GET /mf/leaderboard
 * feeds Hero + 11 of 17 sections via useLeaderboard() (see sections.tsx). A board
 * absent from the response — endpoint not deployed yet, or that board isn't wired
 * server-side — leaves its section on the original illustrative PREVIEW from
 * components/mf/leaderboard/sampleData.ts, same LiveBadge/Preview-chip pattern as
 * the sister Fund Comparison page. No section is ever deleted or hidden.
 *
 * The two deploy-gating compliance bridges are honoured exactly as the sister V3
 * pages do (educational labels in place of advisory verbs; band rings / strength
 * words in place of the raw DhanRadar score — live rows carry no score field at
 * all). Everything else is 1:1 with design.
 */

import * as React from 'react';
import Link from 'next/link';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Skeleton } from '@/components/ui/Skeleton';
import { LiveBadge } from '@/components/mf/funddetail/parts';
import { REGIME_DISPLAY, REGIME_COLOR } from '@/components/mood/MoodGauge';
import { useLeaderboard, usePortfolioHoldingsIsins } from '@/features/mf/api';
import { useMe } from '@/features/auth/api';
import { useMoodCurrent } from '@/features/mood/api';
import { PortfolioIsinsContext } from '@/components/mf/leaderboard/ui';
import {
  Anchor, HeroSection, CatNav, DiscoverSection, Top100Section, ChampionsSection,
  PerformanceSection, SipSection, RiskSection, ValueSection, IntelligenceSection,
  MarketSection, FlowsSection, ImprovedSection, ManagersSection, AmcSection,
  AiInsightsSection, FaqSection, FilterSheet, TrendingSection, type T100Filters,
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
  // I4 — Top-100 client-side filters; owned here because the mobile FilterSheet
  // (page-level toolbar) and the Top100Section table both read/write them.
  const [t100Filters, setT100Filters] = React.useState<T100Filters>({});

  // Real leaderboard feed (docs/features/leaderboard-data-backend.md §5/§6). One
  // request feeds every board below; a board absent from `boards` (endpoint not
  // deployed yet, or that board just isn't wired) leaves its section on the
  // untouched illustrative sample + Preview chip — never fabricated.
  const lb = useLeaderboard();
  const boards = lb.data?.boards;
  const hero = lb.data?.hero ?? undefined;

  // V4 — "In your portfolio" pills: the logged-in user's holding ISINs, fetched
  // only when authed (MaybeShell page — useMe resolves the auth state). Logged
  // out / no portfolio / consent absent all collapse to the empty set: no pills.
  const { data: me } = useMe();
  const { data: pfHoldings } = usePortfolioHoldingsIsins(!!me);
  const pfIsins = React.useMemo(() => new Set(pfHoldings?.isins ?? []), [pfHoldings]);

  // DMMI hero tile — regime WORD + band only, reusing the same mood hook and
  // word/colour maps as Fund Explorer's DmmiSection (never a number).
  const mood = useMoodCurrent();
  const moodHealthy = !!mood.data && mood.data.data_quality !== 'unavailable' &&
    mood.data.regime !== 'data_unavailable' && mood.data.regime !== 'insufficient_data';
  const moodWord = moodHealthy ? REGIME_DISPLAY[mood.data!.regime] : undefined;
  const moodBand = moodHealthy ? mood.data!.confidence_band : undefined;
  const moodColor = moodHealthy ? REGIME_COLOR[mood.data!.regime] : undefined;

  const perfLive = !!(boards?.perf_1y && boards?.perf_3y && boards?.perf_5y && boards?.wealth_creator);
  const riskLive = !!(boards?.risk_lowest && boards?.risk_drawdown && boards?.risk_sharpe && boards?.risk_recovery);
  const valueLive = !!(boards?.value_ter && boards?.value_efficiency && boards?.value_index);
  const improvedLive = !!(boards?.movers_up && boards?.label_upgrades && boards?.top10_entries);
  const intelLive = !!(boards?.hidden_gems && boards?.future_leaders && boards?.momentum && boards?.quality && boards?.ai_spotlight);
  const managersInfo = boards?.manager_facts ? 'the people behind the returns — covered schemes only' : 'the people behind the returns';

  return (
    <PortfolioIsinsContext.Provider value={pfIsins}>
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
      <HeroSection hero={hero} moodWord={moodWord} moodBand={moodBand} moodColor={moodColor} />

      {/* Sticky category nav */}
      <CatNav />

      {/* S2 — Discover */}
      <Anchor>
        <SectionHeader index="01" title="Discover" info="jump to what you’re looking for" />
        <DiscoverSection />
      </Anchor>

      {/* S3 — Top 100 */}
      <Anchor id="top100">
        <SectionHeader index="02" title="DhanRadar Top 100" tag="Flagship" info="the best funds in India, ranked" badge={boards?.top100 ? <LiveBadge /> : undefined} />
        <Top100Section live={boards?.top100?.rows} filters={t100Filters} />
      </Anchor>

      {/* S4 — Category Champions */}
      <Anchor id="champions">
        <SectionHeader index="03" title="Category Champions" info="the best fund in every category" badge={boards?.champions ? <LiveBadge /> : undefined} />
        <ChampionsSection live={boards?.champions?.rows} />
      </Anchor>

      {/* S5 — Performance (all 4 rails live → section badge, else per-rail chip; see PerformanceSection) */}
      <Anchor id="performance">
        <SectionHeader index="04" title="Performance Leaderboards" info="highest returns by period" badge={perfLive ? <LiveBadge /> : undefined} />
        <PerformanceSection boards={boards} />
      </Anchor>

      {/* S6 — SIP (mixed coverage: per-rail chip, see SipSection) */}
      <Anchor id="sip">
        <SectionHeader index="05" title="SIP Leaderboards" info="best for monthly investors" />
        <SipSection boards={boards} />
      </Anchor>

      {/* S7 — Risk (all 4 rails live → section badge, else per-rail chip; see RiskSection) */}
      <Anchor id="risk">
        <SectionHeader index="06" title="Risk Leaderboards" info="safest & steadiest funds" badge={riskLive ? <LiveBadge /> : undefined} />
        <RiskSection boards={boards} />
      </Anchor>

      {/* S8 — Value (all 3 rails live → section badge) */}
      <Anchor id="value">
        <SectionHeader index="07" title="Value Leaderboards" info="best return for the cost" badge={valueLive ? <LiveBadge /> : undefined} />
        <ValueSection boards={boards} />
      </Anchor>

      {/* S9 — Intelligence (all 5 rails live → section badge, else per-rail chip; see IntelligenceSection) */}
      <Anchor id="intelligence">
        <SectionHeader index="08" title="DhanRadar Intelligence" tag="Proprietary" info="our unique rankings" badge={intelLive ? <LiveBadge /> : undefined} />
        <IntelligenceSection boards={boards} />
      </Anchor>

      {/* S10 — Current Market */}
      <Anchor id="market">
        <SectionHeader index="09" title="Current Market Leaders" tag="DMMI" info="what fits today’s market" />
        <MarketSection regime={moodHealthy ? mood.data!.regime : undefined} moodWord={moodWord} moodBand={moodBand} moodColor={moodColor} />
      </Anchor>

      {/* S11 — Fund Flows (mixed coverage: per-rail chip, see FlowsSection) */}
      <Anchor id="flows">
        <SectionHeader index="10" title="Fund Flow Leaders" info="where the money is moving" />
        <FlowsSection boards={boards} />
      </Anchor>

      {/* S12 — Most Improved (movers_up + label_upgrades + top10_entries live → section badge) */}
      <Anchor id="improved">
        <SectionHeader index="11" title="Most Improved & Future Stars" info="funds on the rise" badge={improvedLive ? <LiveBadge /> : undefined} />
        <ImprovedSection boards={boards} />
      </Anchor>

      {/* S15 (Trusted Ratings) removed — founder decision 2026-08-16: third-party
          ratings not required. D-3 (same day): Managers + AMCs are reference
          material, moved to the end after AI Insights; FAQ stays last. */}

      {/* Trending (mixed coverage: per-rail chip, see TrendingSection) */}
      <Anchor id="trending">
        <SectionHeader index="12" title="Trending Now" info="biggest movers this week" />
        <TrendingSection boards={boards} />
      </Anchor>

      {/* AI Insights */}
      <Anchor>
        <SectionHeader index="13" title="AI Insights" tag="DhanRadar AI" badge={boards?.ai_insights ? <LiveBadge /> : undefined} />
        <AiInsightsSection live={boards?.ai_insights?.rows} />
      </Anchor>

      {/* Managers */}
      <Anchor id="managers">
        <SectionHeader index="14" title="Best Fund Managers" info={managersInfo} badge={boards?.manager_facts ? <LiveBadge /> : undefined} />
        <ManagersSection live={boards?.manager_facts?.rows} />
      </Anchor>

      {/* AMCs */}
      <Anchor id="amc">
        <SectionHeader index="15" title="Best AMCs" info="the most trusted fund houses" badge={boards?.amc_facts ? <LiveBadge /> : undefined} />
        <AmcSection live={boards?.amc_facts?.rows} />
      </Anchor>

      {/* FAQ */}
      <Anchor>
        <SectionHeader index="16" title="Rankings FAQ" />
        <FaqSection />
      </Anchor>

      {/* Disclosure (educational boundary) */}
      <div className="mt-7 rounded-2xl border border-line bg-surface-2 p-4">
        <DisclosureBundle notAdvice="For education only — not investment advice. These rankings, scores and the figures shown (some illustrative previews while data feeds are built) are educational signals derived from factual data, not recommendations to buy, sell, or hold any fund. Mutual fund investments are subject to market risks; read all scheme-related documents carefully. Past performance does not indicate future returns." />
      </div>

      <FilterSheet open={filterOpen} onClose={() => setFilterOpen(false)} value={t100Filters} onChange={setT100Filters} />
    </div>
    </PortfolioIsinsContext.Provider>
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
