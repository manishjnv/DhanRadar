'use client';

/**
 * Fund Explorer — /mf/explore
 *
 * Public browsable comparison of all mutual funds in a SEBI category, ranked
 * by the nightly market-wide ordinal score. Educational-only: no advisory CTAs,
 * no unified_score, no "invest/avoid" language. Compliance: non-neg #1, #2, #9.
 *
 * Note: `export const dynamic` is silently ignored on Client Components —
 * data is fetched client-side via TanStack Query hooks, no build-time fetch.
 */

import * as React from 'react';
import { useSearchParams } from 'next/navigation';
import { Card, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { FundExplorerTable } from '@/components/mf/FundExplorerTable';
import { useFundCategories, useFundExplorer } from '@/features/mf/api';
import { cn } from '@/lib/cn';
import type { SortKey } from '@/components/mf/FundExplorerTable';

// ---------------------------------------------------------------------------
// Sort options — displayed as chip toggles (not a native <select>)
// ---------------------------------------------------------------------------

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'rank',         label: 'Power Rank' },
  { key: 'return_1y',   label: '1Y Return'  },
  { key: 'return_3y',   label: '3Y Return'  },
  { key: 'max_drawdown', label: 'Drawdown'   },
];

// ---------------------------------------------------------------------------
// Category tabs — .chip / .chip.active pattern from component library
// ---------------------------------------------------------------------------

function CategoryTabs({
  categories,
  activeKey,
  onSelect,
}: {
  categories: { key: string; display_name: string; fund_count: number }[];
  activeKey: string;
  onSelect: (key: string) => void;
}) {
  return (
    <div className="overflow-x-auto pb-1 -mx-1 px-1">
      <div className="flex gap-1.5 min-w-max">
        {categories.map((cat) => (
          <button
            key={cat.key}
            type="button"
            onClick={() => onSelect(cat.key)}
            className={cn(
              'inline-flex items-center gap-1 px-3 py-1.5 rounded-full whitespace-nowrap',
              'text-[12px] font-medium border transition-colors',
              activeKey === cat.key
                ? 'bg-ink text-bg border-ink'
                : 'bg-surface-2 text-ink-secondary border-line hover:text-ink',
            )}
          >
            {cat.display_name}
            <span className={cn(
              'font-mono text-[10px]',
              activeKey === cat.key ? 'text-bg/60' : 'text-ink-muted',
            )}>
              {cat.fund_count}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sort chip group — replaces native <select> with .chip toggle pattern
// ---------------------------------------------------------------------------

function SortChips({
  sort,
  onSort,
}: {
  sort: SortKey;
  onSort: (k: SortKey) => void;
}) {
  return (
    <div className="flex items-center gap-2 flex-wrap" data-testid="sort-select">
      <span className="font-mono text-[10px] uppercase tracking-[0.06em] font-semibold text-ink-muted shrink-0">
        Sort
      </span>
      <div className="flex gap-1 flex-wrap">
        {SORT_OPTIONS.map((o) => (
          <button
            key={o.key}
            type="button"
            onClick={() => onSort(o.key)}
            className={cn(
              'inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium border transition-colors whitespace-nowrap',
              sort === o.key
                ? 'bg-ink text-bg border-ink'
                : 'bg-surface-2 text-ink-secondary border-line hover:text-ink',
            )}
          >
            {o.label}
            {sort === o.key && <span className="ml-1 text-bg/70 text-[9px]">▴</span>}
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Search input — .search pattern: icon inset on the left
// ---------------------------------------------------------------------------

function SearchInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="relative flex-1 min-w-[180px]">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="11" cy="11" r="7" />
          <path d="M16 16L21 21" />
        </svg>
      </span>
      <input
        type="search"
        placeholder="Search funds by name or AMC…"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          'w-full h-[38px] rounded-lg border border-line bg-surface-2',
          'pl-9 pr-3 text-small text-ink placeholder:text-ink-muted',
          'focus:outline-none focus:border-royal focus:ring-2 focus:ring-royal/20',
          'transition-colors',
        )}
        data-testid="fund-search"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pagination — .chip style buttons with smart ellipsis window
// ---------------------------------------------------------------------------

function getPageWindow(current: number, total: number): (number | '…')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | '…')[] = [1];
  if (current > 3) pages.push('…');
  for (let p = Math.max(2, current - 1); p <= Math.min(total - 1, current + 1); p++) {
    pages.push(p);
  }
  if (current < total - 2) pages.push('…');
  pages.push(total);
  return pages;
}

function Pagination({
  page,
  total,
  limit,
  onPage,
}: {
  page: number;
  total: number;
  limit: number;
  onPage: (p: number) => void;
}) {
  const totalPages = Math.ceil(total / limit);
  if (totalPages <= 1) return null;

  const window = getPageWindow(page, totalPages);
  const start = (page - 1) * limit + 1;
  const end = Math.min(page * limit, total);

  return (
    <div className="flex items-center justify-between mt-2 gap-3 flex-wrap">
      <p className="font-mono text-[11px] text-ink-muted">
        {start}–{end} of {total} funds
      </p>
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium border border-line bg-surface-2 text-ink-secondary hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          ‹ Prev
        </button>

        {window.map((p, i) =>
          p === '…' ? (
            <span key={`ellipsis-${i}`} className="px-1 text-[11px] text-ink-muted font-mono">…</span>
          ) : (
            <button
              key={p}
              type="button"
              onClick={() => onPage(p as number)}
              className={cn(
                'inline-flex items-center justify-center w-7 h-7 rounded-full text-[11px] font-medium border transition-colors',
                p === page
                  ? 'bg-ink text-bg border-ink'
                  : 'bg-surface-2 text-ink-secondary border-line hover:text-ink',
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
          className="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium border border-line bg-surface-2 text-ink-secondary hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Next ›
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Explorer body — data orchestration layer
// ---------------------------------------------------------------------------

function ExplorerBody({ initialCategory }: { initialCategory: string | null }) {
  const { data: catData, isLoading: catsLoading } = useFundCategories();

  const [activeCategory, setActiveCategory] = React.useState<string>('');
  const [sort, setSort]                     = React.useState<SortKey>('rank');
  const [page, setPage]                     = React.useState(1);
  const [search, setSearch]                 = React.useState('');

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
  };
  const handleSort = (key: SortKey) => {
    setSort(key);
    setPage(1);
  };

  const { data, isLoading: fundsLoading, isError } = useFundExplorer({
    category: activeCategory,
    sort,
    page,
  });

  // Client-side search filter within the loaded page
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

  // --- Loading skeleton ---
  if (catsLoading) {
    return (
      <div className="flex flex-col gap-4">
        <div className="flex gap-2 overflow-hidden">
          {[...Array(7)].map((_, i) => (
            <Skeleton key={i} className="h-8 w-24 rounded-full shrink-0" />
          ))}
        </div>
        <Skeleton className="h-10 rounded-lg" />
        <div className="flex flex-col gap-2">
          {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}
        </div>
      </div>
    );
  }

  // --- Empty state (nightly task not yet run) ---
  if (!catData?.categories.length) {
    return (
      <div className="rounded-xl border border-line bg-surface-2 p-10 text-center">
        <div className="text-2xl mb-3">📊</div>
        <p className="text-small font-medium text-ink">Market rankings not yet available</p>
        <p className="mt-1 text-caption text-ink-muted">Rankings are computed nightly — check back tomorrow.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Category chip tabs */}
      <CategoryTabs
        categories={catData.categories}
        activeKey={activeCategory}
        onSelect={handleCategoryChange}
      />

      {/* Controls bar: search + sort chips + count */}
      <div className="flex flex-wrap items-center gap-3">
        <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} />
        <SortChips sort={sort} onSort={handleSort} />
        {data && (
          <span className="font-mono text-[11px] text-ink-muted ml-auto whitespace-nowrap">
            {data.total} funds
          </span>
        )}
      </div>

      {/* Table / loading rows / error */}
      {fundsLoading ? (
        <div className="flex flex-col gap-2">
          {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}
        </div>
      ) : isError ? (
        <ErrorCard title="Could not load funds" message="Please try again in a moment." />
      ) : (
        <FundExplorerTable funds={filtered} activeSort={sort} onSort={handleSort} />
      )}

      {/* Pagination */}
      {data && (
        <Pagination page={page} total={data.total} limit={data.limit} onPage={setPage} />
      )}

      {/* Disclosure bundle — non-neg #9: must accompany every label/AI surface */}
      {data && (
        <div className="rounded-xl border border-line bg-surface-2 p-4 mt-1">
          <DisclosureBundle
            disclosure={data.disclosure || undefined}
            notAdvice={data.not_advice || 'For education only — not investment advice.'}
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ExplorePage() {
  const searchParams = useSearchParams();
  const initialCategory = searchParams.get('category');

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="font-mono text-[10px] uppercase tracking-[0.14em] font-semibold text-royal mb-1">
          Mutual Funds
        </p>
        <h1 className="text-h2 font-medium text-ink">Fund Explorer</h1>
        <p className="mt-1 text-small text-ink-secondary">
          Compare funds by rank, assessment, and returns — educational analysis only
        </p>
      </div>

      <Card>
        <CardBody>
          <ExplorerBody initialCategory={initialCategory} />
        </CardBody>
      </Card>
    </div>
  );
}
