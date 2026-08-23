'use client';

/**
 * Fund Explorer — /mf/explore  (V4 redesign, full layout)
 *
 * Full V4 layout: hero (6 stats + 9 quick actions), smart search (+ tags),
 * quick-discovery (15 chips), advanced filters, AI discovery, fund explorer
 * (table ⇄ cards, REAL data), category leaderboards, DMMI, fund flow, momentum,
 * consistency, low-cost, beginner picks, AI feed, FAQ, floating shortlist.
 *
 * Real data: fund table/cards/categories (/mf/funds), market mood (/market/mood),
 * category leaders. Other sections render illustrative "preview" data so every
 * UI component shows now; data/functionality wired later (BLOCKERS B73–B78).
 *
 * Compliance (binding, overrides the V4 mockup): NO numeric score/grade/percentile
 * (band-driven ring only); NO advisory verbs (educational labels); "View" not
 * "Invest"; mood/DMMI show a regime WORD, never a number.
 *
 * Public route (outside (app)): MaybeShell + Suspense for useSearchParams.
 */

import * as React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { FundExplorerTable, ALL_COL_IDS, COL_LABELS } from '@/components/mf/FundExplorerTable';
import { useFundCategories, useFundExplorer, useFundSearch, useLeaderboard } from '@/features/mf/api';
import { useMoodCurrent } from '@/features/mood/api';
import { formatCategoryLabel } from '@/features/mf/explorer-format';
import { cn } from '@/lib/cn';
import type { SortKey, ColId } from '@/components/mf/FundExplorerTable';
import type { FundSearchItem } from '@/features/mf/types';

import { ExploreHero } from '@/components/mf/explore/ExploreHero';
import { QuickChips } from '@/components/mf/explore/QuickChips';
import { AdvancedFilters } from '@/components/mf/explore/AdvancedFilters';
import { FundCardGrid } from '@/components/mf/explore/FundCardGrid';
import { DiscoveryFaq } from '@/components/mf/explore/DiscoveryFaq';
import { MarketMoodSection } from '@/components/mf/explore/MarketMoodSection';
import { CategoryLeaders } from '@/components/mf/explore/CategoryLeaders';
import { Leaderboards } from '@/components/mf/explore/Leaderboards';
import { Momentum } from '@/components/mf/explore/Momentum';
import { ConsistencyTable, LowCostTable } from '@/components/mf/explore/LeaderTables';
import { BeginnerPicks } from '@/components/mf/explore/BeginnerPicks';
import { AiFeed } from '@/components/mf/explore/AiFeed';
import { Shortlist, useShortlist } from '@/components/mf/explore/Shortlist';
import { SectionHeader, Section } from '@/components/mf/explore/ExploreSection';
import { FundFlowSection } from '@/components/mf/explore/FundFlowSection';
import { SpotlightSignals } from '@/components/mf/explore/SpotlightSignals';
import { LiveBadge } from '@/components/mf/funddetail/parts';
import { QUICK_INTENTS, type QuickIntent } from '@/features/mf/quickIntents';

const TRY_INTENTS = QUICK_INTENTS.filter((q) => q.backing.kind === 'category');

type PlanFilter   = 'all' | 'direct' | 'regular';
type OptionFilter = 'all' | 'growth' | 'idcw';
type ViewMode     = 'table' | 'cards';

const PER_PAGE_OPTIONS = [
  { value: 20, label: '20' }, { value: 50, label: '50' }, { value: 100, label: '100' }, { value: 500, label: 'All' },
];
const PLAN_OPTIONS: { key: PlanFilter; label: string }[] = [
  { key: 'all', label: 'All' }, { key: 'direct', label: 'Direct' }, { key: 'regular', label: 'Regular' },
];
const OPTION_OPTIONS: { key: OptionFilter; label: string }[] = [
  { key: 'all', label: 'All' }, { key: 'growth', label: 'Growth' }, { key: 'idcw', label: 'IDCW' },
];

// ── small controls ─────────────────────────────────────────────────────────

function CategoryDropdown({ categories, activeKey, onSelect }: {
  categories: { key: string; display_name: string; fund_count: number }[]; activeKey: string; onSelect: (k: string) => void;
}) {
  const sorted = React.useMemo(
    () => [...categories].sort((a, b) => formatCategoryLabel(a.display_name).localeCompare(formatCategoryLabel(b.display_name))),
    [categories],
  );
  return (
    <div className="relative inline-flex items-center gap-2">
      <span className="font-mono text-[10px] uppercase tracking-[0.06em] font-medium text-ink-muted shrink-0">Category</span>
      <div className="relative">
        <select value={activeKey} onChange={(e) => onSelect(e.target.value)}
          className="h-[38px] rounded-lg border border-line bg-surface pl-3 pr-8 text-small text-ink font-medium cursor-pointer appearance-none focus-visible:outline-none focus-visible:border-royal focus-visible:ring-2 focus-visible:ring-royal/40 transition-colors max-w-[280px]">
          {sorted.map((c) => <option key={c.key} value={c.key}>{formatCategoryLabel(c.display_name)} ({c.fund_count})</option>)}
        </select>
        <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-muted" aria-hidden="true">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor"><path d="M5 7L0.5 2.5h9L5 7z" /></svg>
        </span>
      </div>
    </div>
  );
}

function PillGroup<T extends string>({ label, options, value, onChange }: {
  label: string; options: { key: T; label: string }[]; value: T; onChange: (k: T) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-[10px] uppercase tracking-[0.06em] font-medium text-ink-muted shrink-0">{label}</span>
      <div className="flex gap-1">
        {options.map((o) => (
          <button key={o.key} type="button" onClick={() => onChange(o.key)} aria-pressed={value === o.key}
            className={cn('inline-flex items-center px-2.5 py-1 rounded-full text-caption font-medium border transition-colors whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
              value === o.key ? 'bg-ink text-bg border-ink' : 'bg-surface-2 text-ink-secondary border-line hover:text-ink')}>
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── TypeaheadSearch ────────────────────────────────────────────────────────
// Calls GET /mf/search (debounced 300ms) and navigates to /mf/fund/{isin}.
// Also updates the client-side table name filter so typing text filters rows.

function TypeaheadSearch({ clientSearch, onClientSearch }: {
  clientSearch: string;
  onClientSearch: (v: string) => void;
}) {
  const router = useRouter();
  const [query, setQuery]       = React.useState(clientSearch);
  const [apiQuery, setApiQuery] = React.useState('');
  const [open, setOpen]         = React.useState(false);
  const debounceRef             = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef              = React.useRef<HTMLDivElement>(null);

  const { data: results } = useFundSearch(apiQuery);

  function handleChange(v: string) {
    setQuery(v);
    onClientSearch(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const trimmed = v.trim();
      setApiQuery(trimmed.length >= 2 ? trimmed : '');
      setOpen(trimmed.length >= 2);
    }, 300);
  }

  function handleSelect(item: FundSearchItem) {
    setOpen(false);
    setQuery('');
    onClientSearch('');
    setApiQuery('');
    router.push(`/mf/fund/${item.isin}`);
  }

  React.useEffect(() => {
    function handler(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={wrapperRef} className="relative w-full">
      <div className="relative w-full">
        <span className="absolute top-1/2 -translate-y-1/2 left-4 text-ink-muted pointer-events-none">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="M16 16L21 21" /></svg>
        </span>
        <input
          type="search"
          placeholder="Search fund, AMC, category…"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => apiQuery.length >= 2 && setOpen(true)}
          data-testid="fund-search"
          className="w-full rounded-lg border border-line bg-surface text-ink placeholder:text-ink-muted focus-visible:outline-none focus-visible:border-royal focus-visible:ring-2 focus-visible:ring-royal/40 transition-colors h-[56px] pl-12 pr-4 text-body shadow-sm"
        />
      </div>
      {open && results && results.length > 0 && (
        <div className="absolute z-20 left-0 right-0 mt-1 rounded-xl border border-line bg-surface shadow-lg overflow-hidden">
          {results.map((item) => (
            <button
              key={item.isin}
              type="button"
              onClick={() => handleSelect(item)}
              data-testid={`search-result-${item.isin}`}
              className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-2 transition-colors text-left focus-visible:outline-none focus-visible:bg-surface-2"
            >
              <div className="min-w-0 flex-1">
                <div className="text-small font-medium text-ink leading-snug">{item.fund_name_short ?? item.scheme_name}</div>
                <div className="flex gap-2 mt-0.5">
                  {item.amc_name && <span className="font-mono text-caption text-ink-muted truncate">{item.amc_name}</span>}
                  {item.plan_type && <span className="font-mono text-caption text-ink-secondary">{item.plan_type === 'direct' ? 'Direct' : 'Regular'}</span>}
                </div>
              </div>
              <svg className="shrink-0 text-ink-muted" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── ColumnsPopover ─────────────────────────────────────────────────────────

function ColumnsPopover({ visibleCols, onChange }: {
  visibleCols: Set<ColId>;
  onChange: (cols: Set<ColId>) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  function toggle(col: ColId) {
    const next = new Set(visibleCols);
    if (next.has(col)) next.delete(col); else next.add(col);
    onChange(next);
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        data-testid="columns-toggle"
        className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-small font-medium text-ink-secondary hover:border-royal hover:text-royal transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 6h16M7 12h10M10 18h4" /></svg>Columns
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-20 min-w-[168px] rounded-xl border border-line bg-surface shadow-lg p-3">
          {ALL_COL_IDS.map((col) => (
            <label key={col} className="flex items-center gap-2 px-1 py-1 cursor-pointer hover:text-ink rounded text-small text-ink-secondary">
              <input
                type="checkbox"
                className="accent-royal"
                checked={visibleCols.has(col)}
                onChange={() => toggle(col)}
                data-testid={`col-toggle-${col}`}
              />
              {COL_LABELS[col]}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

function PerPageSelect({ perPage, onChange }: { perPage: number; onChange: (n: number) => void }) {
  return (
    <div className="relative inline-flex items-center gap-2">
      <span className="font-mono text-[10px] uppercase tracking-[0.06em] font-medium text-ink-muted shrink-0 whitespace-nowrap">Show</span>
      <div className="relative">
        <select value={perPage} onChange={(e) => onChange(Number(e.target.value))} aria-label="Funds per page"
          className="h-[30px] rounded-full border border-line bg-surface pl-3 pr-7 text-caption text-ink font-medium cursor-pointer appearance-none focus-visible:outline-none focus-visible:border-royal focus-visible:ring-2 focus-visible:ring-royal/40 transition-colors">
          {PER_PAGE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-ink-muted" aria-hidden="true">
          <svg width="8" height="8" viewBox="0 0 10 10" fill="currentColor"><path d="M5 7L0.5 2.5h9L5 7z" /></svg>
        </span>
      </div>
    </div>
  );
}

function ViewToggle({ view, onChange }: { view: ViewMode; onChange: (v: ViewMode) => void }) {
  const items: { key: ViewMode; label: string; icon: React.ReactNode }[] = [
    { key: 'table', label: 'Table', icon: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18M3 12h18M3 18h18" /></svg> },
    { key: 'cards', label: 'Cards', icon: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /></svg> },
  ];
  return (
    <div className="inline-flex rounded-lg border border-line bg-surface-2 p-0.5" role="group" aria-label="View mode">
      {items.map((it) => (
        <button key={it.key} type="button" onClick={() => onChange(it.key)} aria-pressed={view === it.key}
          className={cn('inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-small font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
            view === it.key ? 'bg-surface text-ink shadow-sm' : 'text-ink-muted hover:text-ink')}>
          {it.icon}{it.label}
        </button>
      ))}
    </div>
  );
}

function getPageWindow(current: number, total: number): (number | '…')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | '…')[] = [1];
  if (current > 3) pages.push('…');
  for (let p = Math.max(2, current - 1); p <= Math.min(total - 1, current + 1); p++) pages.push(p);
  if (current < total - 2) pages.push('…');
  pages.push(total);
  return pages;
}

function Pagination({ page, total, limit, onPage, leftSlot }: {
  page: number; total: number; limit: number; onPage: (p: number) => void; leftSlot?: React.ReactNode;
}) {
  const totalPages = Math.ceil(total / limit);
  if (totalPages <= 1 && !leftSlot) return null;
  const win = getPageWindow(page, totalPages);
  const start = (page - 1) * limit + 1, end = Math.min(page * limit, total);
  return (
    <div className="flex items-center justify-between mt-3 gap-3 flex-wrap">
      {leftSlot ?? <p className="font-mono text-caption text-ink-muted">{start}–{end} of {total} funds</p>}
      {totalPages > 1 && (
        <div className="flex items-center gap-1">
          <button type="button" disabled={page <= 1} onClick={() => onPage(page - 1)} className="inline-flex items-center px-2.5 py-1 rounded-full text-caption font-medium border border-line bg-surface text-ink-secondary hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">‹ Prev</button>
          {win.map((p, i) => p === '…'
            ? <span key={`e${i}`} className="px-1 text-caption text-ink-muted font-mono">…</span>
            : <button key={p} type="button" onClick={() => onPage(p as number)} aria-label={`Page ${p}`} aria-current={p === page ? 'page' : undefined}
                className={cn('inline-flex items-center justify-center w-7 h-7 rounded-full text-caption font-medium border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                  p === page ? 'bg-ink text-bg border-ink' : 'bg-surface text-ink-secondary border-line hover:text-ink')}>{p}</button>)}
          <button type="button" disabled={page >= totalPages} onClick={() => onPage(page + 1)} className="inline-flex items-center px-2.5 py-1 rounded-full text-caption font-medium border border-line bg-surface text-ink-secondary hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">Next ›</button>
        </div>
      )}
    </div>
  );
}

// ── body ───────────────────────────────────────────────────────────────────

function ExplorerBody({ initialCategory, initialQuery }: { initialCategory: string | null; initialQuery: string | null }) {
  const router = useRouter();
  const { data: catData, isLoading: catsLoading } = useFundCategories();
  const { data: moodData } = useMoodCurrent();
  const lb = useLeaderboard();
  const boards = lb.data?.boards;
  const hero = lb.data?.hero;

  const [activeCategory, setActiveCategory] = React.useState('');
  const [sort, setSort]                     = React.useState<SortKey>('rank');
  const [sortDir, setSortDir]               = React.useState<'asc' | 'desc'>('desc');
  const [page, setPage]                     = React.useState(1);
  const [search, setSearch]                 = React.useState(initialQuery ?? '');
  const [planFilter, setPlanFilter]         = React.useState<PlanFilter>('all');
  const [optionFilter, setOptionFilter]     = React.useState<OptionFilter>('all');
  const [riskFilter, setRiskFilter]         = React.useState<string[]>([]);
  const [maxTer, setMaxTer]                 = React.useState('');
  const [minAum, setMinAum]                 = React.useState('');
  const [perPage, setPerPage]               = React.useState(20);
  const [view, setView]                     = React.useState<ViewMode>('table');
  const [activeIntentId, setActiveIntentId] = React.useState<string | null>(null);
  const [visibleCols, setVisibleCols]       = React.useState<Set<ColId>>(() => new Set(ALL_COL_IDS));

  const { items: slItems, toggle: slToggle, remove: slRemove, isins: slIsins, isFull: slFull, count: slCount } = useShortlist();
  const slSet = React.useMemo(() => new Set(slIsins), [slIsins]);

  // Applied server-side filter values (committed on "Apply filters" click).
  const [appliedMaxTer, setAppliedMaxTer]     = React.useState<number | undefined>(undefined);
  const [appliedMinAum, setAppliedMinAum]     = React.useState<number | undefined>(undefined);
  const [appliedRisk, setAppliedRisk]         = React.useState<string | undefined>(undefined);

  React.useEffect(() => {
    if (!catData?.categories.length || activeCategory) return;
    const first = initialCategory ?? catData.categories[0].key;
    const found = catData.categories.find((c) => c.key === first);
    setActiveCategory(found?.key ?? catData.categories[0].key);
  }, [catData, initialCategory, activeCategory]);

  const handleCategoryChange = (key: string) => {
    setActiveCategory(key); setPage(1); setSearch(''); setPlanFilter('all'); setOptionFilter('all'); setSortDir('desc');
    setRiskFilter([]); setMaxTer(''); setMinAum('');
    setAppliedMaxTer(undefined); setAppliedMinAum(undefined); setAppliedRisk(undefined);
  };
  const handleSort = (key: SortKey) => {
    if (key === sort) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    else { setSort(key); setSortDir('desc'); }
    setPage(1);
  };

  // Shared quick-intent handler (Phase C) — every intent's backing is a real
  // category filter, a real sort, or a real page/anchor link.
  const handleIntent = (intent: QuickIntent) => {
    setActiveIntentId(intent.id);
    if (intent.backing.kind === 'category') handleCategoryChange(intent.backing.category);
    else if (intent.backing.kind === 'sort') { setSort(intent.backing.sort as SortKey); setSortDir(intent.backing.dir); setPage(1); }
    else router.push(intent.backing.href);
  };
  const activeIntent = QUICK_INTENTS.find((q) => q.id === activeIntentId) ?? null;

  const { data, isLoading: fundsLoading, isError } = useFundExplorer({
    category: activeCategory, sort, sortDir,
    planType: planFilter !== 'all' ? planFilter : undefined,
    optionType: optionFilter !== 'all' ? optionFilter : undefined,
    page, limit: perPage,
    maxTer: appliedMaxTer,
    minAum: appliedMinAum,
    riskometer: appliedRisk,
  });
  const { data: leadersData } = useFundExplorer({ category: activeCategory, sort: 'rank', sortDir: 'asc', page: 1, limit: 3 });

  const filtered = React.useMemo(() => {
    if (!data?.funds) return [];
    const q = search.toLowerCase().trim();
    if (!q) return data.funds;
    return data.funds.filter((f) => f.scheme_name.toLowerCase().includes(q) || (f.amc_name?.toLowerCase().includes(q) ?? false));
  }, [data?.funds, search]);

  const totalRanked = React.useMemo(() => catData?.categories.reduce((s, c) => s + c.fund_count, 0) ?? null, [catData]);
  const activeCategoryName = React.useMemo(() => {
    const c = catData?.categories.find((x) => x.key === activeCategory);
    return c ? formatCategoryLabel(c.display_name) : '';
  }, [catData, activeCategory]);

  if (catsLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-56 rounded-2xl" />
        <Skeleton className="h-[56px] rounded-lg" />
        <div className="flex flex-col gap-2">{[...Array(8)].map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      {/* HERO */}
      <ExploreHero
        totalFunds={totalRanked}
        categoryCount={catData?.categories.length ?? null}
        moodRegime={moodData?.regime ?? null}
        trendingCategory={hero?.trending_category ?? null}
        topMoverName={boards?.movers_up?.rows[0]?.fund_name_short ?? boards?.movers_up?.rows[0]?.scheme_name ?? null}
        topMoverDelta={boards?.movers_up?.rows[0]?.rank_delta ?? null}
        topInflowCategory={boards?.category_inflows?.rows[0]?.category ?? null}
        topInflowCr={boards?.category_inflows?.rows[0]?.net_flow_cr ?? null}
        onIntent={handleIntent}
        activeIntentId={activeIntentId}
      />

      {/* SEARCH + category quick-jump tags (Phase C: real category filters, not search-text shortcuts) */}
      <Section>
        <TypeaheadSearch clientSearch={search} onClientSearch={(v) => { setSearch(v); setPage(1); }} />
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          <span className="text-caption text-ink-muted font-medium mr-1">Try:</span>
          {TRY_INTENTS.map((intent) => (
            <button key={intent.id} type="button" title={intent.rule} onClick={() => handleIntent(intent)}
              aria-pressed={activeIntentId === intent.id}
              className="rounded-lg border border-line bg-surface px-2.5 py-1 text-caption font-medium text-ink-secondary hover:border-royal hover:text-royal transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
              {intent.label}
            </button>
          ))}
        </div>
      </Section>

      {!catData?.categories.length ? (
        <Section>
          <div className="rounded-xl border border-line bg-surface-2 p-10 text-center">
            <div className="text-2xl mb-3" aria-hidden="true">📊</div>
            <p className="text-small font-medium text-ink">Market rankings not yet available</p>
            <p className="mt-1 text-caption text-ink-muted">Rankings are computed nightly — check back tomorrow.</p>
          </div>
        </Section>
      ) : (
        <>
          {/* 01 QUICK DISCOVERY */}
          <Section>
            <SectionHeader index="01" title="Quick Discovery" info="One-click presets" />
            <div className="flex items-center gap-x-4 gap-y-2 flex-wrap mb-3">
              <CategoryDropdown categories={catData.categories} activeKey={activeCategory} onSelect={handleCategoryChange} />
              <PillGroup label="Plan" options={PLAN_OPTIONS} value={planFilter} onChange={(k) => { setPlanFilter(k); setPage(1); }} />
              <PillGroup label="Option" options={OPTION_OPTIONS} value={optionFilter} onChange={(k) => { setOptionFilter(k); setPage(1); }} />
              {data && <span className="font-mono text-caption text-ink-muted whitespace-nowrap ml-auto">{data.total} funds</span>}
            </div>
            <QuickChips active={activeIntentId} onSelect={handleIntent} />
            {activeIntent && (
              <p className="mt-2 text-caption text-ink-muted">How this list is built: {activeIntent.rule}</p>
            )}
          </Section>

          {/* ADVANCED FILTERS */}
          <Section>
            <AdvancedFilters
              planFilter={planFilter} optionFilter={optionFilter}
              onPlan={(k) => { setPlanFilter(k); setPage(1); }}
              onOption={(k) => { setOptionFilter(k); setPage(1); }}
              riskFilter={riskFilter} onRisk={setRiskFilter}
              maxTer={maxTer} onMaxTer={setMaxTer}
              minAum={minAum} onMinAum={setMinAum}
              onApply={() => {
                setAppliedMaxTer(maxTer ? parseFloat(maxTer) : undefined);
                setAppliedMinAum(minAum ? parseFloat(minAum) : undefined);
                setAppliedRisk(riskFilter.length > 0 ? riskFilter.join(',') : undefined);
                setPage(1);
              }}
              onReset={() => {
                setRiskFilter([]); setMaxTer(''); setMinAum('');
                setAppliedMaxTer(undefined); setAppliedMinAum(undefined); setAppliedRisk(undefined);
                setPlanFilter('all'); setOptionFilter('all');
                setPage(1);
              }}
            />
          </Section>

          {/* 02 SPOTLIGHT & SIGNALS */}
          <Section>
            <SectionHeader index="02" title="Spotlight &amp; Signals" badge={
              (boards?.ai_spotlight || boards?.hidden_gems || boards?.future_leaders || boards?.label_upgrades)
                ? <LiveBadge /> : undefined
            } />
            <SpotlightSignals
              aiSpotlight={boards?.ai_spotlight}
              hiddenGems={boards?.hidden_gems}
              futureLeaders={boards?.future_leaders}
              labelUpgrades={boards?.label_upgrades}
            />
          </Section>

          {/* 03 FUND EXPLORER (real) */}
          <Section>
            <SectionHeader index="03" title="Fund Explorer" info={data ? `${activeCategoryName} · ${data.total} funds` : undefined} />
            <div className="flex items-center gap-2 flex-wrap mb-3">
              <ViewToggle view={view} onChange={setView} />
              <div className="flex items-center gap-2 ml-auto flex-wrap">
                <ColumnsPopover visibleCols={visibleCols} onChange={setVisibleCols} />
                <button
                  type="button"
                  data-testid="export-csv"
                  onClick={() => {
                    const headers = ['Fund', 'ISIN', 'Category', 'Label', 'Band', 'Rank', '3M%', '6M%', '1Y%', '3Y%', '5Y%', 'TER%', 'AUM(Cr)', 'Risk', 'Sharpe', 'Drawdown%'];
                    const rows = filtered.map((f) => [
                      f.fund_name_short ?? f.scheme_name, f.isin, f.sebi_category,
                      f.verb_label, f.confidence_band ?? '', f.category_rank,
                      f.return_3m_pct?.toFixed(1) ?? '', f.return_6m_pct?.toFixed(1) ?? '',
                      f.return_1y_pct?.toFixed(1) ?? '', f.return_3y_pct?.toFixed(1) ?? '',
                      f.return_5y_pct?.toFixed(1) ?? '', f.expense_ratio_pct?.toFixed(2) ?? '',
                      f.aum_crore?.toFixed(0) ?? '', f.riskometer ?? '',
                      f.sharpe_ratio?.toFixed(2) ?? '', f.max_drawdown_pct?.toFixed(1) ?? '',
                    ]);
                    const csv = [headers, ...rows]
                      .map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(','))
                      .join('\n');
                    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `funds-${activeCategory.replace(/[^a-z0-9]/gi, '-')}.csv`;
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-small font-medium text-ink-secondary hover:border-royal hover:text-royal transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 3v12M8 11l4 4 4-4M5 21h14" /></svg>Export
                </button>
                <PerPageSelect perPage={perPage} onChange={(n) => { setPerPage(n); setPage(1); }} />
              </div>
            </div>
            {fundsLoading ? (
              <div className="flex flex-col gap-2">{[...Array(8)].map((_, i) => <Skeleton key={i} className="h-14 rounded-lg" />)}</div>
            ) : isError ? (
              <ErrorCard title="Could not load funds" message="Please try again in a moment." />
            ) : view === 'table' ? (
              <FundExplorerTable
                funds={filtered}
                activeSort={sort}
                sortDir={sortDir}
                onSort={handleSort}
                visibleCols={visibleCols}
                shortlistIsins={slSet}
                shortlistFull={slFull}
                onShortlistToggle={slToggle}
              />
            ) : (
              <FundCardGrid
                funds={filtered}
                shortlistIsins={slSet}
                shortlistFull={slFull}
                onShortlistToggle={slToggle}
              />
            )}
            {data && <Pagination page={page} total={data.total} limit={perPage} onPage={setPage} />}
            {data && (
              <div className="rounded-lg border border-line bg-surface-2 p-4 mt-3">
                <DisclosureBundle disclosure={data.disclosure || undefined} notAdvice={data.not_advice || 'For education only — not investment advice.'} />
              </div>
            )}
          </Section>

          {/* 04 CATEGORY LEADERBOARDS */}
          <Section>
            <SectionHeader index="04" title="Category Leaderboards"
              badge={boards?.champions ? <LiveBadge /> : undefined} />
            <Leaderboards champions={boards?.champions} />
          </Section>

          {/* 05 MARKET MOOD */}
          <Section>
            <SectionHeader index="05" title="Market Mood" tag="DhanRadar Mood" badge={<LiveBadge />} />
            <MarketMoodSection />
          </Section>

          {/* 06 FUND FLOW */}
          <Section>
            <SectionHeader index="06" title="Fund Flow" badge={(boards?.category_inflows || boards?.aum_growth) ? <LiveBadge /> : undefined} />
            <FundFlowSection categoryInflows={boards?.category_inflows} aumGrowth={boards?.aum_growth} />
          </Section>

          {/* 07 MOMENTUM */}
          <Section>
            <SectionHeader index="07" title="Momentum Center" badge={(boards?.movers_up || boards?.movers_down) ? <LiveBadge /> : undefined} />
            <Momentum moversUp={boards?.movers_up} moversDown={boards?.movers_down} />
          </Section>

          {/* 08 CONSISTENCY */}
          <Section>
            <SectionHeader index="08" title="Consistency Leaderboard"
              badge={boards?.sip_consistency ? <LiveBadge /> : undefined} />
            <ConsistencyTable sipConsistency={boards?.sip_consistency} threeLens={boards?.three_lens} />
          </Section>

          {/* 09 LOW COST */}
          <Section>
            <SectionHeader index="09" title="Low-Cost Leaderboard"
              badge={(boards?.value_ter || boards?.value_efficiency) ? <LiveBadge /> : undefined} />
            <LowCostTable valueTer={boards?.value_ter} valueEfficiency={boards?.value_efficiency} />
          </Section>

          {/* 10 STEADY SIP STARTERS */}
          <Section>
            <SectionHeader index="10" title="Steady SIP Starters" tag="New investor"
              badge={boards?.sip_beginner ? <LiveBadge /> : undefined} />
            <BeginnerPicks sipBeginner={boards?.sip_beginner} />
          </Section>

          {/* 11 AI FEED */}
          <Section>
            <SectionHeader index="11" title="AI Insights Feed" tag="DhanRadar AI" badge={boards?.ai_insights ? <LiveBadge /> : undefined} />
            <AiFeed board={boards?.ai_insights} />
          </Section>

          {/* TOP RANKED (real, derived) */}
          {leadersData?.funds?.length ? (
            <Section>
              <SectionHeader index="12" title="Top Ranked" info={activeCategoryName} />
              <CategoryLeaders leaders={leadersData.funds} categoryName={activeCategoryName} />
            </Section>
          ) : null}

          {/* FAQ */}
          <Section>
            <SectionHeader title="Discovery FAQ" />
            <DiscoveryFaq />
          </Section>
        </>
      )}

      <p className="mt-8 text-center text-caption text-ink-muted max-w-2xl mx-auto leading-relaxed">
        DhanRadar is an educational research platform, not a SEBI-registered investment adviser.

        Mutual fund investments are subject to market risks; read all scheme-related documents carefully.
        Past performance does not guarantee future returns.
      </p>

      <Shortlist items={slItems} onRemove={slRemove} count={slCount} />
    </div>
  );
}

function ExplorePageContent() {
  const searchParams = useSearchParams();
  const initialCategory = searchParams.get('category');
  // ?q= prefill (I4) — lets AMC cards on the leaderboard land here with the
  // AMC name already in the search box (client-side name/AMC filter).
  const initialQuery = searchParams.get('q');
  return (
    <div className="w-full px-4 sm:px-6 lg:px-8 xl:px-12 py-6">
      <ExplorerBody initialCategory={initialCategory} initialQuery={initialQuery} />
    </div>
  );
}

export default function ExplorePage() {
  return (
    <MaybeShell maxWidth="full">
      <React.Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
        <ExplorePageContent />
      </React.Suspense>
    </MaybeShell>
  );
}
