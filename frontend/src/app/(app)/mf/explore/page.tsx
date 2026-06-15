'use client';

export const dynamic = 'force-dynamic';

/**
 * Fund Explorer — /mf/explore
 *
 * Public browsable comparison of all mutual funds in a SEBI category, ranked
 * by the nightly market-wide ordinal score. Educational-only: no advisory CTAs,
 * no unified_score, no "invest/avoid" language. Compliance: non-neg #1, #2, #9.
 */

import * as React from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { FundExplorerTable } from '@/components/mf/FundExplorerTable';
import { useFundCategories, useFundExplorer } from '@/features/mf/api';
import { cn } from '@/lib/cn';
import type { SortKey } from '@/components/mf/FundExplorerTable';

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'rank',         label: 'Power Rank' },
  { key: 'return_1y',   label: '1Y Return' },
  { key: 'return_3y',   label: '3Y Return' },
  { key: 'max_drawdown', label: 'Drawdown' },
];

// ---------------------------------------------------------------------------
// Category tabs
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
    <div className="overflow-x-auto pb-1">
      <div className="flex gap-1 min-w-max">
        {categories.map((cat) => (
          <button
            key={cat.key}
            type="button"
            onClick={() => onSelect(cat.key)}
            className={cn(
              'px-3 py-1.5 rounded-full text-caption font-medium whitespace-nowrap transition-colors',
              activeKey === cat.key
                ? 'bg-royal text-white'
                : 'bg-surface-2 text-ink-secondary hover:text-ink',
            )}
          >
            {cat.display_name}
            <span className="ml-1 opacity-60">{cat.fund_count}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

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

  return (
    <div className="flex items-center justify-between mt-4">
      <p className="text-caption text-ink-muted">
        {(page - 1) * limit + 1}–{Math.min(page * limit, total)} of {total} funds
      </p>
      <div className="flex gap-1">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="px-3 py-1.5 rounded text-caption bg-surface-2 text-ink-secondary disabled:opacity-40"
        >
          ‹ Prev
        </button>
        {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
          const p = i + 1;
          return (
            <button
              key={p}
              type="button"
              onClick={() => onPage(p)}
              className={cn(
                'px-3 py-1.5 rounded text-caption',
                p === page
                  ? 'bg-royal text-white'
                  : 'bg-surface-2 text-ink-secondary hover:text-ink',
              )}
            >
              {p}
            </button>
          );
        })}
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => onPage(page + 1)}
          className="px-3 py-1.5 rounded text-caption bg-surface-2 text-ink-secondary disabled:opacity-40"
        >
          Next ›
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Explorer body
// ---------------------------------------------------------------------------

function ExplorerBody({
  initialCategory,
}: {
  initialCategory: string | null;
}) {
  const router = useRouter();

  const { data: catData, isLoading: catsLoading } = useFundCategories();

  const [activeCategory, setActiveCategory] = React.useState<string>('');
  const [sort, setSort] = React.useState<SortKey>('rank');
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState('');

  // Set initial category once categories load
  React.useEffect(() => {
    if (!catData?.categories.length) return;
    if (activeCategory) return;  // already set
    const first = initialCategory ?? catData.categories[0].key;
    // Validate: only accept if it's in the known list
    const found = catData.categories.find((c) => c.key === first);
    setActiveCategory(found?.key ?? catData.categories[0].key);
  }, [catData, initialCategory, activeCategory]);

  // Reset page when category or sort changes
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

  // Client-side search filter within loaded page
  const filtered = React.useMemo(() => {
    if (!data?.funds) return [];
    const q = search.toLowerCase();
    if (!q) return data.funds;
    return data.funds.filter(
      (f) =>
        f.scheme_name.toLowerCase().includes(q) ||
        (f.amc_name?.toLowerCase().includes(q) ?? false),
    );
  }, [data?.funds, search]);

  if (catsLoading) {
    return (
      <div className="flex flex-col gap-4">
        <div className="flex gap-2">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-8 w-24 rounded-full" />)}
        </div>
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  if (!catData?.categories.length) {
    return (
      <div className="rounded-lg border border-line bg-surface-2 p-8 text-center">
        <p className="text-small font-medium text-ink">Market rankings not yet available</p>
        <p className="mt-1 text-caption text-ink-muted">
          Rankings are computed nightly. Check back tomorrow.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Category tabs */}
      <CategoryTabs
        categories={catData.categories}
        activeKey={activeCategory}
        onSelect={handleCategoryChange}
      />

      {/* Controls: search + sort + page info */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="Search funds by name or AMC…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-[200px] rounded-lg border border-line bg-surface-2 px-3 py-2 text-small text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40"
          data-testid="fund-search"
        />
        <div className="flex items-center gap-2">
          <span className="text-caption text-ink-muted">Sort:</span>
          <select
            value={sort}
            onChange={(e) => handleSort(e.target.value as SortKey)}
            className="rounded-lg border border-line bg-surface-2 px-2 py-2 text-small text-ink focus:outline-none focus:ring-2 focus:ring-royal/40"
            data-testid="sort-select"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.key} value={o.key}>{o.label}</option>
            ))}
          </select>
        </div>
        {data && (
          <p className="text-caption text-ink-muted ml-auto">
            {data.total} funds in this category
          </p>
        )}
      </div>

      {/* Table */}
      {fundsLoading ? (
        <div className="flex flex-col gap-2">
          {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-12 rounded" />)}
        </div>
      ) : isError ? (
        <ErrorCard title="Could not load funds" message="Please try again." />
      ) : (
        <FundExplorerTable funds={filtered} activeSort={sort} onSort={handleSort} />
      )}

      {/* Pagination */}
      {data && (
        <Pagination
          page={page}
          total={data.total}
          limit={data.limit}
          onPage={setPage}
        />
      )}

      {/* Disclosure */}
      {data && (
        <div className="rounded-lg border border-line bg-surface-2 p-4 mt-2">
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
        <h1 className="text-h2 font-medium text-ink">Fund Explorer</h1>
        <p className="mt-1 text-small text-ink-secondary">
          Compare mutual funds by rank, assessment, and returns — educational analysis only
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
