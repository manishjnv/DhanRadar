/**
 * Fund Detail V3 — Sections B: Snapshot · Performance · Risk Center.
 *
 * COMPLIANCE: factual stats (returns %, Sharpe, drawdown %, rank, quartile) are
 * DOM-allowed. NO DhanRadar composite score numbers, no advisory verbs
 * (buy/sell/hold/avoid/caution/switch).
 *
 * W1+W2 (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §17): every Performance-Center
 * tab (Returns/SIP/Rolling/Rank-Trend/Drawdowns/Consistency) and the whole Risk
 * Center are wired to real data (`fund.nav_series`, `fund.analytics`,
 * `fund.rank_history`, `fund.sip_illustration`, `fund.health`, plus the
 * benchmark daily-close endpoint). Fix 1 (fund-page-quick-wins) wires the
 * Returns-tab "vs benchmark & category" comparison table to real data too
 * (fund.analytics + the new /mf/benchmark/{key}/returns route) — only the
 * Rolling-tab "vs benchmark & category" table stays sampleData preview, with
 * its own inline <PreviewBadge/>.
 *
 * Item 3 (2026-07): the Returns-tab overlay picks a category-appropriate
 * benchmark (`categoryBenchmark.ts` — Large Cap → Nifty 100, Mid Cap → Nifty
 * Midcap 150, Flexi/Multi/ELSS/Value/Focused/Contra/Div-Yield → Nifty 500,
 * everything else → Nifty 50), falling back to Nifty 50 when the mapped
 * benchmark's series is empty (e.g. cold-start before its backfill runs).
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { useFundNav, useFundAnalytics, useFundSip, useFundPeople } from '@/features/mf/api';
import { useBenchmarkSeries, useBenchmarkReturns } from '@/features/portfolio/api';
import { benchmarkForCategory } from './categoryBenchmark';
import type { CategoryPercentileBand } from '@/features/mf/types';
import { DataState } from '@/components/ui/DataState';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  TabBar, ChipToggle, Accordion, BandBar, InfoTip, Panel,
  WhatThisMeans, PreviewBadge, GrowthChart, RankChart, DrawdownChart,
  TONE_TEXT,
} from './parts';
import {
  GROWTH, ROLLING, RANK,
} from './sampleData';
import type { Band3 } from './sampleData';
import type { FundHead } from './sectionsHero';

// SIP menu — amount/years are PROVISIONAL DEFAULTS (§18.4 founder decision
// pending), mirroring the backend's fixed Literal-typed menu (mf/router.py).
const SIP_AMOUNTS = [1000, 5000, 10000] as const;
const SIP_YEARS = [1, 3, 5] as const;

// Quartile → tone colour (Q1 = top quartile, best) — shared by the Consistency tab.
const QUARTILE_TONE: Record<1 | 2 | 3 | 4, string> = {
  1: 'bg-emerald text-white',
  2: 'bg-amber text-white',
  3: 'bg-red/70 text-white',
  4: 'bg-red text-white',
};

// ─────────────────────────────────────────────────────────────────────────────
// S9 — INVESTMENT SNAPSHOT
// ─────────────────────────────────────────────────────────────────────────────

/** Years since launch, one decimal — "—" when launch_date isn't on file. */
function fundAgeLabel(launchDate: string | null): string {
  if (!launchDate) return '—';
  const years = (Date.now() - new Date(launchDate).getTime()) / (365.25 * 24 * 3600 * 1000);
  return years > 0 ? `${years.toFixed(1)} yrs` : '—';
}

/** ELSS carries a statutory 3-year lock-in; every other category has none — a
 * static, factual category rule (not a per-fund data field). */
function isElss(category: string): boolean {
  return category.toLowerCase().includes('elss');
}

type SnapshotCell = {
  l: string;
  v: string;
  p?: string;
  /** sub-line tone */
  tone?: 'emerald' | 'red';
  /** main-value tone (returns colour up/down) */
  valueTone?: 'emerald' | 'red';
  tip: string;
};

/**
 * 4-col desktop / 2-col mobile KPI grid with 1px-gap dividers via gap-px +
 * bg-line wrapper (cells are bg-surface). Each cell: label + InfoTip, mono
 * value, optional coloured sub-line. Real cells come from `head` (already
 * fetched by FundDetailClientView) plus fund.analytics/fund.people for the
 * two cells that need them; source-blocked cells stay "—" with a tooltip
 * naming the reason (ADR-0039 per-cell pattern) — never a fabricated number.
 */
export function SnapshotSection({ head, isin }: { head: FundHead; isin: string }) {
  const { data: analyticsEnv } = useFundAnalytics(isin);
  const { data: peopleEnv } = useFundPeople(isin);
  const a = analyticsEnv?.analytics.data ?? null;
  const managers = peopleEnv?.people.data?.managers ?? [];
  const managerTenureYears = managers.length ? Math.max(...managers.map((m) => m.tenure_years)) : null;
  const elss = isElss(head.category);

  const cells: SnapshotCell[] = [
    {
      l: 'NAV',
      v: head.navLatest != null ? `₹${head.navLatest.toFixed(2)}` : '—',
      p: head.navChangePct != null
        ? `${head.navChangePct >= 0 ? '▲' : '▼'} ${Math.abs(head.navChangePct).toFixed(2)}% today`
        : head.navDate ? `as of ${new Date(head.navDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}` : undefined,
      tone: head.navChangePct != null ? (head.navChangePct >= 0 ? 'emerald' : 'red') : undefined,
      tip: 'Per-unit price of the fund.',
    },
    {
      l: 'Expense Ratio',
      v: head.expenseRatioPct != null ? `${head.expenseRatioPct.toFixed(2)}%` : '—',
      tip: 'Annual fee as % of your investment.',
    },
    {
      l: 'Fund Size (AUM)',
      v: head.fundAumCr != null ? `₹${head.fundAumCr.toLocaleString('en-IN')} Cr` : '—',
      p: head.fundAumCr != null && head.fundAumAsOf
        ? `as of ${new Date(head.fundAumAsOf).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })}`
        : undefined,
      tip: 'Total assets from the fund’s own SEBI disclosure.',
    },
    {
      l: 'Fund Age',
      v: fundAgeLabel(head.launchDate),
      p: head.launchDate ? `Since ${new Date(head.launchDate).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })}` : undefined,
      tip: 'Time since launch.',
    },
    {
      l: 'Manager Tenure',
      v: managerTenureYears != null ? `${managerTenureYears.toFixed(1)} yrs` : '—',
      tip: 'How long the current manager(s) have run it.',
    },
    {
      l: 'Category Rank',
      v: head.rank != null && head.total != null ? `#${head.rank} / ${head.total}` : '—',
      tip: 'Rank within its SEBI category.',
    },
    {
      l: 'Tracking Error',
      v: a?.tracking_error_pct != null ? `${a.tracking_error_pct.toFixed(2)}%` : '—',
      tip: 'How tightly the fund tracks its benchmark index.',
    },
    {
      l: 'Plan / Option',
      v: head.planOption.length ? head.planOption.join(' · ') : '—',
      tip: 'Direct/Regular plan and Growth/IDCW option.',
    },
    {
      l: 'Lock-in',
      v: elss ? '3 years' : 'None',
      tip: elss ? 'ELSS funds carry a mandatory 3-year lock-in.' : 'No mandatory holding period for this category.',
    },
    {
      l: 'Stamp Duty',
      v: '0.005%',
      p: 'On purchase',
      tip: 'Statutory govt levy on buying units — same for every fund.',
    },
    {
      l: '1Y Return',
      v: fmtPct(head.return1yPct),
      valueTone: head.return1yPct != null ? (head.return1yPct >= 0 ? 'emerald' : 'red') : undefined,
      tip: 'Return over the last 1 year.',
    },
    {
      l: '3Y Return',
      v: fmtPct(head.return3yPct),
      valueTone: head.return3yPct != null ? (head.return3yPct >= 0 ? 'emerald' : 'red') : undefined,
      tip: 'Annualised return over the last 3 years.',
    },
    {
      l: '5Y Return',
      v: fmtPct(head.return5yPct),
      valueTone: head.return5yPct != null ? (head.return5yPct >= 0 ? 'emerald' : 'red') : undefined,
      tip: 'Annualised return over the last 5 years.',
    },
    { l: 'Exit Load', v: '—', tip: 'Exit load isn’t in our data yet.' },
    { l: 'Min SIP · Lumpsum', v: '—', tip: 'Minimum investment amounts aren’t in our data yet.' },
    { l: 'Portfolio Turnover', v: '—', tip: 'Portfolio turnover isn’t in our data yet.' },
    { l: 'Riskometer', v: '—', tip: 'Riskometer band isn’t in our data yet.' },
  ];

  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-line">
      <div className="grid grid-cols-2 gap-px sm:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-7">
        {cells.map((item) => (
          <div key={item.l} className="bg-surface px-4 py-3.5 sm:px-[15px]">
            {/* label + tip */}
            <div className="flex items-center gap-1.5">
              <span className="text-[10.5px] font-semibold text-ink-muted">{item.l}</span>
              <InfoTip tip={item.tip} />
            </div>
            {/* value */}
            <div className={cn('mt-1.5 font-mono text-[15px] font-bold', item.valueTone ? TONE_TEXT[item.valueTone] : 'text-ink')}>
              {item.v}
            </div>
            {/* sub-line */}
            {item.p && (
              <div
                className={cn(
                  'mt-0.5 text-[10px] font-semibold',
                  item.tone ? TONE_TEXT[item.tone] : 'text-ink-muted',
                )}
              >
                {item.p}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers reused across Performance tabs
// ─────────────────────────────────────────────────────────────────────────────

/** Colour a return value: null → muted dash, positive → emerald, negative → red. */
function ReturnValue({ v }: { v: number | null }) {
  if (v === null) return <span className="font-mono text-[14px] font-bold text-ink-faint">—</span>;
  const cls = v >= 0 ? 'text-emerald' : 'text-red';
  return (
    <span className={cn('font-mono text-[14px] font-bold', cls)}>
      {v >= 0 ? '+' : ''}{v.toFixed(1)}%
    </span>
  );
}

function fmtPct(v: number | null | undefined, digits = 1): string {
  return v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(digits)}%`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Performance tabs
// ─────────────────────────────────────────────────────────────────────────────

const PERF_TABS = [
  { key: 'returns',   label: 'Returns'     },
  { key: 'sip',       label: 'SIP Growth'  },
  { key: 'rolling',   label: 'Rolling'     },
  { key: 'rank',      label: 'Rank Trend'  },
  { key: 'drawdowns', label: 'Drawdowns'   },
  { key: 'consist',   label: 'Consistency' },
];

// UI range labels (GROWTH.ranges) → the fund.nav_series `range` query param.
const RANGE_TO_API: Record<string, '1y' | '3y' | '5y' | 'max'> = {
  '1Y': '1y', '3Y': '3y', '5Y': '5y', 'MAX': 'max',
};

// Returns-tab comparison table column labels (Fix 1) — Launch has no real
// basis anywhere yet, kept as a column so its cells can honestly show "—"
// rather than being silently dropped.
const COMPARISON_TABLE_HEAD = ['Period', '1Y', '3Y', '5Y', 'Launch'];

// ── Returns tab ──────────────────────────────────────────────────────────────
function ReturnsTab({ head, isin }: { head: FundHead; isin: string }) {
  const [uiRange, setUiRange] = React.useState(GROWTH.ranges[2]); // default 5Y
  const apiRange = RANGE_TO_API[uiRange] ?? '5y';

  const { data: navEnv, isLoading: navLoading } = useFundNav(isin, apiRange);
  const navData = navEnv?.data ?? null;

  // Fix 1 (fund-page-quick-wins) — category_percentiles.return_1y_pct/3y_pct p50
  // feeds the comparison table's "Category avg" row below.
  const { data: analyticsEnv } = useFundAnalytics(isin);
  const analyticsData = analyticsEnv?.analytics.data ?? null;

  // Item 3 (2026-07): category-appropriate benchmark, falling back to Nifty 50
  // when the mapped benchmark's own series is empty (e.g. cold-start before
  // its backfill has run) — the `enabled` flag skips the fallback fetch
  // entirely until it's actually needed.
  const benchmarkMeta = React.useMemo(() => benchmarkForCategory(head.category), [head.category]);
  const dateParams = navData
    ? { from: navData.from ?? undefined, to: navData.to ?? undefined }
    : undefined;
  const { data: mappedBench } = useBenchmarkSeries(benchmarkMeta.key, dateParams);
  const mappedIsEmpty = !!mappedBench && mappedBench.points.length === 0;
  const shouldFallback = benchmarkMeta.key !== 'nifty50' && mappedIsEmpty;
  const { data: fallbackBench } = useBenchmarkSeries('nifty50', dateParams, { enabled: shouldFallback });
  const benchSeries = shouldFallback ? fallbackBench : mappedBench;
  const benchDisplayName = shouldFallback ? 'Nifty 50' : benchmarkMeta.displayName;

  // Rebase both series to a ₹10,000 start (growth-of-10k) — W1 real chart
  // (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §10.5). Each series rebases off its own
  // first point rather than date-matching every trading day — an intentional
  // simplification for an illustrative chart, not an exact tracking-error overlay.
  const fundSeries = React.useMemo(() => {
    const pts = navData?.points ?? [];
    if (pts.length < 2 || pts[0].nav <= 0) return [];
    return pts.map((p) => 10000 * (p.nav / pts[0].nav));
  }, [navData]);
  const benchmarkSeries = React.useMemo(() => {
    const pts = benchSeries?.points ?? [];
    if (pts.length < 2 || pts[0].close_value <= 0) return null;
    return pts.map((p) => 10000 * (p.close_value / pts[0].close_value));
  }, [benchSeries]);

  const growthValue = fundSeries.length ? Math.round(fundSeries[fundSeries.length - 1]) : null;
  const growthGainPct = fundSeries.length ? (fundSeries[fundSeries.length - 1] / 10000 - 1) * 100 : null;

  // W0 — real period returns (§17); periods we don't have yet (1M/10Y/Launch) show "—"
  // rather than the sampleData preview number, so real and unbuilt cells aren't mixed.
  const returns: { p: string; v: number | null }[] = [
    { p: '1M', v: null },
    { p: '3M', v: head.return3mPct },
    { p: '6M', v: head.return6mPct },
    { p: '1Y', v: head.return1yPct },
    { p: '3Y', v: head.return3yPct },
    { p: '5Y', v: head.return5yPct },
    { p: '10Y', v: null },
    { p: 'Launch', v: null },
  ];

  // Comparison table — real (Fix 1, fund-page-quick-wins). "This fund" reuses
  // head.return1yPct/3yPct/5yPct (same numbers as the 8-col grid above).
  // "Benchmark" is fetched from the new server-side /mf/benchmark/{key}/returns
  // route for the SAME resolved key the growth-chart overlay above uses
  // (mapped category benchmark, or its nifty50 fallback when the mapped
  // series is empty) — table and chart always agree on which index is shown.
  // "Category avg" is the category's stored p50 (mf_category_stats) already
  // served in fund.analytics.category_percentiles. Launch has no real basis
  // anywhere yet and 5Y category stats aren't published — both stay "—"
  // rather than a fabricated/interpolated number (§8.4 no-fabrication).
  const resolvedBenchmarkKey = shouldFallback ? 'nifty50' : benchmarkMeta.key;
  const { data: benchReturns } = useBenchmarkReturns(resolvedBenchmarkKey);
  const catPct = analyticsData?.category_percentiles;

  const comparisonRows: { row: string; me: boolean; tip?: string; cells: string[] }[] = [
    {
      row: 'This fund',
      me: true,
      cells: [fmtPct(head.return1yPct), fmtPct(head.return3yPct), fmtPct(head.return5yPct), '—'],
    },
    {
      row: 'Benchmark',
      me: false,
      tip: 'Price index; excludes dividends.',
      cells: [
        fmtPct(benchReturns?.return_1y_pct),
        fmtPct(benchReturns?.return_3y_pct),
        fmtPct(benchReturns?.return_5y_pct),
        '—',
      ],
    },
    {
      row: 'Category avg',
      me: false,
      cells: [
        fmtPct(catPct?.return_1y_pct?.p50),
        fmtPct(catPct?.return_3y_pct?.p50),
        '—',
        '—',
      ],
    },
  ];

  return (
    <>
      {/* 8-col return cells */}
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-8">
        {returns.map((r) => (
          <div
            key={r.p}
            className="rounded-xl border border-line bg-surface px-1.5 py-3 text-center"
          >
            <div className="text-[10.5px] font-semibold text-ink-muted">{r.p}</div>
            <div className="mt-1"><ReturnValue v={r.v} /></div>
          </div>
        ))}
      </div>

      {/* Comparison table — real (Fix 1): this fund / benchmark / category avg */}
      <div className="mt-4 flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">vs benchmark &amp; category</span>
      </div>
      <table className="mt-2 w-full border-collapse text-[12.5px]">
        <thead>
          <tr>
            {COMPARISON_TABLE_HEAD.map((h, i) => (
              <th
                key={h}
                className={cn(
                  'border-b border-line pb-2 pt-2 font-mono text-[9.5px] font-bold uppercase tracking-[0.05em] text-ink-muted',
                  i === 0 ? 'text-left' : 'text-right',
                )}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {comparisonRows.map((row) => (
            <tr key={row.row}>
              <td
                className={cn(
                  'border-b border-line py-2.5 pr-2 font-semibold last:border-b-0',
                  row.me ? 'text-royal' : 'text-ink-secondary',
                )}
              >
                <span className="inline-flex items-center gap-1">
                  {row.row}
                  {row.tip && <InfoTip tip={row.tip} />}
                </span>
              </td>
              {row.cells.map((c, i) => (
                <td
                  key={i}
                  className={cn(
                    'border-b border-line py-2.5 text-right font-mono font-semibold last:border-b-0',
                    row.me ? 'text-emerald' : 'text-ink',
                  )}
                >
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Growth chart — real (W1) */}
      <div className="mt-4 rounded-2xl border border-line bg-gradient-to-b from-white to-surface-2 p-4">
        <div className="mb-2 flex items-baseline justify-between">
          <span className="text-[13px] font-semibold text-ink-secondary">
            Growth of {GROWTH.invested}
          </span>
          <span className="font-mono text-[13px] font-bold text-emerald">
            {growthValue != null ? `₹${growthValue.toLocaleString('en-IN')}` : '—'}{' '}
            <span className="font-normal text-ink-muted">
              · {growthGainPct != null ? fmtPct(growthGainPct, 0) : '—'}
            </span>
          </span>
        </div>
        <DataState
          status={navLoading ? 'loading' : fundSeries.length >= 2 ? 'present' : 'empty'}
          emptyCopy="We don't have enough price history yet to draw this chart."
          skeleton={<Skeleton className="h-[170px] w-full rounded-xl" />}
        >
          <GrowthChart fund={fundSeries} benchmark={benchmarkSeries} height={170} />
        </DataState>
        {/* Range toggle */}
        <div className="mt-3">
          <ChipToggle
            options={GROWTH.ranges.map((r) => ({ key: r, label: r }))}
            active={uiRange}
            onChange={setUiRange}
          />
        </div>
        {/* Legend */}
        <div className="mt-3 flex flex-wrap gap-4 text-[11.5px] text-ink-muted">
          <span className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2 w-5 rounded-full" style={{ background: '#1E5EFF' }} aria-hidden="true" />
            This fund
          </span>
          <span className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2 w-5 rounded-full bg-ink-faint" aria-hidden="true" />
            Benchmark ({benchDisplayName})
          </span>
        </div>
      </div>

      <WhatThisMeans>
        This chart shows how {GROWTH.invested} invested at the start of the selected period would
        have grown, next to the {benchDisplayName} price index (excludes dividends) for comparison.
      </WhatThisMeans>
    </>
  );
}

// ── SIP Growth tab ────────────────────────────────────────────────────────────
// Real (W2, §10.4) — historical SIP illustration, never a projection.
function SipTab({ isin }: { isin: string }) {
  const [amount, setAmount] = React.useState<(typeof SIP_AMOUNTS)[number]>(5000);
  const [years, setYears] = React.useState<(typeof SIP_YEARS)[number]>(5);
  const { data, isLoading, isError, refetch } = useFundSip(isin, amount, years);
  const sip = data?.data ?? null;
  const status = isLoading ? 'loading' : isError ? 'error' : (data?.status ?? 'empty');
  const hasResult = sip != null && sip.total_invested != null && sip.final_value != null;

  return (
    <>
      {/* Amount + years chips */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <ChipToggle
          options={SIP_AMOUNTS.map((a) => ({ key: String(a), label: `₹${a.toLocaleString('en-IN')}/mo` }))}
          active={String(amount)}
          onChange={(k) => setAmount(Number(k) as (typeof SIP_AMOUNTS)[number])}
        />
        <ChipToggle
          options={SIP_YEARS.map((y) => ({ key: String(y), label: `${y}Y` }))}
          active={String(years)}
          onChange={(k) => setYears(Number(k) as (typeof SIP_YEARS)[number])}
        />
      </div>

      <DataState
        status={status}
        emptyCopy="We don't have price history for this fund yet."
        onRetry={refetch}
        skeleton={<Skeleton className="h-40 w-full rounded-2xl" />}
      >
        {hasResult && sip ? (
          <>
            {/* Result panel */}
            <div className="mb-4 flex items-start justify-between rounded-2xl bg-emerald/[0.08] p-4">
              <div>
                <div className="text-[11px] font-semibold text-ink-muted">
                  ₹{amount.toLocaleString('en-IN')}/mo · {years} yr{years > 1 ? 's' : ''} · invested ₹{sip.total_invested!.toLocaleString('en-IN')}
                </div>
                <div className="mt-1 font-mono text-[24px] font-extrabold tracking-tight text-emerald">
                  ₹{sip.final_value!.toLocaleString('en-IN')}
                </div>
              </div>
              <div className="text-right">
                <div className="text-[11px] font-semibold text-ink-muted">Gain</div>
                <div className="font-mono text-[15px] font-bold text-emerald">
                  +₹{(sip.final_value! - sip.total_invested!).toLocaleString('en-IN')}
                </div>
                <div className="font-mono text-[12px] text-emerald">
                  {sip.xirr_pct != null ? `${sip.xirr_pct.toFixed(1)}% XIRR` : '— XIRR'}
                </div>
              </div>
            </div>

            {/* SIP tiles */}
            <div className="grid grid-cols-3 gap-2">
              {[
                { p: 'Invested', v: `₹${sip.total_invested!.toLocaleString('en-IN')}` },
                { p: 'Value today', v: `₹${sip.final_value!.toLocaleString('en-IN')}` },
                { p: 'XIRR', v: sip.xirr_pct != null ? `${sip.xirr_pct.toFixed(1)}%` : '—' },
              ].map((t) => (
                <div key={t.p} className="rounded-xl border border-line bg-surface py-3 text-center">
                  <div className="text-[10.5px] font-semibold text-ink-muted">{t.p}</div>
                  <div className="mt-1 font-mono text-[14px] font-bold text-emerald">{t.v}</div>
                </div>
              ))}
            </div>

            <WhatThisMeans>{sip.assumptions}</WhatThisMeans>
          </>
        ) : (
          <div className="rounded-2xl border border-line bg-surface-2 p-4 text-center text-small text-ink-muted">
            {sip
              ? `This fund only has ${sip.months_invested} month${sip.months_invested === 1 ? '' : 's'} of price history — too short to illustrate a SIP outcome yet.`
              : "We don't have price history for this fund yet."}
          </div>
        )}
      </DataState>
    </>
  );
}

// ── Rolling tab ───────────────────────────────────────────────────────────────
function RollingTab({ isin }: { isin: string }) {
  const { data } = useFundAnalytics(isin);
  const a = data?.analytics.data ?? null;

  const tiles = [
    { p: '1Y rolling avg', v: fmtPct(a?.rolling_1y_avg_pct) },
    { p: '1Y rolling min', v: fmtPct(a?.rolling_1y_min_pct) },
    { p: '1Y rolling max', v: fmtPct(a?.rolling_1y_max_pct) },
    { p: '% positive', v: a?.rolling_1y_pct_positive != null ? `${a.rolling_1y_pct_positive.toFixed(0)}%` : '—' },
  ];

  // Rolling-3Y tiles (W2 §10.5) — same shape, longer window; "—" when not yet
  // computed (fund under 3 years old, or nightly refresh hasn't run for it).
  const tiles3y = [
    { p: '3Y rolling avg', v: fmtPct(a?.rolling_3y_avg_pct) },
    { p: '3Y rolling min', v: fmtPct(a?.rolling_3y_min_pct) },
    { p: '3Y rolling max', v: fmtPct(a?.rolling_3y_max_pct) },
    { p: '% positive', v: a?.rolling_3y_pct_positive != null ? `${a.rolling_3y_pct_positive.toFixed(0)}%` : '—' },
  ];

  const meaning = a?.rolling_1y_pct_positive != null
    ? `Rolling returns test every holding period, not just lucky start dates. This fund's 1-year rolling return was positive in about ${a.rolling_1y_pct_positive.toFixed(0)}% of the periods measured.`
    : "Rolling returns test every holding period, not just lucky start dates — we don't have enough history yet to measure this fund's rolling-return consistency.";

  return (
    <>
      {/* Tiles — real (W1) */}
      <div className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {tiles.map((t) => (
          <div key={t.p} className="rounded-xl border border-line bg-surface py-3 text-center">
            <div className="text-[10.5px] font-semibold text-ink-muted">{t.p}</div>
            <div className="mt-1 font-mono text-[14px] font-bold text-emerald">{t.v}</div>
          </div>
        ))}
      </div>
      {/* 3Y tiles — real (W2 §10.5) */}
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {tiles3y.map((t) => (
          <div key={t.p} className="rounded-xl border border-line bg-surface py-3 text-center">
            <div className="text-[10.5px] font-semibold text-ink-muted">{t.p}</div>
            <div className="mt-1 font-mono text-[14px] font-bold text-emerald">{t.v}</div>
          </div>
        ))}
      </div>

      {/* Comparison table — preview (3Y/5Y rolling vs bench/category is W2, §10.5) */}
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">vs benchmark &amp; category</span>
        <PreviewBadge />
      </div>
      <table className="w-full border-collapse text-[12.5px]">
        <thead>
          <tr>
            {ROLLING.head.map((h, i) => (
              <th
                key={h}
                className={cn(
                  'border-b border-line pb-2 pt-1 font-mono text-[9.5px] font-bold uppercase tracking-[0.05em] text-ink-muted',
                  i === 0 ? 'text-left' : 'text-right',
                )}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROLLING.rows.map((row) => (
            <tr key={row.row}>
              <td className="border-b border-line py-2.5 pr-2 font-semibold text-ink-secondary last:border-b-0">
                {row.row}
              </td>
              {row.cells.map((c, i) => (
                <td
                  key={i}
                  className={cn(
                    'border-b border-line py-2.5 text-right font-mono font-semibold last:border-b-0',
                    i === 0 ? 'text-emerald' : 'text-ink',
                  )}
                >
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <WhatThisMeans>{meaning}</WhatThisMeans>
    </>
  );
}

// ── Rank Trend tab ────────────────────────────────────────────────────────────
function RankTab({ isin, head }: { isin: string; head: FundHead }) {
  const { data } = useFundAnalytics(isin);
  const points = data?.rank_history.data?.points ?? [];
  const ranks = points.map((p) => p.rank);
  const current = head.rank;
  const total = head.total;

  const best = ranks.length ? Math.min(...ranks, ...(current != null ? [current] : [])) : current;
  const avg = ranks.length ? Math.round(ranks.reduce((s, r) => s + r, 0) / ranks.length) : null;

  // Quartile band from this fund's rank/total (Q1 = top 25% of category).
  let q: number | null = null;
  if (current != null && total != null && total > 0) {
    q = Math.min(4, Math.max(1, Math.ceil((current / total) * 4)));
  }
  const quartileLabel = q != null ? `Q${q}` : '—';
  const bandName = q === 1 ? 'Great' : q === 2 ? 'Good' : q === 3 ? 'Average' : q === 4 ? 'Weak' : null;

  const cells = [
    { v: current != null ? `#${current}` : '—', l: 'Current' },
    { v: best != null ? `#${best}` : '—', l: 'Best (12mo)' },
    { v: avg != null ? `#${avg}` : '—', l: 'Avg (12mo)' },
    { v: quartileLabel, l: 'Quartile', tone: q === 1 ? ('emerald' as const) : undefined },
  ];

  const meaning = current != null && total != null
    ? `This fund's category rank has been tracked for ${points.length} month${points.length === 1 ? '' : 's'} and currently sits at #${current} of ${total}${bandName ? ` — in the "${bandName}" band` : ''}.`
    : "We don't have enough rank history yet to show a trend for this fund.";

  return (
    <>
      {/* 4-up rank cells — gap-px grid with bg-line wrapper */}
      <div className="mb-4 overflow-hidden rounded-2xl border border-line bg-line">
        <div className="grid grid-cols-2 gap-px sm:grid-cols-4">
          {cells.map((c) => (
            <div key={c.l} className="bg-surface px-3 py-4 text-center">
              <div
                className={cn(
                  'font-mono text-[20px] font-extrabold tracking-tight',
                  c.tone ? TONE_TEXT[c.tone] : 'text-ink',
                )}
              >
                {c.v}
              </div>
              <div className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.03em] text-ink-muted">
                {c.l}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Rank trend chart — real (W1) */}
      <DataState
        status={ranks.length >= 2 ? 'present' : 'empty'}
        emptyCopy="We need at least two months of rank history to plot a trend."
        skeleton={<Skeleton className="h-[150px] w-full rounded-xl" />}
      >
        <RankChart series={ranks} maxRank={total ?? 8} height={150} />
      </DataState>

      {/* Band strip — colours/labels are static design tokens; which band is "on" is real */}
      <div className="mt-3 flex gap-1.5">
        {RANK.bands.map((b) => (
          <div
            key={b.name}
            className={cn(
              'flex-1 rounded-lg py-1.5 text-center font-mono text-[11px] font-bold',
              b.name === bandName ? 'text-white' : 'text-ink-faint opacity-40',
            )}
            style={{ background: b.color }}
          >
            {b.name}
          </div>
        ))}
      </div>

      <WhatThisMeans>{meaning}</WhatThisMeans>
    </>
  );
}

// ── Drawdowns tab ─────────────────────────────────────────────────────────────
// Real (W2 §10.5) — worst fall/recovery/current-from-peak + the real drawdown chart.
function DrawdownsTab({ isin }: { isin: string }) {
  const { data, isLoading, isError, refetch } = useFundAnalytics(isin);
  const a = data?.analytics.data ?? null;
  const status = isLoading ? 'loading' : isError ? 'error' : (data?.analytics.status ?? 'empty');
  const series = a?.drawdown_series ?? [];
  const currentFromPeak = series.length ? series[series.length - 1].pct : null;

  const cells: { v: string; l: string; tone: 'red' | 'ink' }[] = [
    { v: a?.worst_fall_pct != null ? `${a.worst_fall_pct.toFixed(1)}%` : '—', l: 'Worst fall', tone: 'red' },
    {
      v: a?.recovery_days != null
        ? `${Math.round(a.recovery_days / 30)} mo`
        : a?.worst_fall_pct != null ? 'Not yet' : '—',
      l: 'Recovery time',
      tone: 'ink',
    },
    { v: currentFromPeak != null ? `${currentFromPeak.toFixed(1)}%` : '—', l: 'Current from peak', tone: 'red' },
  ];

  const meaning = a?.worst_fall_pct != null
    ? `This fund's worst historical fall was ${a.worst_fall_pct.toFixed(1)}%${
        a.recovery_days != null
          ? `, recovered in about ${Math.round(a.recovery_days / 30)} months`
          : ' and it has not yet recovered back to that peak'
      }. Only invest money you will not need during such dips.`
    : "We don't have enough price history yet to show this fund's drawdown history.";

  return (
    <>
      {/* 3-up stat cells */}
      <div className="mb-4 grid grid-cols-3 gap-3">
        {cells.map((c) => (
          <div key={c.l} className="rounded-xl bg-surface-2 py-4 text-center">
            <div className={cn('font-mono text-[15px] font-bold', TONE_TEXT[c.tone])}>
              {c.v}
            </div>
            <div className="mt-1 text-[10px] font-semibold text-ink-muted">{c.l}</div>
          </div>
        ))}
      </div>

      <DataState
        status={status}
        emptyCopy="We don't have enough price history yet to draw this chart."
        onRetry={refetch}
        skeleton={<Skeleton className="h-[150px] w-full rounded-xl" />}
      >
        <DrawdownChart series={series.map((p) => p.pct)} height={150} />
      </DataState>

      <WhatThisMeans>{meaning}</WhatThisMeans>
    </>
  );
}

// ── Consistency tab ───────────────────────────────────────────────────────────
// Real (W2 §10.5) — calendar-year quartile strip from `calendar_year_returns`.
function ConsistencyTab({ isin }: { isin: string }) {
  const { data, isLoading, isError, refetch } = useFundAnalytics(isin);
  const a = data?.analytics.data ?? null;
  const status = isLoading ? 'loading' : isError ? 'error' : (data?.analytics.status ?? 'empty');
  const years = a?.calendar_year_returns ?? [];
  const q1Count = years.filter((y) => y.quartile === 1).length;
  const consistencyWord = years.length === 0 ? '—'
    : q1Count / years.length >= 0.6 ? 'Strong'
    : q1Count / years.length >= 0.3 ? 'Moderate'
    : 'Mixed';

  const tiles: { v: string; l: string; tone: 'emerald' | 'ink' }[] = [
    { v: years.length ? `${q1Count}/${years.length}` : '—', l: 'Top-quartile years', tone: 'emerald' },
    { v: consistencyWord, l: 'Consistency', tone: consistencyWord === 'Strong' ? 'emerald' : 'ink' },
    {
      v: a?.rolling_1y_pct_positive != null ? `${a.rolling_1y_pct_positive.toFixed(0)}%` : '—',
      l: '1Y periods positive',
      tone: 'ink',
    },
  ];

  const meaning = years.length
    ? `Finished top-quartile in ${q1Count} of the last ${years.length} year${years.length === 1 ? '' : 's'} measured (quartile shown only where its category has published enough funds).`
    : "We don't have enough calendar-year history yet to show this fund's consistency.";

  return (
    <>
      <p className="mb-3 text-[12.5px] text-ink-muted">
        Quartile finish each calendar year (Q1 = top 25% of category):
      </p>

      <DataState
        status={status}
        emptyCopy="We don't have enough calendar-year history yet for this fund."
        onRetry={refetch}
        skeleton={<Skeleton className="h-24 w-full rounded-xl" />}
      >
        {/* Quartile strip */}
        <div className="mb-4 flex flex-wrap gap-2">
          {years.map((y) => (
            <div key={y.year} className="flex flex-col items-center gap-1">
              <div
                className={cn(
                  'h-9 w-9 rounded-lg text-center font-mono text-[13px] font-bold leading-9',
                  y.quartile ? QUARTILE_TONE[y.quartile] : 'bg-surface-2 text-ink-faint',
                )}
              >
                {y.quartile ? `Q${y.quartile}` : '—'}
              </div>
              <span className="text-[10px] font-semibold text-ink-muted">{y.year}</span>
            </div>
          ))}
        </div>

        {/* Tiles */}
        <div className="grid grid-cols-3 gap-3">
          {tiles.map((t) => (
            <div key={t.l} className="rounded-xl bg-surface-2 py-4 text-center">
              <div className={cn('font-mono text-[15px] font-bold', TONE_TEXT[t.tone])}>
                {t.v}
              </div>
              <div className="mt-1 text-[10px] font-semibold text-ink-muted">{t.l}</div>
            </div>
          ))}
        </div>

        <WhatThisMeans>{meaning}</WhatThisMeans>
      </DataState>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// S10 — PERFORMANCE CENTER
// ─────────────────────────────────────────────────────────────────────────────

export function PerformanceSection({ head, isin }: { head: FundHead; isin: string }) {
  const [tab, setTab] = React.useState('returns');
  // SIP/Drawdowns/Consistency are real as of W2 (§10.5); the Returns-tab
  // comparison table is real as of Fix 1 — only the Rolling-tab comparison
  // table stays preview (its own inline <PreviewBadge/>), so no tab-level
  // badge is needed.

  return (
    <Panel className="p-5 sm:p-6">
      <div className="flex items-center justify-between gap-3 mb-4">
        <TabBar tabs={PERF_TABS} active={tab} onChange={setTab} />
      </div>

      {tab === 'returns'   && <ReturnsTab head={head} isin={isin} />}
      {tab === 'sip'       && <SipTab isin={isin} />}
      {tab === 'rolling'   && <RollingTab isin={isin} />}
      {tab === 'rank'      && <RankTab isin={isin} head={head} />}
      {tab === 'drawdowns' && <DrawdownsTab isin={isin} />}
      {tab === 'consist'   && <ConsistencyTab isin={isin} />}
    </Panel>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// S12 — RISK CENTER
// ─────────────────────────────────────────────────────────────────────────────

// Percentile → risk-level word/tone (§16.2 stat-to-sentence translation, simplified).
function riskLevelWord(pct: number | null): { word: string; tone: 'emerald' | 'ink' | 'amber' | 'red' } {
  if (pct == null) return { word: '—', tone: 'ink' };
  if (pct < 25) return { word: 'Calmer than most', tone: 'emerald' };
  if (pct < 50) return { word: 'About average', tone: 'ink' };
  if (pct < 75) return { word: 'Swings more than most', tone: 'amber' };
  return { word: 'Among the most volatile', tone: 'red' };
}

// ponytail: these band rules are simple static heuristics (industry-standard Sharpe/
// Sortino cutoffs; volatility-percentile proxy for std-dev/max-drawdown favorability),
// not a per-metric category percentile — upgrade when a real per-metric percentile
// exists for each (rolling-3Y / alpha-beta wave, §10.5/§11).
function sharpeBand(v: number | null): Band3 {
  if (v == null) return 'medium';
  return v >= 1 ? 'high' : v >= 0.5 ? 'medium' : 'low';
}
function sortinoBand(v: number | null): Band3 {
  if (v == null) return 'medium';
  return v >= 1.5 ? 'high' : v >= 0.75 ? 'medium' : 'low';
}
function volFavorabilityBand(pct: number | null): Band3 {
  if (pct == null) return 'medium';
  return pct < 33 ? 'high' : pct < 66 ? 'medium' : 'low';
}
function maxDDBand(v: number | null): Band3 {
  if (v == null) return 'medium';
  return v > -10 ? 'high' : v > -25 ? 'medium' : 'low';
}

// Fix 2 (fund-page-quick-wins) — Max Drawdown stat-to-sentence. Honest basis:
// the category percentile band already served in
// fund.analytics.category_percentiles.max_drawdown_pct (mf_category_stats
// p25/p50/p75/p90, computed ascending-sorted over the raw negative
// max_drawdown_pct values — so p90 = smallest/least-negative fall = best,
// p25 = largest fall = worst). Sharpe/Sortino get NO sentence anywhere in
// this file: no category-relative or historical comparison basis is served
// for either metric today (only the static band heuristics above, which the
// code comment on them already flags as not a real percentile) — inventing
// one would be a fabricated comparison (§16.2).
function drawdownSentence(
  value: number | null | undefined,
  band: CategoryPercentileBand | undefined,
): string | null {
  if (value == null || !band || band.p25 == null || band.p75 == null) return null;
  if (value >= band.p75) return 'Its worst fall was smaller than most funds in its category.';
  if (value <= band.p25) return 'Its worst fall was larger than most funds in its category.';
  return 'Its worst fall was about typical for its category.';
}

export function RiskCenterSection({ isin }: { isin: string }) {
  const { data, isLoading, isError, refetch } = useFundAnalytics(isin);
  const a = data?.analytics.data ?? null;
  const health = data?.health.data ?? null;
  const envStatus = data?.analytics.status ?? 'empty';
  const allNull = a != null && a.sharpe_ratio == null && a.volatility_pct == null && a.max_drawdown_pct == null;
  const status = isLoading ? 'loading' : isError ? 'error' : (envStatus === 'present' && allNull ? 'empty' : envStatus);

  // §10.7 — the SAME engine that powers Fund Health also stat-to-sentence
  // translates a ratio; today only Risk (Std Deviation's exact input,
  // volatility_percentile) has a ready-made sentence — others stay tip-only
  // until their own health dimension exists.
  const riskDimensionNote = health?.lights.find((l) => l.name === 'Risk')?.note ?? null;

  const risk = riskLevelWord(a?.volatility_percentile ?? null);
  const simpleCells: { v: string; l: string; tone: 'amber' | 'red' | 'emerald' | 'ink'; sub?: string }[] = [
    {
      v: risk.word, l: 'Risk level', tone: risk.tone,
      sub: a?.volatility_percentile != null ? 'based on price swings vs category' : undefined,
    },
    { v: a?.worst_fall_pct != null ? `${a.worst_fall_pct.toFixed(1)}%` : '—', l: 'Worst fall', tone: 'red' },
    {
      v: a?.recovery_days != null
        ? `${Math.round(a.recovery_days / 30)} mo`
        : a?.worst_fall_pct != null ? 'Not yet' : '—',
      l: 'Recovery time',
      tone: 'ink',
    },
    { v: '—', l: 'Upside (good yr)', tone: 'emerald' },
    { v: '—', l: 'Downside (bad yr)', tone: 'red' },
    { v: a?.volatility_pct != null ? `${a.volatility_pct.toFixed(1)}%` : '—', l: 'Volatility (std dev)', tone: 'ink' },
  ];

  const advRows: { name: string; tip: string; real: boolean; value: string; band: Band3; note?: string | null }[] = [
    { name: 'Sharpe Ratio', tip: 'Return earned per unit of risk', real: a?.sharpe_ratio != null, value: a?.sharpe_ratio != null ? a.sharpe_ratio.toFixed(2) : '—', band: sharpeBand(a?.sharpe_ratio ?? null) },
    { name: 'Sortino Ratio', tip: 'Downside-adjusted return', real: a?.sortino_ratio != null, value: a?.sortino_ratio != null ? a.sortino_ratio.toFixed(2) : '—', band: sortinoBand(a?.sortino_ratio ?? null) },
    { name: 'Alpha', tip: 'Excess vs benchmark', real: a?.alpha_1y != null, value: a?.alpha_1y != null ? a.alpha_1y.toFixed(2) : '—', band: 'medium' },
    { name: 'Beta', tip: 'Moves with the index', real: a?.beta_1y != null, value: a?.beta_1y != null ? a.beta_1y.toFixed(2) : '—', band: 'medium' },
    { name: 'Tracking Error', tip: 'Index-tracking tightness', real: a?.tracking_error_pct != null, value: a?.tracking_error_pct != null ? `${a.tracking_error_pct.toFixed(1)}%` : '—', band: 'medium' },
    { name: 'Std Deviation', tip: 'Volatility', real: a?.volatility_pct != null, value: a?.volatility_pct != null ? `${a.volatility_pct.toFixed(1)}%` : '—', band: volFavorabilityBand(a?.volatility_percentile ?? null), note: riskDimensionNote },
    { name: 'Max Drawdown', tip: 'Worst peak-to-trough', real: a?.max_drawdown_pct != null, value: a?.max_drawdown_pct != null ? `${a.max_drawdown_pct.toFixed(1)}%` : '—', band: maxDDBand(a?.max_drawdown_pct ?? null), note: drawdownSentence(a?.max_drawdown_pct, a?.category_percentiles.max_drawdown_pct) },
    { name: 'Upside Capture', tip: 'Of index gains captured', real: false, value: '—', band: 'medium' },
    { name: 'Downside Capture', tip: 'Of index falls absorbed', real: false, value: '—', band: 'medium' },
    { name: 'Portfolio Turnover', tip: 'Trading frequency', real: false, value: '—', band: 'medium' },
  ];

  const riskMeaning = a?.sharpe_ratio != null
    ? `A Sharpe ratio of ${a.sharpe_ratio.toFixed(2)} means the return earned has, historically, been reasonably compensated for the risk taken — higher generally means better risk-adjusted return.`
    : "We don't have enough return history yet to compute this fund's risk-adjusted return.";

  return (
    <Panel className="p-5 sm:p-6">
      <DataState
        status={status}
        emptyCopy="We don't have risk data for this fund yet."
        onRetry={refetch}
        skeleton={<Skeleton className="h-40 w-full rounded-2xl" />}
      >
        {/* Simple risk grid — 3-col desktop / 2-col mobile */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 2xl:grid-cols-6">
          {simpleCells.map((r) => (
            <div key={r.l} className="rounded-xl bg-surface-2 px-3 py-4 text-center">
              <div className={cn('font-mono text-[15px] font-bold', TONE_TEXT[r.tone])}>
                {r.v}
              </div>
              <div className="mt-1 text-[10px] font-semibold text-ink-muted">{r.l}</div>
              {r.sub && <div className="mt-0.5 text-[9px] text-ink-faint">{r.sub}</div>}
            </div>
          ))}
        </div>

        {/* Advanced accordion */}
        <Accordion title={
          <>
            Advanced risk analytics{' '}
            <span className="ml-1.5 font-normal text-ink-faint text-[12px]">(10 metrics)</span>
          </>
        }>
          <div className="flex flex-col gap-3">
            {advRows.map((row) => (
              <div
                key={row.name}
                className="border-b border-line pb-3 last:border-b-0 last:pb-0"
              >
                <div className="flex items-center gap-3">
                  {/* Name + tip */}
                  <div className="flex min-w-[140px] shrink-0 items-center gap-1.5">
                    <span className="text-[12.5px] font-semibold text-ink">{row.name}</span>
                    <InfoTip tip={row.tip} />
                  </div>
                  {/* Decorative band bar (no %) — only for metrics we actually compute */}
                  <div className="flex-1">
                    {row.real ? (
                      <BandBar band={row.band} width={70} />
                    ) : (
                      <span className="text-caption text-ink-faint">Not available yet</span>
                    )}
                  </div>
                  {/* Factual value */}
                  <div className="w-[56px] shrink-0 text-right font-mono text-[12.5px] font-bold text-ink-secondary">
                    {row.value}
                  </div>
                </div>
                {/* Stat-to-sentence line (§10.7) — rendered only where a health
                    dimension already covers this exact metric (never fabricated). */}
                {row.note && (
                  <div className="mt-1.5 text-[11px] text-ink-faint">{row.note}</div>
                )}
              </div>
            ))}
          </div>
        </Accordion>

        <WhatThisMeans>{riskMeaning}</WhatThisMeans>
      </DataState>
    </Panel>
  );
}
