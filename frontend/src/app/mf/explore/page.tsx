'use client';

/**
 * Fund Explorer — /mf/explore  (V4 redesign)
 *
 * Public browsable comparison of all mutual funds in a SEBI category, ranked by
 * the nightly market-wide ordinal score. Educational-only: no advisory CTAs, no
 * unified_score, no "invest/avoid" language. Compliance: non-neg #1, #2, #9.
 *
 * V4 layout, made compliant: premium hero, smart search, quick-sort chips,
 * advanced filters, table⇄card explorer, category leaders + market mood (real
 * data), and honest "in development" states for sections with no data source.
 * All data fetching / sort / filter / pagination logic is unchanged from main.
 *
 * Public route (outside the (app) group): wrapped in MaybeShell + a Suspense
 * boundary for useSearchParams (static prerender).
 */

import * as React from 'react';
import { useSearchParams } from 'next/navigation';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { FundExplorerTable } from '@/components/mf/FundExplorerTable';
import { useFundCategories, useFundExplorer } from '@/features/mf/api';
import { useMoodCurrent } from '@/features/mood/api';
import { formatCategoryLabel } from '@/features/mf/explorer-format';
import { cn } from '@/lib/cn';
import type { SortKey } from '@/components/mf/FundExplorerTable';

import { ExploreHero } from '@/components/mf/explore/ExploreHero';
import { QuickChips } from '@/components/mf/explore/QuickChips';
import { AdvancedFilters } from '@/components/mf/explore/AdvancedFilters';
import { FundCardGrid } from '@/components/mf/explore/FundCardGrid';
import { CategoryLeaders } from '@/components/mf/explore/CategoryLeaders';
import { MarketMoodSection } from '@/components/mf/explore/MarketMoodSection';
import { DiscoveryFaq } from '@/components/mf/explore/DiscoveryFaq';
import { SectionHeader, Section } from '@/components/mf/explore/ExploreSection';

type PlanFilter   = 'all' | 'direct' | 'regular';
type OptionFilter = 'all' | 'growth' | 'idcw';
type ViewMode     = 'table' | 'cards';

const PER_PAGE_OPTIONS: { value: number; label: string }[] = [
  { value: 20,  label: '20'  },
  { value: 50,  label: '50'  },
  { value: 100, label: '100' },
  { value: 500, label: 'All' },
];

// "In development" sections — V4 sections with no public data source yet.
const PENDING_SECTIONS: { title: string; desc: string; icon: string }[] = [
  { title: 'AI Discovery',  desc: 'Funds improving or losing rank, surfaced automatically.', icon: '⚡' },
  { title: 'Fund Flow',     desc: 'Where money is moving — inflows and outflows by fund.',   icon: '🐋' },
  { title: 'Momentum',      desc: 'Rank changes over 30 days, 90 days and a year.',          icon: '📈' },
  { title: 'Consistency',   desc: 'The most reliable performers across market cycles.',      icon: '🎯' },
  { title: 'Low-Cost',      desc: 'Best value funds by expense ratio.',                      icon: '💸' },
  { title: 'AI Insights',   desc: 'Plain-language market observations, refreshed daily.',    icon: '🧠' },
];

// ---------------------------------------------------------------------------
// Category dropdown — native <select> with chevron overlay (alpha-sorted labels)
// ---------------------------------------------------------------------------

function CategoryDropdown({
  categories, activeKey, onSelect,
}: {
  categories: { key: string; display_name: string; fund_count: number }[];
  activeKey: string;
  onSelect: (key: string) => void;
}) {
  const sorted = React.useMemo(
    () =>
      [...categories].sort((a, b) =>
        formatCategoryLabel(a.display_name).localeCompare(formatCategoryLabel(b.display_name)),
      ),
    [categories],
  );
  return (
    <div className="relative inline-flex items-center gap-2">
      <span className="font-mono text-[10px] uppercase tracking-[0.06em] font-medium text-ink-muted shrink-0">
        Category
      </span>
      <div className="relative">
        <select
          value={activeKey}
          onChange={(e) => onSelect(e.target.value)}
          className={cn(
            'h-[38px] rounded-lg border border-line bg-surface',
            'pl-3 pr-8 text-small text-ink font-medium cursor-pointer appearance-none',
            'focus-visible:outline-none focus-visible:border-royal focus-visible:ring-2 focus-visible:ring-royal/40',
            'transition-colors max-w-[280px]',
          )}
        >
          {sorted.map((cat) => (
            <option key={cat.key} value={cat.key}>
              {formatCategoryLabel(cat.display_name)} ({cat.fund_count})
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-muted" aria-hidden="true">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor"><path d="M5 7L0.5 2.5h9L5 7z" /></svg>
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Search input — left-inset icon; lg variant for the prominent smart search
// ---------------------------------------------------------------------------

function SearchInput({
  value, onChange, size = 'md',
}: {
  value: string;
  onChange: (v: string) => void;
  size?: 'md' | 'lg';
}) {
  return (
    <div className="relative w-full">
      <span className={cn('absolute top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none', size === 'lg' ? 'left-4' : 'left-3')}>
        <svg width={size === 'lg' ? 18 : 14} height={size === 'lg' ? 18 : 14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="11" cy="11" r="7" /><path d="M16 16L21 21" />
        </svg>
      </span>
      <input
        type="search"
        placeholder={size === 'lg' ? 'Search funds by name or AMC…' : 'Search funds…'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          'w-full rounded-lg border border-line bg-surface text-ink placeholder:text-ink-muted',
          'focus-visible:outline-none focus-visible:border-royal focus-visible:ring-2 focus-visible:ring-royal/40 transition-colors',
          size === 'lg' ? 'h-[52px] pl-12 pr-4 text-body shadow-sm' : 'h-[38px] pl-9 pr-3 text-small',
        )}
        data-testid="fund-search"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-page selector
// ---------------------------------------------------------------------------

function PerPageSelect({ perPage, onChange }: { perPage: number; onChange: (n: number) => void }) {
  return (
    <div className="relative inline-flex items-center gap-2">
      <span className="font-mono text-[10px] uppercase tracking-[0.06em] font-medium text-ink-muted shrink-0 whitespace-nowrap">Show</span>
      <div className="relative">
        <select
          value={perPage}
          onChange={(e) => onChange(Number(e.target.value))}
          aria-label="Funds per page"
          className={cn(
            'h-[30px] rounded-full border border-line bg-surface',
            'pl-3 pr-7 text-caption text-ink font-medium cursor-pointer appearance-none',
            'focus-visible:outline-none focus-visible:border-royal focus-visible:ring-2 focus-visible:ring-royal/40 transition-colors',
          )}
        >
          {PER_PAGE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-ink-muted" aria-hidden="true">
          <svg width="8" height="8" viewBox="0 0 10 10" fill="currentColor"><path d="M5 7L0.5 2.5h9L5 7z" /></svg>
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// View toggle — Table / Cards segmented control
// ---------------------------------------------------------------------------

function ViewToggle({ view, onChange }: { view: ViewMode; onChange: (v: ViewMode) => void }) {
  const items: { key: ViewMode; label: string; icon: React.ReactNode }[] = [
    { key: 'table', label: 'Table', icon: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18M3 12h18M3 18h18" /></svg> },
    { key: 'cards', label: 'Cards', icon: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /></svg> },
  ];
  return (
    <div className="inline-flex rounded-lg border border-line bg-surface-2 p-0.5" role="group" aria-label="View mode">
      {items.map((it) => (
        <button
          key={it.key}
          type="button"
          onClick={() => onChange(it.key)}
          aria-pressed={view === it.key}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-small font-medium transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
            view === it.key ? 'bg-surface text-ink shadow-sm' : 'text-ink-muted hover:text-ink',
          )}
        >
          {it.icon}{it.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pagination — chip-style buttons with smart ellipsis window.
// ---------------------------------------------------------------------------

function getPageWindow(current: number, total: number): (number | '…')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | '…')[] = [1];
  if (current > 3) pages.push('…');
  for (let p = Math.max(2, current - 1); p <= Math.min(total - 1, current + 1); p++) pages.push(p);
  if (current < total - 2) pages.push('…');
  pages.push(total);
  return pages;
}

function Pagination({
  page, total, limit, onPage, leftSlot,
}: {
  page: number;
  total: number;
  limit: number;
  onPage: (p: number) => void;
  leftSlot?: React.ReactNode;
}) {
  const totalPages = Math.ceil(total / limit);
  if (totalPages <= 1 && !leftSlot) return null;

  const pageWindow = getPageWindow(page, totalPages);
  const start = (page - 1) * limit + 1;
  const end = Math.min(page * limit, total);

  return (
    <div className="flex items-center justify-between mt-3 gap-3 flex-wrap">
      {leftSlot ?? (
        <p className="font-mono text-caption text-ink-muted">{start}–{end} of {total} funds</p>
      )}
      {totalPages > 1 && (
        <div className="flex items-center gap-1">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
            className="inline-flex items-center px-2.5 py-1 rounded-full text-caption font-medium border border-line bg-surface text-ink-secondary hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
          >
            ‹ Prev
          </button>
          {pageWindow.map((p, i) =>
            p === '…' ? (
              <span key={`ellipsis-${i}`} className="px-1 text-caption text-ink-muted font-mono">…</span>
            ) : (
              <button
                key={p}
                type="button"
                onClick={() => onPage(p as number)}
                aria-label={`Page ${p}`}
                aria-current={p === page ? 'page' : undefined}
                className={cn(
                  'inline-flex items-center justify-center w-7 h-7 rounded-full text-caption font-medium border transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                  p === page ? 'bg-ink text-bg border-ink' : 'bg-surface text-ink-secondary border-line hover:text-ink',
                )}
              >
                {p}
              </button>
            )
          )}
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => onPage(page + 1)}
            className="inline-flex items-center px-2.5 py-1 rounded-full text-caption font-medium border border-line bg-surface text-ink-secondary hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
          >
            Next ›
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Explorer body — data orchestration layer
// ---------------------------------------------------------------------------

function ExplorerBody({ initialCategory }: { initialCategory: string | null }) {
  const { data: catData, isLoading: catsLoading } = useFundCategories();
  const { data: moodData } = useMoodCurrent();

  const [activeCategory, setActiveCategory] = React.useState<string>('');
  const [sort, setSort]                     = React.useState<SortKey>('rank');
  const [sortDir, setSortDir]               = React.useState<'asc' | 'desc'>('desc');
  const [page, setPage]                     = React.useState(1);
  const [search, setSearch]                 = React.useState('');
  const [planFilter, setPlanFilter]         = React.useState<PlanFilter>('all');
  const [optionFilter, setOptionFilter]     = React.useState<OptionFilter>('all');
  const [perPage, setPerPage]               = React.useState(20);
  const [view, setView]                     = React.useState<ViewMode>('table');

  // Set initial category once categories load — validate against known list
  React.useEffect(() => {
    if (!catData?.categories.length) return;
    if (activeCategory) return;
    const first = initialCategory ?? catData.categories[0].key;
    const found = catData.categories.find((c) => c.key === first);
    setActiveCategory(found?.key ?? catData.categories[0].key);
  }, [catData, initialCategory, activeCategory]);

  const handleCategoryChange = (key: string) => {
    setActiveCategory(key);
    setPage(1);
    setSearch('');
    setPlanFilter('all');
    setOptionFilter('all');
    setSortDir('desc');
  };

  const handleSort = (key: SortKey) => {
    if (key === sort) {
      setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    } else {
      setSort(key);
      setSortDir('desc');
    }
    setPage(1);
  };

  // Quick-chip handler: set sort + an explicit direction (no toggle).
  const handleQuickSort = (key: SortKey, dir: 'asc' | 'desc') => {
    setSort(key);
    setSortDir(dir);
    setPage(1);
  };

  const { data, isLoading: fundsLoading, isError } = useFundExplorer({
    category: activeCategory,
    sort,
    sortDir,
    planType:   planFilter   !== 'all' ? planFilter   : undefined,
    optionType: optionFilter !== 'all' ? optionFilter : undefined,
    page,
    limit: perPage,
  });

  // Category leaders — top-ranked funds in the selected category (existing endpoint).
  const { data: leadersData } = useFundExplorer({
    category: activeCategory,
    sort: 'rank',
    sortDir: 'asc',
    page: 1,
    limit: 3,
  });

  // Client-side filter: search only (plan/option are server-side for correct total/pagination)
  const filtered = React.useMemo(() => {
    if (!data?.funds) return [];
    const q = search.toLowerCase().trim();
    if (!q) return data.funds;
    return data.funds.filter(
      (f) =>
        f.scheme_name.toLowerCase().includes(q) ||
        (f.amc_name?.toLowerCase().includes(q) ?? false),
    );
  }, [data?.funds, search]);

  const totalRanked = React.useMemo(
    () => catData?.categories.reduce((s, c) => s + c.fund_count, 0) ?? null,
    [catData],
  );
  const activeCategoryName = React.useMemo(() => {
    const c = catData?.categories.find((x) => x.key === activeCategory);
    return c ? formatCategoryLabel(c.display_name) : '';
  }, [catData, activeCategory]);

  // --- Loading skeleton (first paint, before categories resolve) ---
  if (catsLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-48 rounded-2xl" />
        <Skeleton className="h-[52px] rounded-lg" />
        <div className="flex flex-col gap-2">
          {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}
        </div>
      </div>
    );
  }

  // --- Empty state (nightly task not yet run) ---
  if (!catData?.categories.length) {
    return (
      <div className="flex flex-col gap-7">
        <ExploreHero totalFunds={null} categoryCount={null} moodRegime={moodData?.regime ?? null} />
        <div className="rounded-xl border border-line bg-surface-2 p-10 text-center">
          <div className="text-2xl mb-3" aria-hidden="true">📊</div>
          <p className="text-small font-medium text-ink">Market rankings not yet available</p>
          <p className="mt-1 text-caption text-ink-muted">Rankings are computed nightly — check back tomorrow.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      {/* Hero */}
      <ExploreHero
        totalFunds={totalRanked}
        categoryCount={catData.categories.length}
        moodRegime={moodData?.regime ?? null}
      />

      {/* Smart search */}
      <Section>
        <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} size="lg" />
      </Section>

      {/* Quick discovery + category + filters */}
      <Section>
        <SectionHeader index="01" title="Quick Discovery" info="One-click presets" />
        <div className="flex items-center gap-3 flex-wrap mb-3">
          <CategoryDropdown categories={catData.categories} activeKey={activeCategory} onSelect={handleCategoryChange} />
          {data && (
            <span className="font-mono text-caption text-ink-muted whitespace-nowrap">{data.total} funds</span>
          )}
        </div>
        <QuickChips
          sort={sort}
          sortDir={sortDir}
          planFilter={planFilter}
          optionFilter={optionFilter}
          onSort={handleQuickSort}
          onPlan={(k) => { setPlanFilter(k); setPage(1); }}
          onOption={(k) => { setOptionFilter(k); setPage(1); }}
        />
        <div className="mt-3">
          <AdvancedFilters
            planFilter={planFilter}
            optionFilter={optionFilter}
            onPlan={(k) => { setPlanFilter(k); setPage(1); }}
            onOption={(k) => { setOptionFilter(k); setPage(1); }}
          />
        </div>
      </Section>

      {/* Fund Explorer — table / cards */}
      <Section>
        <SectionHeader index="02" title="Fund Explorer" info={data ? `${activeCategoryName} · ${data.total} funds` : undefined} />
        <div className="flex items-center gap-3 flex-wrap mb-3">
          <ViewToggle view={view} onChange={setView} />
          <div className="ml-auto"><PerPageSelect perPage={perPage} onChange={(n) => { setPerPage(n); setPage(1); }} /></div>
        </div>

        {fundsLoading ? (
          <div className="flex flex-col gap-2">
            {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-14 rounded-lg" />)}
          </div>
        ) : isError ? (
          <ErrorCard title="Could not load funds" message="Please try again in a moment." />
        ) : view === 'table' ? (
          <FundExplorerTable funds={filtered} activeSort={sort} sortDir={sortDir} onSort={handleSort} />
        ) : (
          <FundCardGrid funds={filtered} />
        )}

        {data && <Pagination page={page} total={data.total} limit={perPage} onPage={setPage} />}

        {/* Disclosure bundle — non-neg #9 */}
        {data && (
          <div className="rounded-lg border border-line bg-surface-2 p-4 mt-3">
            <DisclosureBundle
              disclosure={data.disclosure || undefined}
              notAdvice={data.not_advice || 'For education only — not investment advice.'}
            />
          </div>
        )}
      </Section>

      {/* Category leaders */}
      {leadersData?.funds?.length ? (
        <Section>
          <SectionHeader index="03" title="Top Ranked" info={activeCategoryName} />
          <CategoryLeaders leaders={leadersData.funds} categoryName={activeCategoryName} />
        </Section>
      ) : null}

      {/* Market mood */}
      <Section>
        <SectionHeader index="04" title="Market Mood" tag="DhanRadar Mood" />
        <MarketMoodSection />
      </Section>

      {/* In-development sections (no public data source yet) */}
      <Section>
        <SectionHeader index="05" title="More Fund Intelligence" info="In development" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {PENDING_SECTIONS.map((s) => (
            <div key={s.title} className="rounded-xl border border-dashed border-line bg-surface-2/50 p-4">
              <div className="flex items-center gap-2 mb-1.5">
                <span aria-hidden="true">{s.icon}</span>
                <span className="text-small font-semibold text-ink">{s.title}</span>
              </div>
              <p className="text-caption text-ink-muted leading-relaxed">{s.desc}</p>
              <p className="mt-2 font-mono text-caption uppercase tracking-wide text-ink-muted">In development</p>
            </div>
          ))}
        </div>
      </Section>

      {/* FAQ */}
      <Section>
        <SectionHeader index="06" title="Discovery FAQ" />
        <DiscoveryFaq />
      </Section>

      {/* Standing educational disclaimer */}
      <p className="mt-8 text-center text-caption text-ink-muted max-w-2xl mx-auto leading-relaxed">
        DhanRadar is an educational research platform, not a SEBI-registered investment adviser.
        Mutual fund investments are subject to market risks; read all scheme-related documents carefully.
        Past performance does not guarantee future returns.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function ExplorePageContent() {
  const searchParams = useSearchParams();
  const initialCategory = searchParams.get('category');

  return (
    <div className="mx-auto w-full max-w-[1200px] px-4 sm:px-6 py-6">
      <ExplorerBody initialCategory={initialCategory} />
    </div>
  );
}

export default function ExplorePage() {
  // useSearchParams must sit under a Suspense boundary now that this page is
  // public and statically prerendered (outside the (app) group it no longer
  // inherits the auth-guarded dynamic render).
  return (
    <MaybeShell maxWidth="full">
      <React.Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
        <ExplorePageContent />
      </React.Suspense>
    </MaybeShell>
  );
}
