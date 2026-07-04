/**
 * Fund Detail V3 — Sections B: Snapshot · Performance · Risk Center.
 *
 * COMPLIANCE: factual stats (returns %, Sharpe, drawdown %, rank, quartile) are
 * DOM-allowed. NO DhanRadar composite score numbers, no advisory verbs
 * (buy/sell/hold/avoid/caution/switch).
 *
 * W1 (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §17): Returns/Rolling/Rank-Trend tabs
 * and the whole Risk Center are wired to real data (`fund.nav_series`,
 * `fund.analytics`, `fund.rank_history`, plus the existing Nifty 50 benchmark
 * endpoint reused from the portfolio-vs-market chart). SIP/Drawdowns/Consistency
 * stay sampleData preview (W2) — PreviewBadge shows only on those tabs now.
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { useFundNav, useFundAnalytics } from '@/features/mf/api';
import { useNiftyCloseSeries } from '@/features/portfolio/api';
import { DataState } from '@/components/ui/DataState';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  TabBar, ChipToggle, Accordion, BandBar, InfoTip, Panel,
  WhatThisMeans, PreviewBadge, GrowthChart, RankChart, DrawdownChart,
  TONE_TEXT,
} from './parts';
import {
  SNAPSHOT,
  RETURN_TABLE, RETURN_TABLE_HEAD, GROWTH, SIP, ROLLING, RANK, DRAWDOWN, CONSISTENCY,
} from './sampleData';
import type { Band3 } from './sampleData';
import type { FundHead } from './sectionsHero';

// ─────────────────────────────────────────────────────────────────────────────
// S9 — INVESTMENT SNAPSHOT
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 4-col desktop / 2-col mobile KPI grid with 1px-gap dividers via gap-px +
 * bg-line wrapper (cells are bg-surface). Each cell: label + InfoTip, mono
 * value, optional coloured sub-line.
 */
export function SnapshotSection() {
  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-line">
      <div className="grid grid-cols-2 gap-px sm:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-7">
        {SNAPSHOT.map((item) => (
          <div key={item.l} className="bg-surface px-4 py-3.5 sm:px-[15px]">
            {/* label + tip */}
            <div className="flex items-center gap-1.5">
              <span className="text-[10.5px] font-semibold text-ink-muted">{item.l}</span>
              <InfoTip tip={item.tip} />
            </div>
            {/* value */}
            <div className="mt-1.5 font-mono text-[15px] font-bold text-ink">{item.v}</div>
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

// ── Returns tab ──────────────────────────────────────────────────────────────
function ReturnsTab({ head, isin }: { head: FundHead; isin: string }) {
  const [uiRange, setUiRange] = React.useState(GROWTH.ranges[2]); // default 5Y
  const apiRange = RANGE_TO_API[uiRange] ?? '5y';

  const { data: navEnv, isLoading: navLoading } = useFundNav(isin, apiRange);
  const navData = navEnv?.data ?? null;
  const { data: benchSeries } = useNiftyCloseSeries(
    navData ? { from: navData.from ?? undefined, to: navData.to ?? undefined } : undefined,
  );

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

      {/* Comparison table — preview (fund/benchmark/category-avg 1Y/3Y/5Y/Launch table;
          not trivially fillable from what W1 serves without scope-creep, §10.5 W2). */}
      <div className="mt-4 flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">vs benchmark &amp; category</span>
        <PreviewBadge />
      </div>
      <table className="mt-2 w-full border-collapse text-[12.5px]">
        <thead>
          <tr>
            {RETURN_TABLE_HEAD.map((h, i) => (
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
          {RETURN_TABLE.map((row) => (
            <tr key={row.row}>
              <td
                className={cn(
                  'border-b border-line py-2.5 pr-2 font-semibold last:border-b-0',
                  row.me ? 'text-royal' : 'text-ink-secondary',
                )}
              >
                {row.row}
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
            Benchmark (Nifty 50)
          </span>
        </div>
      </div>

      <WhatThisMeans>
        This chart shows how {GROWTH.invested} invested at the start of the selected period would
        have grown, next to the Nifty 50 price index (excludes dividends) for comparison.
      </WhatThisMeans>
    </>
  );
}

// ── SIP Growth tab ────────────────────────────────────────────────────────────
function SipTab() {
  const [selected, setSelected] = React.useState(SIP.amounts[0].key);
  const current = SIP.amounts.find((a) => a.key === selected) ?? SIP.amounts[0];

  return (
    <>
      {/* Amount chips */}
      <div className="mb-4">
        <ChipToggle
          options={SIP.amounts.map((a) => ({ key: a.key, label: a.label }))}
          active={selected}
          onChange={setSelected}
        />
      </div>

      {/* Result panel */}
      <div className="mb-4 flex items-start justify-between rounded-2xl bg-emerald/[0.08] p-4">
        <div>
          <div className="text-[11px] font-semibold text-ink-muted">{current.sub}</div>
          <div className="mt-1 font-mono text-[24px] font-extrabold tracking-tight text-emerald">
            {current.val}
          </div>
        </div>
        <div className="text-right">
          <div className="text-[11px] font-semibold text-ink-muted">Gain</div>
          <div className="font-mono text-[15px] font-bold text-emerald">{current.gain}</div>
          <div className="font-mono text-[12px] text-emerald">{current.xirr}</div>
        </div>
      </div>

      {/* SIP tiles */}
      <div className="grid grid-cols-3 gap-2">
        {SIP.tiles.map((t) => (
          <div key={t.p} className="rounded-xl border border-line bg-surface py-3 text-center">
            <div className="text-[10.5px] font-semibold text-ink-muted">{t.p}</div>
            <div className="mt-1 font-mono text-[14px] font-bold text-emerald">{t.v}</div>
          </div>
        ))}
      </div>

      <WhatThisMeans>{SIP.meaning}</WhatThisMeans>
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

  const meaning = a?.rolling_1y_pct_positive != null
    ? `Rolling returns test every holding period, not just lucky start dates. This fund's 1-year rolling return was positive in about ${a.rolling_1y_pct_positive.toFixed(0)}% of the periods measured.`
    : "Rolling returns test every holding period, not just lucky start dates — we don't have enough history yet to measure this fund's rolling-return consistency.";

  return (
    <>
      {/* Tiles — real (W1) */}
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {tiles.map((t) => (
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
function DrawdownsTab() {
  return (
    <>
      {/* 3-up stat cells */}
      <div className="mb-4 grid grid-cols-3 gap-3">
        {DRAWDOWN.cells.map((c) => (
          <div key={c.l} className="rounded-xl bg-surface-2 py-4 text-center">
            <div className={cn('font-mono text-[15px] font-bold', TONE_TEXT[c.tone])}>
              {c.v}
            </div>
            <div className="mt-1 text-[10px] font-semibold text-ink-muted">{c.l}</div>
          </div>
        ))}
      </div>

      <DrawdownChart height={150} />

      <WhatThisMeans>{DRAWDOWN.meaning}</WhatThisMeans>
    </>
  );
}

// ── Consistency tab ───────────────────────────────────────────────────────────
const QUARTILE_COLOR: Record<string, string> = {
  Q1: 'bg-emerald text-white',
  Q2: 'bg-amber text-white',
  Q3: 'bg-red/70 text-white',
  Q4: 'bg-red text-white',
};

function ConsistencyTab() {
  return (
    <>
      <p className="mb-3 text-[12.5px] text-ink-muted">{CONSISTENCY.intro}</p>

      {/* Quartile strip */}
      <div className="mb-4 flex flex-wrap gap-2">
        {CONSISTENCY.strip.map((s) => (
          <div key={s.y} className="flex flex-col items-center gap-1">
            <div
              className={cn(
                'h-9 w-9 rounded-lg text-center font-mono text-[13px] font-bold leading-9',
                QUARTILE_COLOR[s.q] ?? 'bg-surface-2 text-ink',
              )}
            >
              {s.q}
            </div>
            <span className="text-[10px] font-semibold text-ink-muted">{s.y}</span>
          </div>
        ))}
      </div>

      {/* Tiles — use sampleData (compliance: no numeric DhanRadar score) */}
      <div className="grid grid-cols-3 gap-3">
        {CONSISTENCY.tiles.map((t) => (
          <div key={t.l} className="rounded-xl bg-surface-2 py-4 text-center">
            <div className={cn('font-mono text-[15px] font-bold', TONE_TEXT[t.tone])}>
              {t.v}
            </div>
            <div className="mt-1 text-[10px] font-semibold text-ink-muted">{t.l}</div>
          </div>
        ))}
      </div>

      <WhatThisMeans>{CONSISTENCY.meaning}</WhatThisMeans>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// S10 — PERFORMANCE CENTER
// ─────────────────────────────────────────────────────────────────────────────

export function PerformanceSection({ head, isin }: { head: FundHead; isin: string }) {
  const [tab, setTab] = React.useState('returns');
  const isPreviewTab = tab === 'sip' || tab === 'drawdowns' || tab === 'consist';

  return (
    <Panel className="p-5 sm:p-6">
      <div className="flex items-center justify-between gap-3 mb-4">
        <TabBar tabs={PERF_TABS} active={tab} onChange={setTab} />
        {isPreviewTab && <PreviewBadge className="shrink-0" />}
      </div>

      {tab === 'returns'   && <ReturnsTab head={head} isin={isin} />}
      {tab === 'sip'       && <SipTab />}
      {tab === 'rolling'   && <RollingTab isin={isin} />}
      {tab === 'rank'      && <RankTab isin={isin} head={head} />}
      {tab === 'drawdowns' && <DrawdownsTab />}
      {tab === 'consist'   && <ConsistencyTab />}
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

export function RiskCenterSection({ isin }: { isin: string }) {
  const { data, isLoading, isError, refetch } = useFundAnalytics(isin);
  const a = data?.analytics.data ?? null;
  const envStatus = data?.analytics.status ?? 'empty';
  const allNull = a != null && a.sharpe_ratio == null && a.volatility_pct == null && a.max_drawdown_pct == null;
  const status = isLoading ? 'loading' : isError ? 'error' : (envStatus === 'present' && allNull ? 'empty' : envStatus);

  const risk = riskLevelWord(a?.volatility_percentile ?? null);
  const simpleCells: { v: string; l: string; tone: 'amber' | 'red' | 'emerald' | 'ink'; sub?: string }[] = [
    {
      v: risk.word, l: 'Risk level', tone: risk.tone,
      sub: a?.volatility_percentile != null ? 'based on price swings vs category' : undefined,
    },
    { v: a?.max_drawdown_pct != null ? `${a.max_drawdown_pct.toFixed(1)}%` : '—', l: 'Worst fall', tone: 'red' },
    { v: '—', l: 'Recovery time', tone: 'ink' },
    { v: '—', l: 'Upside (good yr)', tone: 'emerald' },
    { v: '—', l: 'Downside (bad yr)', tone: 'red' },
    { v: a?.volatility_pct != null ? `${a.volatility_pct.toFixed(1)}%` : '—', l: 'Volatility (std dev)', tone: 'ink' },
  ];

  const advRows: { name: string; tip: string; real: boolean; value: string; band: Band3 }[] = [
    { name: 'Sharpe Ratio', tip: 'Return earned per unit of risk', real: a?.sharpe_ratio != null, value: a?.sharpe_ratio != null ? a.sharpe_ratio.toFixed(2) : '—', band: sharpeBand(a?.sharpe_ratio ?? null) },
    { name: 'Sortino Ratio', tip: 'Downside-adjusted return', real: a?.sortino_ratio != null, value: a?.sortino_ratio != null ? a.sortino_ratio.toFixed(2) : '—', band: sortinoBand(a?.sortino_ratio ?? null) },
    { name: 'Alpha', tip: 'Excess vs benchmark', real: false, value: '—', band: 'medium' },
    { name: 'Beta', tip: 'Moves with the index', real: false, value: '—', band: 'medium' },
    { name: 'Tracking Error', tip: 'Index-tracking tightness', real: false, value: '—', band: 'medium' },
    { name: 'Std Deviation', tip: 'Volatility', real: a?.volatility_pct != null, value: a?.volatility_pct != null ? `${a.volatility_pct.toFixed(1)}%` : '—', band: volFavorabilityBand(a?.volatility_percentile ?? null) },
    { name: 'Max Drawdown', tip: 'Worst peak-to-trough', real: a?.max_drawdown_pct != null, value: a?.max_drawdown_pct != null ? `${a.max_drawdown_pct.toFixed(1)}%` : '—', band: maxDDBand(a?.max_drawdown_pct ?? null) },
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
                className="flex items-center gap-3 border-b border-line pb-3 last:border-b-0 last:pb-0"
              >
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
            ))}
          </div>
        </Accordion>

        <WhatThisMeans>{riskMeaning}</WhatThisMeans>
      </DataState>
    </Panel>
  );
}
