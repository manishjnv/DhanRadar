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
import { MaybeShell } from '@/components/ui/MaybeShell';
import { FundExplorerTable } from '@/components/mf/FundExplorerTable';
import { useFundCategories, useFundExplorer } from '@/features/mf/api';
import { cn } from '@/lib/cn';
import type { SortKey } from '@/components/mf/FundExplorerTable';

type PlanFilter   = 'all' | 'direct' | 'regular';
type OptionFilter = 'all' | 'growth' | 'idcw';

const PER_PAGE_OPTIONS: { value: number; label: string }[] = [
  { value: 20,  label: '20'  },
  { value: 50,  label: '50'  },
  { value: 100, label: '100' },
  { value: 500, label: 'All' },
];

// ---------------------------------------------------------------------------
// Category dropdown — native <select> with chevron overlay
// ---------------------------------------------------------------------------

function CategoryDropdown({
  categories,
  activeKey,
  onSelect,
}: {
  categories: { key: string; display_name: string; fund_count: number }[];
  activeKey: string;
  onSelect: (key: string) => void;
}) {
  return (
    <div className="relative inline-flex items-center gap-2">
      <span className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted shrink-0">
        Category
      </span>
      <div className="relative">
        <select
          value={activeKey}
          onChange={(e) => onSelect(e.target.value)}
          className={cn(
            'h-[34px] rounded-lg border border-line bg-surface-2',
            'pl-3 pr-8 text-small text-ink font-medium cursor-pointer appearance-none',
            'focus-visible:outline-none focus-visible:border-royal focus-visible:ring-2 focus-visible:ring-royal/40',
            'transition-colors max-w-[320px]',
          )}
        >
          {categories.map((cat) => (
            <option key={cat.key} value={cat.key}>
              {cat.display_name} ({cat.fund_count})
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-muted" aria-hidden="true">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
            <path d="M5 7L0.5 2.5h9L5 7z" />
          </svg>
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter chip group — plan type + option type (client-side filter)
// ---------------------------------------------------------------------------

const PLAN_OPTIONS: { key: PlanFilter; label: string }[] = [
  { key: 'all',     label: 'All'     },
  { key: 'direct',  label: 'Direct'  },
  { key: 'regular', label: 'Regular' },
];
const OPTION_OPTIONS: { key: OptionFilter; label: string }[] = [
  { key: 'all',    label: 'All'    },
  { key: 'growth', label: 'Growth' },
  { key: 'idcw',   label: 'IDCW'   },
];

function FilterChips({
  planFilter,
  optionFilter,
  onPlanFilter,
  onOptionFilter,
}: {
  planFilter: PlanFilter;
  optionFilter: OptionFilter;
  onPlanFilter: (k: PlanFilter) => void;
  onOptionFilter: (k: OptionFilter) => void;
}) {
  return (
    <div className="flex items-center gap-4 flex-wrap">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted shrink-0">
          Plan
        </span>
        <div className="flex gap-1">
          {PLAN_OPTIONS.map((o) => (
            <button
              key={o.key}
              type="button"
              onClick={() => onPlanFilter(o.key)}
              aria-pressed={planFilter === o.key}
              className={cn(
                'inline-flex items-center px-2.5 py-1 rounded-full text-caption font-medium border transition-colors whitespace-nowrap',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                planFilter === o.key
                  ? 'bg-ink text-bg border-ink'
                  : 'bg-surface-2 text-ink-secondary border-line hover:text-ink',
              )}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted shrink-0">
          Option
        </span>
        <div className="flex gap-1">
          {OPTION_OPTIONS.map((o) => (
            <button
              key={o.key}
              type="button"
              onClick={() => onOptionFilter(o.key)}
              aria-pressed={optionFilter === o.key}
              className={cn(
                'inline-flex items-center px-2.5 py-1 rounded-full text-caption font-medium border transition-colors whitespace-nowrap',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                optionFilter === o.key
                  ? 'bg-ink text-bg border-ink'
                  : 'bg-surface-2 text-ink-secondary border-line hover:text-ink',
              )}
            >
              {o.label}
            </button>
          ))}
        </div>
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
    <div className="relative w-full">
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
          'focus-visible:outline-none focus-visible:border-royal focus-visible:ring-2 focus-visible:ring-royal/40',
          'transition-colors',
        )}
        data-testid="fund-search"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-page selector — rendered in the top pagination bar left slot
// ---------------------------------------------------------------------------

function PerPageSelect({
  perPage,
  onChange,
}: {
  perPage: number;
  onChange: (n: number) => void;
}) {
  return (
    <div className="relative inline-flex items-center gap-2">
      <span className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted shrink-0 whitespace-nowrap">
        Show
      </span>
      <div className="relative">
        <select
          value={perPage}
          onChange={(e) => onChange(Number(e.target.value))}
          aria-label="Funds per page"
          className={cn(
            'h-[28px] rounded-full border border-line bg-surface-2',
            'pl-3 pr-7 text-caption text-ink font-medium cursor-pointer appearance-none',
            'focus-visible:outline-none focus-visible:border-royal focus-visible:ring-2 focus-visible:ring-royal/40',
            'transition-colors',
          )}
        >
          {PER_PAGE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-ink-muted" aria-hidden="true">
          <svg width="8" height="8" viewBox="0 0 10 10" fill="currentColor">
            <path d="M5 7L0.5 2.5h9L5 7z" />
          </svg>
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pagination — .chip style buttons with smart ellipsis window.
// leftSlot: when provided, renders instead of the count text and the
// component renders even when totalPages <= 1 (top bar needs PerPageSelect).
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
  leftSlot,
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
    <div className="flex items-center justify-between mt-2 gap-3 flex-wrap">
      {leftSlot ?? (
        <p className="font-mono text-caption text-ink-muted">
          {start}–{end} of {total} funds
        </p>
      )}
      {totalPages > 1 && (
        <div className="flex items-center gap-1">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
            className="inline-flex items-center px-2.5 py-1 rounded-full text-caption font-medium border border-line bg-surface-2 text-ink-secondary hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
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
            className="inline-flex items-center px-2.5 py-1 rounded-full text-caption font-medium border border-line bg-surface-2 text-ink-secondary hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
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

  const [activeCategory, setActiveCategory] = React.useState<string>('');
  const [sort, setSort]                     = React.useState<SortKey>('rank');
  const [sortDir, setSortDir]               = React.useState<'asc' | 'desc'>('desc');
  const [page, setPage]                     = React.useState(1);
  const [search, setSearch]                 = React.useState('');
  const [planFilter, setPlanFilter]         = React.useState<PlanFilter>('all');
  const [optionFilter, setOptionFilter]     = React.useState<OptionFilter>('all');
  const [perPage, setPerPage]               = React.useState(20);

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

  const { data, isLoading: fundsLoading, isError } = useFundExplorer({
    category: activeCategory,
    sort,
    sortDir,
    planType:   planFilter   !== 'all' ? planFilter   : undefined,
    optionType: optionFilter !== 'all' ? optionFilter : undefined,
    page,
    limit: perPage,
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

  // --- Loading skeleton ---
  if (catsLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-[34px] w-64 rounded-lg" />
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
    <div className="flex flex-col gap-3">
      {/* Row 1: Category selector + search (right-aligned) + fund count */}
      <div className="flex items-center gap-3 flex-wrap">
        <CategoryDropdown
          categories={catData.categories}
          activeKey={activeCategory}
          onSelect={handleCategoryChange}
        />
        <div className="ml-auto flex items-center gap-3">
          {data && (
            <span className="font-mono text-caption text-ink-muted whitespace-nowrap shrink-0">
              {data.total} funds
            </span>
          )}
          <div className="w-[200px]">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} />
          </div>
        </div>
      </div>

      {/* Row 2: Plan / Option type filters */}
      <FilterChips
        planFilter={planFilter}
        optionFilter={optionFilter}
        onPlanFilter={(k) => { setPlanFilter(k); setPage(1); }}
        onOptionFilter={(k) => { setOptionFilter(k); setPage(1); }}
      />

      {/* Top pagination — per-page selector on left, page buttons on right */}
      {data && (
        <Pagination
          page={page}
          total={data.total}
          limit={perPage}
          onPage={setPage}
          leftSlot={
            <PerPageSelect
              perPage={perPage}
              onChange={(n) => { setPerPage(n); setPage(1); }}
            />
          }
        />
      )}

      {/* Table / loading / error */}
      {fundsLoading ? (
        <div className="flex flex-col gap-2">
          {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}
        </div>
      ) : isError ? (
        <ErrorCard title="Could not load funds" message="Please try again in a moment." />
      ) : (
        <FundExplorerTable funds={filtered} activeSort={sort} sortDir={sortDir} onSort={handleSort} />
      )}

      {/* Bottom pagination — count on left, page buttons on right */}
      {data && (
        <Pagination page={page} total={data.total} limit={perPage} onPage={setPage} />
      )}

      {/* Disclosure bundle — non-neg #9: must accompany every label/AI surface */}
      {data && (
        <div className="rounded-lg border border-line bg-surface-2 p-4 mt-1">
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

function ExplorePageContent() {
  const searchParams = useSearchParams();
  const initialCategory = searchParams.get('category');

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="font-mono text-caption uppercase text-royal mb-1">
          Mutual Funds
        </p>
        <h1 className="text-h2 text-ink">Fund Explorer</h1>
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

export default function ExplorePage() {
  // useSearchParams must sit under a Suspense boundary now that this page is
  // public and statically prerendered (outside the (app) group it no longer
  // inherits the auth-guarded dynamic render).
  return (
    <MaybeShell maxWidth="wide">
      <React.Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
        <ExplorePageContent />
      </React.Suspense>
    </MaybeShell>
  );
}
