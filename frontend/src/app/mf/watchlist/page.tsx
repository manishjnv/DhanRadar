'use client';

/**
 * Watchlist Monitor — /mf/watchlist  (V1 + Wave 1/2 live rewire)
 *
 * Public educational destination for tracking a shortlist of mutual funds,
 * built 1:1 to the approved WatchlistPageV1 desktop + mobile mockups.
 *
 * WATCHLIST_LIVE_DATA_PLAN.md Wave 1 (2026-08-21): page state now derives from
 * the real saved list (`saved.length === 0` → EmptyHero; else dashboard). For a
 * signed-in caller with a non-empty watchlist, Hero KPIs / Filter&Sort / the
 * Funds grid / Category Leaders / Leaderboard / Statistics render the real
 * `GET /api/v1/mf/watchlist/cards` payload (tag="LIVE"). An anonymous visitor,
 * or a signed-in caller with an empty watchlist who opts into "View Sample
 * Watchlist", sees the full illustrative dashboard unchanged.
 *
 * Wave 2 (2026-08-21): What Changed / Similar Funds wire to the new batch
 * endpoints (gated on `showLive`, same convention as the cards payload — an
 * empty/disabled fetch renders the section's own honest empty state, never a
 * decorative sample). DMMI (public `useMoodCurrent`) and Recently Viewed (pure
 * localStorage) need no watchlist data at all and are always live. Performance
 * derives its "watchlist average" from the cards payload and its "category
 * average" from the cards' own `category_return_*_pct` fields (Wave 2 cards
 * extension) — no fabricated 5Y category figure, no benchmark row yet. Smart
 * Alerts is removed (folded into What Changed).
 *
 * Compliance bridges honoured:
 *   1. No raw DhanRadar composite score in DOM — BandRing/FundScoreCell +
 *      strength WORD only.
 *   2. Educational verdict / momentum labels only — no advisory verbs.
 */

import * as React from 'react';
import Link from 'next/link';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  AiCardsGrid, HeroSection, FilterSection, FundsSection,
  OpportunitiesSection, LeaderboardSection, StatsSection, DiscoverySection,
  FaqSection, EmptyHero, BenefitsGrid,
  CompareTray,
  LiveFilterSection, LiveFundsSection, LiveCategoryLeadersSection,
  LiveLeaderboardSection, LiveStatsSection,
  LiveChangedSection, LiveDmmiSection, LivePerfSection, LiveSimilarSection,
  LiveRecentlyViewedSection, LiveAiSection,
  sortWatchlistCards, watchlistCardMatchesSearch, computeCategoryLeaders,
  type LiveSortKey,
} from '@/components/mf/watchlist/sections';
import { AI_SUMMARY, INSIGHTS } from '@/components/mf/watchlist/sampleData';
import { useWatchlist, type WatchlistEntry } from '@/hooks/useWatchlist';
import { useRecentlyViewed } from '@/hooks/useRecentlyViewed';
import { useFundDetail, useWatchlistCards, useWatchlistChanges, useWatchlistSimilar, useWatchlistSummary } from '@/features/mf/api';
import { useMe } from '@/features/auth/api';
import { EDU_LABELS } from '@/lib/displayLabel';
import type { WatchlistCard } from '@/features/mf/types';

// Rich saved-fund card (anonymous/preview path) — real facts from fund.head;
// null facts are omitted, never fabricated. Label renders as the educational
// WORD only (non-neg #1/#2).
function WatchlistFundCard({ entry, onRemove }: { entry: WatchlistEntry; onRemove: () => void }) {
  const { data: head, isLoading } = useFundDetail(entry.isin);

  const displayName = head?.fund_name_short ?? head?.scheme_name ?? (entry.name || entry.isin);
  const category = head?.category ?? head?.sebi_category ?? entry.category;
  const labelWord = head?.verb_label ? EDU_LABELS[head.verb_label] : null;

  return (
    <div className="flex items-start justify-between gap-3 rounded-2xl border border-line bg-surface p-3.5">
      <div className="min-w-0">
        <Link href={`/mf/fund/${entry.isin}`} className="text-small font-semibold text-ink transition-colors hover:text-royal">{displayName}</Link>
        {category && <div className="text-caption text-ink-muted">{category}</div>}
        {isLoading && !head && <div className="text-caption text-ink-faint">loading facts…</div>}
        {head && (
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-ink-secondary">
            {head.nav_latest != null && (
              <span>NAV ₹{head.nav_latest.toFixed(2)}{head.nav_date ? ` (as of ${head.nav_date})` : ''}</span>
            )}
            {head.return_1y_pct != null && <span>1Y return {head.return_1y_pct.toFixed(1)}%</span>}
            {head.return_3y_pct != null && <span>3Y return {head.return_3y_pct.toFixed(1)}%</span>}
            {labelWord && <span>DhanRadar educational read: <span className="font-medium text-ink">{labelWord}</span></span>}
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={onRemove}
        className="shrink-0 rounded p-1 text-lg text-amber transition-opacity hover:opacity-70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
        aria-label={`Remove ${displayName} from watchlist`}
        title="Remove from watchlist"
      >
        ★
      </button>
    </div>
  );
}

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

function computeHeroStats(cards: WatchlistCard[]) {
  const bandCounts: Record<'high' | 'medium' | 'low', number> = { high: 0, medium: 0, low: 0 };
  let upToday = 0;
  let downToday = 0;
  const categories = new Set<string>();
  for (const c of cards) {
    if (c.confidence_band) bandCounts[c.confidence_band] += 1;
    if (c.nav_change_pct != null) {
      if (c.nav_change_pct > 0) upToday += 1;
      else if (c.nav_change_pct < 0) downToday += 1;
    }
    const category = c.category ?? c.sebi_category;
    if (category) categories.add(category);
  }
  return { fundsTracked: cards.length, upToday, downToday, bandCounts, categoriesCovered: categories.size };
}

function WatchlistView() {
  const [selected, setSelected] = React.useState<Set<number>>(() => new Set());
  const [previewSample, setPreviewSample] = React.useState(false);
  const [search, setSearch] = React.useState('');
  const [sort, setSort] = React.useState<LiveSortKey>('recent');

  const { data: me } = useMe();
  const isLoggedIn = !!me;
  // Real saved funds — localStorage (anonymous) or mf.mf_watchlist_items (logged in).
  const { list: saved, toggle: toggleSaved } = useWatchlist();

  const showDashboard = saved.length > 0 || previewSample;
  const showLive = isLoggedIn && saved.length > 0;

  const { data: cardsResp, isLoading: cardsLoading } = useWatchlistCards(showLive);
  const cards = React.useMemo(() => cardsResp?.items ?? [], [cardsResp]);

  // Wave 2 — gated the same way as the cards payload (an anonymous or empty
  // watchlist renders each Live* section's own honest empty state below,
  // never a decorative sample).
  const { data: changesResp } = useWatchlistChanges(showLive);
  const { data: similarResp } = useWatchlistSimilar(showLive);
  // Wave 3 — governed AI-gateway summary/insights (S01 + S11). `LIVE` tag is
  // reserved for a genuine served result — while loading or when a real
  // attempt withheld output, the tag stays PREVIEW-ish but the CONTENT is the
  // honest loading/unavailable state, never the illustrative sample text.
  const { data: summaryResp, isLoading: summaryLoading } = useWatchlistSummary(showLive);
  const summaryItems = summaryResp?.summary_items ?? [];
  const insightItems = summaryResp?.insight_items ?? [];
  const summaryIsLive = showLive && !summaryLoading && summaryItems.length > 0;
  const insightsIsLive = showLive && !summaryLoading && insightItems.length > 0;
  const recentlyViewed = useRecentlyViewed();

  const visibleCards = React.useMemo(() => {
    const filtered = cards.filter((c) => watchlistCardMatchesSearch(c, search));
    return sortWatchlistCards(filtered, sort);
  }, [cards, search, sort]);

  const heroStats = React.useMemo(() => computeHeroStats(cards), [cards]);
  const categoryLeaders = React.useMemo(() => computeCategoryLeaders(cards), [cards]);

  const toggle = React.useCallback((i: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else if (next.size < 4) next.add(i);
      return next;
    });
  }, []);
  const clear = React.useCallback(() => setSelected(new Set()), []);
  const removeByIsin = React.useCallback(
    (isin: string) => toggleSaved({ isin, name: '', category: null }),
    [toggleSaved],
  );
  // Wave 2 — Similar Funds / Recently Viewed "+ Add" both toggle the same real
  // watchlist store (mirrors the fund-detail hero star).
  const addToWatchlist = React.useCallback(
    (isin: string, name: string) => toggleSaved({ isin, name, category: null }),
    [toggleSaved],
  );

  const selectedIsins = [...selected].map((i) => visibleCards[i]?.isin).filter((v): v is string => !!v);
  const compareChips = [...selected].map((i) => {
    const c = visibleCards[i];
    return c ? { key: c.isin, letter: (c.fund_name_short ?? c.scheme_name)[0]?.toUpperCase() ?? '?', color: '#1E5EFF' } : null;
  }).filter((v): v is { key: string; letter: string; color: string } => !!v);

  return (
    <div className="w-full pb-32">
      {/* Breadcrumb */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <nav className="flex flex-wrap items-center gap-1.5 text-caption text-ink-muted" aria-label="Breadcrumb">
          <Link href="/mf/explore" className="hover:text-ink">Watchlist</Link>
          <span className="text-ink-faint">›</span>
          <span className="font-semibold text-ink-secondary">{showDashboard ? 'My Watchlist' : 'Get Started'}</span>
          {showDashboard && (
            <>
              <span className="text-ink-faint">·</span>
              <span className="text-ink-faint">{saved.length} fund{saved.length === 1 ? '' : 's'} tracked</span>
            </>
          )}
        </nav>
      </div>

      {/* ── EMPTY STATE ──────────────────────────────────────────────────────── */}
      {!showDashboard && (
        <div className="flex flex-col gap-6">
          <EmptyHero onViewSample={() => setPreviewSample(true)} />
          <section>
            <SectionHeader title="What you'll get" />
            <BenefitsGrid />
          </section>
        </div>
      )}

      {/* ── DASHBOARD STATE ──────────────────────────────────────────────────── */}
      {showDashboard && (
        <div className="flex flex-col gap-6">
          <HeroSection stats={showLive ? heroStats : undefined} />

          <section>
            <SectionHeader index="01" title="AI Watchlist Summary" tag={summaryIsLive ? 'LIVE' : 'PREVIEW'} />
            {showLive ? (
              summaryLoading ? (
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                  <Skeleton className="h-20 rounded-2xl" />
                  <Skeleton className="h-20 rounded-2xl" />
                </div>
              ) : (
                <LiveAiSection items={summaryItems} disclosure={summaryResp?.disclosure} notAdvice={summaryResp?.not_advice} />
              )
            ) : (
              <AiCardsGrid items={AI_SUMMARY} />
            )}
          </section>

          <section>
            <SectionHeader index="02" title="Filter & Sort" tag={showLive ? 'LIVE' : 'PREVIEW'}
              info={showLive ? `${visibleCards.length} of ${cards.length} funds` : 'Category · AMC · risk · strength · DMMI fit · momentum'} />
            {showLive
              ? <LiveFilterSection search={search} onSearchChange={setSearch} sort={sort} onSortChange={setSort} />
              : <FilterSection />}
          </section>

          <section>
            <SectionHeader index="03" title="Watchlist Funds" tag={showLive ? 'LIVE' : 'PREVIEW'}
              info={showLive ? `${saved.length} funds` : `${saved.length} funds · tap ⇄ to shortlist`} />
            {showLive ? (
              cardsLoading ? (
                <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
                  {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-72 rounded-2xl" />)}
                </div>
              ) : (
                <LiveFundsSection cards={visibleCards} selected={selected} onToggle={toggle} onRemove={removeByIsin} />
              )
            ) : (
              <>
                {/* Anonymous preview: real saved funds first (fund-detail hero star). */}
                {saved.length > 0 && (
                  <div className="mb-3">
                    <p className="mb-2 text-caption font-semibold text-ink-secondary">Your saved funds ({saved.length})</p>
                    <div className="flex flex-col gap-2">
                      {saved.map((e) => (
                        <WatchlistFundCard key={e.isin} entry={e} onRemove={() => toggleSaved(e)} />
                      ))}
                    </div>
                  </div>
                )}
                <FundsSection selected={selected} onToggle={toggle} />
              </>
            )}
          </section>

          <section>
            <SectionHeader index="04" title="What Changed" info="Since last week" tag="LIVE" />
            <LiveChangedSection items={changesResp?.items ?? []} />
          </section>

          <section>
            <SectionHeader index="05" title={showLive ? 'Category Leaders' : 'Best Opportunities'}
              info={showLive ? 'Top 1Y return in your watchlist, per category' : 'In your watchlist'} tag={showLive ? 'LIVE' : 'PREVIEW'} />
            {showLive ? <LiveCategoryLeadersSection leaders={categoryLeaders} /> : <OpportunitiesSection />}
          </section>

          <section>
            <SectionHeader index="06" title="DMMI Watchlist Analysis" tag="LIVE" />
            <LiveDmmiSection />
          </section>

          <section>
            <SectionHeader index="07" title="Watchlist Performance" info="vs category · benchmark coming" tag="LIVE" />
            <LivePerfSection cards={cards} />
          </section>

          <section>
            <SectionHeader index="08" title="Watchlist Leaderboard" info="Ranked by 1Y return" tag={showLive ? 'LIVE' : 'PREVIEW'} />
            {showLive ? <LiveLeaderboardSection cards={cards} /> : <LeaderboardSection />}
          </section>

          <section>
            <SectionHeader index="10" title="Similar Funds Worth Watching" tag="LIVE" />
            <LiveSimilarSection items={similarResp?.items ?? []} onAdd={addToWatchlist} />
          </section>

          <section>
            <SectionHeader index="11" title="Watchlist Insights" tag={insightsIsLive ? 'LIVE' : 'PREVIEW'} />
            {showLive ? (
              summaryLoading ? (
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                  <Skeleton className="h-20 rounded-2xl" />
                  <Skeleton className="h-20 rounded-2xl" />
                </div>
              ) : (
                <LiveAiSection items={insightItems} disclosure={summaryResp?.disclosure} notAdvice={summaryResp?.not_advice} />
              )
            ) : (
              <AiCardsGrid items={INSIGHTS} />
            )}
          </section>

          <section>
            <SectionHeader index="12" title="Watchlist Statistics" tag={showLive ? 'LIVE' : 'PREVIEW'} />
            {showLive ? <LiveStatsSection cards={cards} /> : <StatsSection />}
          </section>

          <section>
            <SectionHeader index="13" title="Discover More" info="Add to your watchlist" tag="PREVIEW" />
            <DiscoverySection />
          </section>

          <section>
            <SectionHeader index="14" title="Recently Viewed" tag="LIVE" />
            <LiveRecentlyViewedSection entries={recentlyViewed} onAdd={addToWatchlist} />
          </section>

          <section>
            <SectionHeader index="15" title="Watchlist FAQ" tag="PREVIEW" />
            <FaqSection />
          </section>

          <p className="mx-auto max-w-[880px] text-center text-caption text-ink-faint leading-relaxed">
            DhanRadar is a research &amp; analytics platform, not an investment advisor. Sections tagged PREVIEW show illustrative data. Mutual fund investments are subject to market risks; read all scheme-related documents carefully. Past performance does not guarantee future returns.
          </p>

          <div className="rounded-2xl border border-line bg-surface-2 p-4">
            <DisclosureBundle notAdvice="For education only — not investment advice. Sections tagged PREVIEW show illustrative preview data. Mutual fund investments are subject to market risks. Past performance does not indicate future returns." />
          </div>

          <CompareTray
            selected={selected}
            onClear={clear}
            chips={showLive ? compareChips : undefined}
            compareHref={showLive && selectedIsins.length > 0 ? `/mf/compare?isins=${selectedIsins.join(',')}` : undefined}
          />
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
