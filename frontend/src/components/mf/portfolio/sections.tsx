/**
 * Portfolio Command Center — section components.
 *
 * Each export is one numbered section of the approved PortfolioPageV1 mockup,
 * built responsive: tables scroll inside their card wrapper, grids collapse to
 * one column on phones, alloc tabs scroll horizontally.
 *
 * PURE-UI build — all values are illustrative preview data (sampleData.ts).
 * COMPLIANCE: BandRing+strength WORD for all composite scores (non-neg #2).
 *             Educational labels only — no advisory verbs (non-neg #1).
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { Logo, BandRing, BandRingFromBand, Semicircle, Donut, AreaChart, Card, SoWhat, RichText, StatusTag, RiskBadge, CTA, LABEL_DISPLAY, BAND_WORD, BAND_COLOR } from './ui';
import {
  COLORS, HERO, HEALTH, ACTIONS, DMMI_VAL, DMMI_MOOD, DMMI_PHASE, DMMI_METRICS,
  ALLOC, ALLOC_TABS, GOALS, PERF_DATA, PERF_PERIODS, HOLDINGS, TOP_PERF,
  UNDER_REVIEW, OVERLAP, DIV_SCORE, DIV_BARS, RISK_CARDS, ADV_METRICS,
  COST_CARDS, AMC_LIST, TIMELINE, RECS, PROJ, PROJ_TABS, WATCHLIST,
  AI_FEED, REPORTS, FAQ, BENEFITS, AUTOSYNC_PILLS,
  toStrength, ringColor, STRENGTH_WORD, STRENGTH_COLOR,
  type HealthLight,
} from './sampleData';
import { DataState } from '@/components/ui/DataState';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  usePortfolioHoldings,
  usePortfolioSummaryById,
  usePortfolioRisk,
  usePortfolioRiskAdvanced,
  type Holding,
} from '@/features/portfolio/api';

const { E, B, A, R, O } = COLORS;

// ── Light dot helper ─────────────────────────────────────────────────────────
const LIGHT_COLOR: Record<HealthLight, string> = { g: E, y: A, r: R };

// ── Priority badge ───────────────────────────────────────────────────────────
const PRI_LABEL = { high: 'High', med: 'Medium', low: 'Low' };
const PRI_COLOR = { high: R, med: A, low: B };

// ═══════════════════════════════════════════════════════════════════════════
// EMPTY STATE
// ═══════════════════════════════════════════════════════════════════════════

export function EmptyHero({ onViewSample }: { onViewSample: () => void }) {
  return (
    <div
      className="relative overflow-hidden rounded-[24px] p-8 text-white shadow-lg sm:p-10"
      style={{ background: 'linear-gradient(135deg,#0B1F3A 0%,#16335E 58%,#1E40AF 100%)' }}
    >
      <div className="pointer-events-none absolute -right-12 -top-16 h-80 w-80 rounded-full" style={{ background: 'radial-gradient(circle,rgba(212,160,23,.28),transparent 70%)' }} aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-32 left-[32%] h-72 w-72 rounded-full" style={{ background: 'radial-gradient(circle,rgba(37,99,235,.3),transparent 70%)' }} aria-hidden="true" />
      <div className="relative z-[2] flex flex-col items-center gap-5 text-center">
        <span className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-1.5 text-caption font-semibold text-slate-300">
          <span aria-hidden="true">📂</span> Upload your CAS to get started
        </span>
        <h1 className="font-sans text-[28px] font-extrabold leading-[1.05] tracking-[-0.03em] sm:text-[36px]">
          Your Portfolio Command Center
        </h1>
        <p className="max-w-[560px] text-small leading-relaxed text-slate-300 sm:text-body">
          Get a complete picture of your mutual fund portfolio — health score, overlap analysis, goal tracking, risk breakdown, and plain-English recommendations — in one place.
        </p>
        {/* Drop zone */}
        <div className="w-full max-w-sm rounded-2xl border-2 border-dashed border-white/30 bg-white/[0.04] p-8 transition-colors hover:border-white/50">
          <div className="flex flex-col items-center gap-2">
            <span className="text-4xl" aria-hidden="true">📄</span>
            <p className="text-small font-semibold text-white">Drop your CAS file here</p>
            <p className="text-caption text-slate-400">PDF or XML · CDSL / NSDL / CAMS</p>
            <CTA variant="primary" className="mt-2">Choose File</CTA>
          </div>
        </div>
        {/* CTAs */}
        <div className="flex flex-wrap justify-center gap-3">
          <button
            type="button"
            onClick={onViewSample}
            className="inline-flex items-center gap-2 rounded-xl border border-white/25 bg-white/10 px-4 py-2.5 text-small font-semibold text-white transition-colors hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
          >
            View Sample Portfolio →
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-xl border border-white/25 bg-white/10 px-4 py-2.5 text-small font-semibold text-white transition-colors hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
          >
            How it works
          </button>
        </div>
      </div>
    </div>
  );
}

export function BenefitsGrid() {
  return (
    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {BENEFITS.map((b) => (
        <div key={b.title} className="rounded-2xl border border-line bg-surface p-5 shadow-sm">
          <span className="mb-3 grid h-11 w-11 place-items-center rounded-xl text-xl" style={{ background: `${b.color}1A`, color: b.color }} aria-hidden="true">{b.icon}</span>
          <div className="text-small font-bold text-ink">{b.title}</div>
          <div className="mt-0.5 text-caption text-ink-muted">{b.desc}</div>
        </div>
      ))}
    </div>
  );
}

export function AutoSyncBanner() {
  return (
    <div className="rounded-2xl border border-line bg-surface-2 p-6 text-center">
      <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-violet/30 bg-violet/10 px-3 py-1 text-caption font-bold text-violet">
        <span aria-hidden="true">⚡</span> Coming Soon
      </div>
      <h2 className="mb-1.5 font-sans text-[20px] font-extrabold text-ink">Auto Sync — Always Up to Date</h2>
      <p className="mx-auto mb-4 max-w-[440px] text-small text-ink-secondary">
        Link your broker once and DhanRadar automatically refreshes your portfolio every day. No manual uploads needed.
      </p>
      <div className="mb-5 flex flex-wrap justify-center gap-2">
        {AUTOSYNC_PILLS.map((p) => (
          <span key={p} className="rounded-full border border-line bg-surface px-3 py-1 text-caption font-semibold text-ink-secondary">{p}</span>
        ))}
      </div>
      <CTA variant="primary">Notify Me When Live</CTA>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S1 — HERO (dashboard) — live data
// ═══════════════════════════════════════════════════════════════════════════

function fmtCurrency(n: number): string {
  const lakh = 100_000;
  return n >= lakh
    ? `₹${(n / lakh).toFixed(2)} L`
    : `₹${n.toLocaleString('en-IN')}`;
}

function fmtPct(n: number): string {
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}

export function HeroSection({ portfolioId }: { portfolioId: string }) {
  const { data: envelope, isLoading, isError, refetch } = usePortfolioSummaryById(portfolioId);

  const status = isLoading ? 'loading' : isError ? 'error' : (envelope?.status ?? 'empty');
  const summary = envelope?.data ?? null;
  const reason = envelope?.meta.reason ?? null;

  const heroGradient = 'linear-gradient(135deg,#0B1F3A 0%,#16335E 58%,#1E40AF 100%)';
  const band = summary?.confidence_band ?? null;

  return (
    <div
      className="relative overflow-hidden rounded-[24px] p-7 text-white shadow-lg sm:p-8"
      style={{ background: heroGradient }}
    >
      <div className="pointer-events-none absolute -right-12 -top-16 h-80 w-80 rounded-full" style={{ background: 'radial-gradient(circle,rgba(212,160,23,.28),transparent 70%)' }} aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-32 left-[32%] h-72 w-72 rounded-full" style={{ background: 'radial-gradient(circle,rgba(37,99,235,.3),transparent 70%)' }} aria-hidden="true" />
      <div className="relative z-[2]">
        <DataState
          status={status}
          reason={reason}
          emptyCopy="Upload your CAS to see your portfolio summary."
          onRetry={() => refetch()}
          skeleton={<Skeleton className="h-40 w-full rounded-xl bg-white/10" />}
        >
          {summary && (
            <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
              {/* Left: user's own money figures — allowed in DOM */}
              <div className="flex-1">
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Total Portfolio Value</div>
                <div className="font-sans text-[38px] font-extrabold leading-none tracking-tight sm:text-[46px]">
                  {fmtCurrency(summary.total_value)}
                </div>
                <div className="mt-1.5 inline-flex items-center gap-1.5 rounded-full bg-emerald-500/20 px-2.5 py-1 text-small font-bold text-emerald-300">
                  {summary.gain >= 0 ? '+' : ''}{fmtCurrency(Math.abs(summary.gain))} · {fmtPct(summary.gain_pct)}
                </div>
                <div className="mt-3 flex flex-wrap gap-4 text-small text-slate-300">
                  <span>Invested: <span className="font-bold text-white">{fmtCurrency(summary.total_invested)}</span></span>
                  {summary.xirr_pct !== null && (
                    <span>XIRR: <span className="font-bold text-emerald-300">{fmtPct(summary.xirr_pct)}</span></span>
                  )}
                </div>
                <div className="mt-3 flex flex-wrap gap-4 text-small text-slate-300">
                  <span>Funds: <span className="font-bold text-white">{summary.fund_count}</span></span>
                  <span>Scored: <span className="font-bold text-white">{summary.funds_scored}</span></span>
                </div>
              </div>
              {/* Right: BandRing (confidence_band) + plain word — NO advisory verdict, NO score */}
              <div className="text-center">
                <div className="relative inline-grid place-items-center">
                  <BandRingFromBand band={band} size={120} stroke={11} />
                  {/* ponytail: NO inner number — non-neg #2 */}
                </div>
                <div className="mt-2 font-sans text-[13px] font-bold text-slate-300">Data Confidence</div>
                <div className="mt-1 font-sans font-bold" style={{ color: band ? BAND_COLOR[band] : '#94A3B8', fontSize: 15 }}>
                  {band ? band.charAt(0).toUpperCase() + band.slice(1) : '—'}
                </div>
                <div className="mt-0.5 text-[11px] text-slate-400">{band ? BAND_WORD[band] : 'Confidence unavailable'}</div>
              </div>
            </div>
          )}
        </DataState>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S01 — HEALTH
// ═══════════════════════════════════════════════════════════════════════════
export function HealthSection() {
  return (
    <Card className="mt-4 p-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {HEALTH.map((h) => (
          <div key={h.title} className="rounded-xl border border-line bg-surface-2 p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11.5px] font-bold text-ink">{h.title}</span>
              <span
                className="h-2.5 w-2.5 rounded-full shrink-0"
                style={{ background: LIGHT_COLOR[h.light] }}
                aria-label={h.light === 'g' ? 'Good' : h.light === 'y' ? 'Watch' : 'Needs attention'}
              />
            </div>
            <div className="text-[13px] font-extrabold" style={{ color: LIGHT_COLOR[h.light] }}>{h.stat}</div>
            <div className="mt-1 text-caption text-ink-muted leading-relaxed">{h.exp}</div>
            <div className="mt-1.5 text-caption font-semibold text-ink-secondary">→ {h.tip}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S02 — ACTION CENTER
// ═══════════════════════════════════════════════════════════════════════════
export function ActionSection() {
  return (
    <Card className="mt-4 divide-y divide-line">
      {ACTIONS.map((a, i) => (
        <div key={i} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-start sm:gap-4">
          <div className="flex shrink-0 items-center gap-2 sm:w-20 sm:flex-col sm:items-start">
            <span
              className="rounded-md px-2 py-0.5 text-[10px] font-bold"
              style={{ background: `${PRI_COLOR[a.pri]}1A`, color: PRI_COLOR[a.pri] }}
            >
              {PRI_LABEL[a.pri]}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-bold text-ink">{a.title}</div>
            <div className="mt-0.5 text-small text-ink-secondary leading-relaxed">{a.desc}</div>
            <div className="mt-1.5 flex items-center gap-1.5 text-caption font-semibold text-ink-muted">
              <span className="text-emerald-500" aria-hidden="true">→</span>
              {a.impact}
            </div>
          </div>
          <CTA variant="ghost" className="shrink-0 self-start">{a.cta}</CTA>
        </div>
      ))}
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S03 — DMMI
// ═══════════════════════════════════════════════════════════════════════════
export function DmmiSection() {
  return (
    <Card className="mt-4 p-5">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        {/* Gauge — DMMI is a market index, numeric val=62 is allowed */}
        <div className="flex flex-col items-center gap-2 lg:w-52 lg:shrink-0">
          <Semicircle val={DMMI_VAL} size={200} />
          <div className="text-center">
            <div className="font-sans text-[16px] font-extrabold text-ink">{DMMI_MOOD}</div>
            <div className="text-caption text-ink-muted">{DMMI_PHASE}</div>
          </div>
        </div>
        {/* Metrics */}
        <div className="flex-1">
          <div className="mb-3 text-small font-bold text-ink">How this market affects your portfolio</div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {DMMI_METRICS.map((m) => (
              <div key={m.label} className="rounded-xl border border-line bg-surface-2 p-4">
                <div className="text-caption text-ink-muted">{m.label}</div>
                <div className="mt-0.5 font-sans text-[15px] font-extrabold" style={{ color: m.color }}>{m.value}</div>
                <div className="mt-1 text-caption text-ink-secondary leading-relaxed">{m.detail}</div>
              </div>
            ))}
          </div>
          <SoWhat>In the current accumulation phase, staying invested and continuing SIPs is historically the optimal move for equity-heavy portfolios like yours.</SoWhat>
        </div>
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S04 — ALLOCATION CENTER
// ═══════════════════════════════════════════════════════════════════════════
export function AllocSection() {
  const [tab, setTab] = React.useState(ALLOC_TABS[0]);
  const { rows, sowhat } = ALLOC[tab];

  return (
    <Card className="mt-4 p-5">
      {/* Tabs — horizontal scroll, hidden scrollbar */}
      <div className="flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {ALLOC_TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              'shrink-0 whitespace-nowrap rounded-lg px-3.5 py-2 text-caption font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
              tab === t ? 'bg-navy text-white' : 'text-ink-muted hover:bg-surface-2 hover:text-ink',
            )}
          >
            {t}
          </button>
        ))}
      </div>
      {/* Body — stacks on mobile, side-by-side on lg */}
      <div className="mt-5 flex flex-col gap-6 lg:grid lg:grid-cols-[1fr_1.2fr]">
        {/* Donut */}
        <div className="flex flex-col items-center gap-4">
          <Donut data={rows.map(([name, cur, , col]) => [name, cur, col] as [string, number, string])} size={200} thick={30} />
          {/* Legend */}
          <div className="flex flex-wrap justify-center gap-x-4 gap-y-1.5">
            {rows.map(([name, , , col]) => (
              <span key={name} className="flex items-center gap-1.5 text-caption text-ink-secondary">
                <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ background: col }} />
                {name}
              </span>
            ))}
          </div>
        </div>
        {/* Bars */}
        <div className="flex flex-col gap-3">
          {rows.map(([name, cur, ideal, col]) => {
            const diff = cur - ideal;
            const diffText = diff > 0 ? `+${diff.toFixed(1)}%` : `${diff.toFixed(1)}%`;
            const diffColor = Math.abs(diff) <= 3 ? E : diff > 0 ? O : B;
            return (
              <div key={name}>
                <div className="mb-1 flex items-center justify-between text-caption">
                  <span className="font-semibold text-ink">{name}</span>
                  <span className="font-mono font-bold" style={{ color: diffColor }}>{cur}% <span className="text-ink-faint">({diffText})</span></span>
                </div>
                <div className="relative h-2 overflow-hidden rounded-full bg-surface-3">
                  <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${Math.min(cur, 100)}%`, background: col }} />
                  {/* Ideal marker */}
                  <div className="absolute inset-y-0 w-0.5 bg-white/60" style={{ left: `${Math.min(ideal, 100)}%` }} />
                </div>
                <div className="mt-0.5 text-[10px] text-ink-faint">Ideal: {ideal}%</div>
              </div>
            );
          })}
          <SoWhat>{sowhat}</SoWhat>
        </div>
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S05 — GOAL TRACKER
// ═══════════════════════════════════════════════════════════════════════════
export function GoalSection() {
  return (
    <div className="mt-4 flex flex-col gap-3">
      {GOALS.map((g) => (
        <Card key={g.name} className="p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
            <span className="shrink-0 text-3xl" aria-hidden="true">{g.icon}</span>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-sans font-bold text-ink">{g.name}</span>
                <span className="text-caption text-ink-muted">{g.meta}</span>
                <span
                  className="rounded-full px-2.5 py-0.5 text-[10.5px] font-bold"
                  style={{ background: `${g.color}18`, color: g.color }}
                >
                  {g.status}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-3 sm:grid-cols-3">
                {[['Target', g.target], ['Current', g.current], ['Gap', g.gap]].map(([label, val]) => (
                  <div key={label}>
                    <div className="text-[10px] text-ink-faint uppercase tracking-wide font-semibold">{label}</div>
                    <div className="mt-0.5 font-sans font-extrabold text-ink">{val}</div>
                  </div>
                ))}
              </div>
              {/* Progress bar */}
              <div className="mt-3">
                <div className="mb-1 flex justify-between text-[10.5px] text-ink-muted">
                  <span>Progress</span><span className="font-bold" style={{ color: g.color }}>{g.pct}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-surface-3">
                  <div className="h-full rounded-full" style={{ width: `${g.pct}%`, background: g.color }} />
                </div>
              </div>
            </div>
          </div>
        </Card>
      ))}
      <button type="button" className="mt-1 self-start text-small font-semibold text-royal hover:underline focus-visible:outline-none">
        + Add a goal
      </button>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S06 — PERFORMANCE CENTER
// ═══════════════════════════════════════════════════════════════════════════
export function PerfSection() {
  const [period, setPeriod] = React.useState(3); // index into PERF_PERIODS

  return (
    <Card className="mt-4 p-5">
      {/* Period tabs */}
      <div className="flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {PERF_PERIODS.map((p, i) => (
          <button
            key={p}
            type="button"
            onClick={() => setPeriod(i)}
            className={cn(
              'shrink-0 whitespace-nowrap rounded-lg px-3.5 py-2 text-caption font-semibold transition-colors focus-visible:outline-none',
              period === i ? 'bg-navy text-white' : 'text-ink-muted hover:bg-surface-2 hover:text-ink',
            )}
          >
            {p}
          </button>
        ))}
      </div>
      {/* Performance rows */}
      <div className="mt-5 flex flex-col gap-3">
        {PERF_DATA.map((s) => {
          const val = s.vals[period];
          const pct = Math.min(Math.max(val / 25, 0), 1); // normalise to [0,1] for bar
          return (
            <div key={s.series} className="flex items-center gap-3">
              <span className="w-28 shrink-0 text-small font-semibold text-ink">{s.series}</span>
              <div className="flex-1 h-2.5 overflow-hidden rounded-full bg-surface-3">
                <div className="h-full rounded-full" style={{ width: `${pct * 100}%`, background: s.color }} />
              </div>
              <span className="w-14 shrink-0 text-right font-mono text-small font-bold" style={{ color: s.color }}>
                {val > 0 ? '+' : ''}{val}%
              </span>
            </div>
          );
        })}
      </div>
      {/* Perf chips */}
      <div className="mt-4 flex flex-wrap gap-2">
        {[
          { label: 'Beat benchmark', sub: 'on 3Y / 5Y', color: E },
          { label: 'XIRR 16.8%', sub: 'since start', color: E },
          { label: 'Category rank', sub: 'Top 22%', color: B },
        ].map((c) => (
          <div key={c.label} className="rounded-xl border border-line bg-surface-2 px-3.5 py-2.5">
            <div className="text-caption font-bold" style={{ color: c.color }}>{c.label}</div>
            <div className="text-[10px] text-ink-muted">{c.sub}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S07 — FUND HOLDINGS — live data
// ═══════════════════════════════════════════════════════════════════════════
const STATUS_FILTERS = ['All', 'In Form', 'On Track', 'Off Track', 'Out of Form'];

function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  const [search, setSearch] = React.useState('');
  const [filter, setFilter] = React.useState('All');

  const totalValue = holdings.reduce((s, h) => s + h.current_value, 0);

  const filtered = holdings.filter((h) => {
    const displayLabel = h.label ? LABEL_DISPLAY[h.label] : '';
    const matchSearch = h.scheme_name.toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === 'All' || displayLabel === filter;
    return matchSearch && matchFilter;
  });

  const fmt = (n: number) => `₹${(n / 100_000).toFixed(2)} L`;

  return (
    <>
      {/* Filters row */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search funds…"
          className="w-full rounded-xl border border-line bg-surface-2 px-3.5 py-2 text-small text-ink placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-royal/40 sm:w-64"
        />
        <div className="flex gap-1.5 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={cn(
                'shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-caption font-semibold transition-colors focus-visible:outline-none',
                filter === f ? 'bg-navy text-white' : 'border border-line bg-surface-2 text-ink-muted hover:text-ink',
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      {/* Table — horizontal scroll inside card */}
      <div className="overflow-x-auto">
        <table className="min-w-[900px] w-full border-collapse text-small">
          <thead>
            <tr className="border-b border-line text-left">
              {['Fund', 'Band', 'Label', 'Value', 'Invested', 'P&L', 'Weight'].map((col) => (
                <th key={col} className="whitespace-nowrap py-2.5 pr-4 font-mono text-[10px] font-bold uppercase tracking-wide text-ink-muted first:pl-0">{col}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {filtered.map((h) => {
              const gain = h.invested_amount !== null ? h.current_value - h.invested_amount : null;
              const gainColor = gain === null ? '#94A3B8' : gain >= 0 ? E : R;
              const weightPct = totalValue > 0 ? ((h.current_value / totalValue) * 100).toFixed(1) : '—';
              const displayLabel = h.label ? LABEL_DISPLAY[h.label] : 'Insufficient Data';
              return (
                <tr key={h.isin} className="group hover:bg-surface-2">
                  {/* Fund */}
                  <td className="py-3 pr-4">
                    <div>
                      <div className="font-semibold text-ink leading-tight max-w-[220px] truncate" title={h.scheme_name}>{h.scheme_name}</div>
                      <div className="text-[10px] text-ink-muted leading-tight">{h.category ?? '—'}</div>
                    </div>
                  </td>
                  {/* Band ring + word (confidence_band) — NO numeric score */}
                  <td className="py-3 pr-4">
                    <span className="inline-flex items-center gap-1.5">
                      <BandRingFromBand band={h.confidence_band} size={28} stroke={4} />
                      <span className="font-bold text-[11px]" style={{ color: h.confidence_band ? BAND_COLOR[h.confidence_band] : '#94A3B8' }}>
                        {h.confidence_band ? h.confidence_band.charAt(0).toUpperCase() + h.confidence_band.slice(1) : '—'}
                      </span>
                    </span>
                  </td>
                  {/* Educational label — no advisory verb */}
                  <td className="py-3 pr-4">
                    <StatusTag status={displayLabel} />
                  </td>
                  {/* User's own value — allowed */}
                  <td className="py-3 pr-4 font-mono font-bold text-ink">{fmt(h.current_value)}</td>
                  {/* User's own invested — allowed */}
                  <td className="py-3 pr-4 font-mono text-ink-secondary">{h.invested_amount !== null ? fmt(h.invested_amount) : '—'}</td>
                  {/* P&L — user's own — allowed */}
                  <td className="py-3 pr-4 font-mono font-bold" style={{ color: gainColor }}>
                    {gain !== null ? `${gain >= 0 ? '+' : ''}${fmt(Math.abs(gain))}` : '—'}
                  </td>
                  {/* Weight */}
                  <td className="py-3 pr-4 font-mono text-ink-secondary">{weightPct}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="py-8 text-center text-small text-ink-muted">No funds match your search or filter.</div>
        )}
      </div>
    </>
  );
}

export function HoldingsSection({ portfolioId }: { portfolioId: string }) {
  const { data: envelope, isLoading, isError, refetch } = usePortfolioHoldings(portfolioId);

  const status = isLoading ? 'loading' : isError ? 'error' : (envelope?.status ?? 'empty');
  const holdings = envelope?.data?.holdings ?? [];
  const reason = envelope?.meta.reason ?? null;

  return (
    <Card className="mt-4 p-5">
      <DataState
        status={status}
        reason={reason}
        emptyCopy="No holdings found. Upload your CAS statement to see your funds here."
        onRetry={() => refetch()}
        skeleton={
          <div className="flex flex-col gap-3">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full rounded-xl" />)}
          </div>
        }
      >
        <HoldingsTable holdings={holdings} />
      </DataState>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S08 — TOP PERFORMERS
// ═══════════════════════════════════════════════════════════════════════════
export function TopPerfSection() {
  return (
    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {TOP_PERF.map((t) => (
        <Card key={t.cat} className="p-4">
          <div className="mb-2 text-[10px] font-bold uppercase tracking-wide text-ink-faint">{t.cat}</div>
          <div className="flex items-center gap-2.5">
            <Logo letter={t.logo} color={t.color} size={32} radius={8} font={12} />
            <div className="min-w-0 flex-1">
              <div className="truncate text-small font-bold text-ink">{t.name}</div>
              <div className="text-caption font-extrabold" style={{ color: t.color }}>{t.val}</div>
            </div>
          </div>
          <div className="mt-2 text-caption text-ink-muted">{t.sub}</div>
        </Card>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S09 — FUNDS NEEDING REVIEW
// ═══════════════════════════════════════════════════════════════════════════
export function UnderReviewSection() {
  return (
    <div className="mt-4 flex flex-col gap-3">
      {UNDER_REVIEW.map((u) => (
        <Card key={u.name} className="p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
            <Logo letter={u.logo} color={u.color} size={40} radius={10} font={15} />
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="font-bold text-ink">{u.name}</span>
                <span
                  className="rounded-full px-2.5 py-0.5 text-[10.5px] font-bold"
                  style={{ background: `${u.color}18`, color: u.color }}
                >
                  {u.action}
                </span>
              </div>
              <p className="text-small text-ink-secondary leading-relaxed">{u.reason}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {u.tags.map((tag) => (
                  <span key={tag} className="rounded-md border border-line px-2 py-0.5 text-caption text-ink-muted">{tag}</span>
                ))}
              </div>
              <div className="mt-3 flex items-center gap-2 text-caption">
                <span className="text-ink-muted">Alternative:</span>
                <span className="font-semibold" style={{ color: u.altColor }}>{u.alt}</span>
              </div>
            </div>
            <CTA variant="ghost" className="shrink-0 self-start">{u.action}</CTA>
          </div>
        </Card>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S10 — OVERLAP ANALYSIS
// ═══════════════════════════════════════════════════════════════════════════
export function OverlapSection() {
  return (
    <div className="mt-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {OVERLAP.map((ov) => (
          <Card key={`${ov.aName}-${ov.bName}`} className="p-5">
            {/* Fund pair */}
            <div className="mb-3 flex items-center gap-3">
              <Logo letter={ov.aLogo} color={ov.aColor} size={32} radius={8} font={12} />
              <div className="text-caption text-ink-muted">vs</div>
              <Logo letter={ov.bLogo} color={ov.bColor} size={32} radius={8} font={12} />
              <div className="flex-1 min-w-0">
                <div className="truncate text-small font-bold text-ink">{ov.aName}</div>
                <div className="truncate text-caption text-ink-muted">{ov.bName}</div>
              </div>
            </div>
            {/* Overlap bar */}
            <div className="mb-2 flex items-center justify-between text-small">
              <span className="font-bold text-ink">Overlap</span>
              <span className="font-mono font-extrabold" style={{ color: ov.vColor }}>{ov.pct}%</span>
            </div>
            <div className="mb-3 h-2.5 overflow-hidden rounded-full bg-surface-3">
              <div className="h-full rounded-full" style={{ width: `${ov.pct}%`, background: ov.vColor }} />
            </div>
            <span
              className="mb-3 inline-flex items-center rounded-md px-2 py-0.5 text-[10.5px] font-bold"
              style={{ background: `${ov.vColor}18`, color: ov.vColor }}
            >
              {ov.verdict}
            </span>
            <SoWhat>{ov.rec}</SoWhat>
          </Card>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S11 — DIVERSIFICATION
// ═══════════════════════════════════════════════════════════════════════════
export function DivSection() {
  return (
    <Card className="mt-4 p-5">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-start">
        {/* Overall score as BandRing + strength WORD, NOT "78" */}
        <div className="text-center sm:w-48 sm:shrink-0">
          <div className="relative inline-grid place-items-center">
            <BandRing score={DIV_SCORE} size={140} stroke={12} />
          </div>
          <div className="mt-2 font-sans font-bold text-[20px]" style={{ color: ringColor(DIV_SCORE) }}>
            {STRENGTH_WORD[toStrength(DIV_SCORE)]}
          </div>
          <div className="text-[12px] text-ink-muted font-semibold mt-1">Overall Diversification</div>
          <div className="text-[11px] text-ink-faint mt-0.5">Top 18% of portfolios</div>
        </div>
        {/* Dimension bars */}
        <div className="flex-1 flex flex-col gap-4">
          {DIV_BARS.map((d) => (
            <div key={d.name}>
              <div className="mb-1.5 flex items-center justify-between text-small">
                <span className="font-semibold text-ink">{d.name}</span>
                <span className="font-mono font-bold text-ink-secondary">{d.cur}% <span className="text-ink-faint text-caption">/ {d.ideal}% ideal</span></span>
              </div>
              <div className="relative h-2.5 overflow-hidden rounded-full bg-surface-3">
                <div
                  className="absolute inset-y-0 left-0 rounded-full transition-all duration-500"
                  style={{ width: `${d.cur}%`, background: d.cur >= d.ideal - 5 ? E : d.cur >= d.ideal * 0.5 ? A : R }}
                />
                <div className="absolute inset-y-0 w-0.5 bg-white/60" style={{ left: `${d.ideal}%` }} />
              </div>
              <div className="mt-1 text-caption text-ink-muted">{d.tip}</div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S12 — RISK CENTER — live data
// COMPLIANCE: no numeric DhanRadar composite score (non-neg #2).
//             Standard ratios (Sharpe/Sortino/volatility/max-drawdown) ARE
//             allowed and DO render — they are NOT the composite (non-neg #2).
//             risk_band renders as a badge+word only, never a number.
//             No advisory verbs (non-neg #1).
// ═══════════════════════════════════════════════════════════════════════════

/** Maps backend risk_band → display word for RiskBadge (factual descriptors, not advisory verbs). */
const RISK_BAND_DISPLAY: Record<string, string> = {
  low:       'Low',
  moderate:  'Moderate',
  high:      'High',
  very_high: 'Very High',
};

/** Maps backend risk_band → a confidence Band3 so BandRingFromBand can render it. */
const RISK_BAND_TO_CONF: Record<string, 'high' | 'medium' | 'low'> = {
  low:       'high',
  moderate:  'medium',
  high:      'low',
  very_high: 'low',
};

function fmtPctRisk(n: number | null, prefix = '±'): string {
  if (n === null) return '—';
  return `${prefix}${Math.abs(n).toFixed(1)}%`;
}

/** Shared "coming soon" card for fields not yet built server-side. */
function ComingSoonCard({ label, desc }: { label: string; desc: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface-2 p-4">
      <div className="text-caption text-ink-muted">{label}</div>
      <div className="mt-0.5 font-sans text-[15px] font-extrabold text-ink-faint">— Coming soon</div>
      <div className="mt-1 text-caption text-ink-secondary">{desc}</div>
    </div>
  );
}

function AdvancedPanel({ portfolioId, open }: { portfolioId: string; open: boolean }) {
  const { data: envelope, isLoading, isError, error, refetch } = usePortfolioRiskAdvanced(portfolioId, open);

  // 402 = free user hitting a Plus-only endpoint — render upgrade card, never hide
  // ponytail: duck-type .problem.status; avoids importing ApiError into sections.tsx
  const is402 = isError && (error as { problem?: { status?: number } } | null)?.problem?.status === 402;
  const status = isLoading ? 'loading' : is402 ? 'withheld' : isError ? 'error' : (envelope?.status ?? 'empty');
  const adv = envelope?.data ?? null;

  return (
    <DataState
      status={status}
      reason={is402 ? 'tier' : (envelope?.meta.reason ?? null)}
      tierCopy="Advanced risk metrics — available on DhanRadar Plus"
      onRetry={() => refetch()}
      skeleton={
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}
        </div>
      }
    >
      {adv && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {/* Standard ratios — DOM-allowed */}
          {/* B88: a true portfolio Sharpe/Sortino needs the portfolio return series (not built) —
              averaging per-fund ratios is meaningless, so defer rather than show a wrong number. */}
          <ComingSoonCard label="Sharpe Ratio" desc="Return per unit of total risk. Needs your portfolio return history — being built." />
          <ComingSoonCard label="Sortino Ratio" desc="Return per unit of downside risk. Needs your portfolio return history — being built." />
          <div className="rounded-xl border border-line bg-surface-2 p-4">
            <div className="text-caption text-ink-muted">Rolling 1Y Avg</div>
            <div className="mt-0.5 font-mono text-[15px] font-extrabold text-ink">{fmtPctRisk(adv.rolling_1y_avg_pct, '')}</div>
            <div className="mt-1 text-caption text-ink-secondary">Average 1-year rolling return.</div>
          </div>
          {/* B88: a per-fund hit-rate (% positive windows) doesn't value-aggregate to a portfolio figure
              (depends on correlation/timing) — deferred like Sharpe/Sortino until the valuation series. */}
          <ComingSoonCard label="Positive 1Y Windows" desc="% of 1-year periods with positive returns. Needs your portfolio return history — being built." />
          {/* alpha/beta always null server-side — render as coming soon */}
          <ComingSoonCard label="Alpha" desc="Excess return vs benchmark. Being built." />
          <ComingSoonCard label="Beta" desc="Market sensitivity measure. Being built." />
        </div>
      )}
    </DataState>
  );
}

export function RiskSection({ portfolioId }: { portfolioId: string }) {
  const [advOpen, setAdvOpen] = React.useState(false);
  const { data: envelope, isLoading, isError, refetch } = usePortfolioRisk(portfolioId);

  const status = isLoading ? 'loading' : isError ? 'error' : (envelope?.status ?? 'empty');
  const risk = envelope?.data ?? null;
  const reason = envelope?.meta.reason ?? null;
  const bandDisplay = risk?.risk_band ? (RISK_BAND_DISPLAY[risk.risk_band] ?? risk.risk_band) : null;
  const bandConf = risk?.risk_band ? (RISK_BAND_TO_CONF[risk.risk_band] ?? null) : null;

  return (
    <Card className="mt-4 p-5">
      <DataState
        status={status}
        reason={reason}
        emptyCopy="Risk data will appear once your portfolio has enough NAV history."
        onRetry={() => refetch()}
        skeleton={
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}
          </div>
        }
      >
        {risk && (
          <>
            {/* Risk band row — badge+word only, NO numeric score (non-neg #2) */}
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="flex items-center gap-3">
                <BandRingFromBand band={bandConf} size={48} stroke={6} />
                <div>
                  <div className="text-caption text-ink-muted">Risk Level</div>
                  {bandDisplay
                    ? <RiskBadge risk={bandDisplay} />
                    : <span className="text-[10.5px] font-bold text-ink-faint">Insufficient data</span>
                  }
                  {bandDisplay && risk.risk_band_basis && (
                    <div className="mt-0.5 text-[10px] text-ink-faint">Indicative — based on {risk.risk_band_basis}</div>
                  )}
                </div>
              </div>
              {risk.as_of && (
                <span className="text-[10px] text-ink-faint sm:ml-auto">As of {risk.as_of}</span>
              )}
            </div>

            {/* Standard ratio cards — DOM-allowed (non-neg #2 exempts standard ratios) */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-xl border border-line bg-surface-2 p-4">
                <div className="text-caption text-ink-muted">Price Swings</div>
                <div className="mt-0.5 font-mono text-[18px] font-extrabold text-ink">{fmtPctRisk(risk.volatility_pct)}</div>
                <div className="mt-1 text-caption text-ink-secondary">Average annualised volatility of your funds (indicative).</div>
              </div>
              {/* B88: portfolio drawdown doesn't aggregate linearly (fund falls happen at different times)
                  — needs the portfolio valuation series (not built). Defer, don't show a wrong number. */}
              <ComingSoonCard label="Biggest Fall" desc="Largest peak-to-trough decline. Needs your portfolio valuation history — being built." />
              {/* recovery_months always null — render as coming soon (NO-SUPPRESS) */}
              <ComingSoonCard label="Recovery Time" desc="Average months to recover from a drawdown. Being built." />
              <div className="rounded-xl border border-line bg-surface-2 p-4">
                <div className="text-caption text-ink-muted">Coverage</div>
                <div className="mt-0.5 font-mono text-[15px] font-extrabold text-ink">
                  {risk.funds_with_metrics}/{risk.fund_count} funds
                </div>
                <div className="mt-1 text-caption text-ink-secondary">Funds with enough data for risk metrics.</div>
              </div>
            </div>
          </>
        )}
      </DataState>

      {/* Advanced metrics accordion */}
      <div className="mt-4">
        <button
          type="button"
          onClick={() => setAdvOpen((v) => !v)}
          className="flex w-full items-center justify-between rounded-xl border border-line bg-surface-2 px-4 py-3 text-small font-semibold text-ink hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
        >
          Advanced Risk Metrics <span className="text-[10px] text-violet font-bold ml-1.5">Plus</span>
          <span aria-hidden="true" className="ml-2 text-ink-faint">{advOpen ? '▲' : '▼'}</span>
        </button>
        {advOpen && (
          <div className="mt-2">
            <AdvancedPanel portfolioId={portfolioId} open={advOpen} />
          </div>
        )}
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S13 — COST ANALYSIS
// ═══════════════════════════════════════════════════════════════════════════
export function CostSection() {
  return (
    <Card className="mt-4 p-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {COST_CARDS.map((c) => (
          <div key={c.label} className="rounded-xl border border-line bg-surface-2 p-4">
            <div className="text-caption text-ink-muted">{c.label}</div>
            <div className="mt-0.5 font-sans text-[20px] font-extrabold" style={{ color: c.color }}>{c.value}</div>
          </div>
        ))}
      </div>
      <SoWhat>
        At 0.80% weighted expense ratio you are already below the industry average of 1.2%. Moving your 2 priciest funds to their direct plan equivalents could save another ₹8,000/yr.
      </SoWhat>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S14 — AMC EXPOSURE
// ═══════════════════════════════════════════════════════════════════════════
export function AmcSection() {
  return (
    <Card className="mt-4 p-5">
      <div className="flex flex-col gap-3">
        {AMC_LIST.map((amc) => (
          <div key={amc.name} className="flex items-center gap-4">
            <Logo letter={amc.logo} color={amc.color} size={32} radius={8} font={12} />
            <div className="w-20 shrink-0">
              <div className="font-bold text-ink">{amc.name}</div>
              <div className="text-caption text-ink-muted">{amc.pct}% of portfolio</div>
            </div>
            <div className="flex-1">
              <div className="h-2 overflow-hidden rounded-full bg-surface-3">
                <div className="h-full rounded-full bg-royal" style={{ width: `${(amc.pct / 30) * 100}%` }} />
              </div>
            </div>
            {/* Quality renders as WORD, not raw qualityScore number */}
            <span
              className="shrink-0 rounded-md px-2 py-0.5 text-[10.5px] font-bold"
              style={{ background: `${amc.qualityScore >= 88 ? E : amc.qualityScore >= 84 ? B : A}18`, color: amc.qualityScore >= 88 ? E : amc.qualityScore >= 84 ? B : A }}
            >
              {amc.qualityWord}
            </span>
          </div>
        ))}
      </div>
      <SoWhat>No single AMC exceeds 22% — your fund house spread is healthy. Invesco is the weakest link at Fair quality; it is still acceptable at 8% exposure.</SoWhat>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S15 — PORTFOLIO TIMELINE
// ═══════════════════════════════════════════════════════════════════════════
export function TimelineSection() {
  return (
    <Card className="mt-4 p-5">
      <div className="relative flex flex-col gap-0">
        {/* Vertical line */}
        <div className="absolute left-[19px] top-5 bottom-5 w-px bg-line" aria-hidden="true" />
        {TIMELINE.map((ev, i) => (
          <div key={i} className="relative flex gap-4 pb-6 last:pb-0">
            {/* Icon dot */}
            <div
              className="relative z-[1] grid h-10 w-10 shrink-0 place-items-center rounded-full text-[14px] font-bold text-white"
              style={{ background: ev.color }}
              aria-hidden="true"
            >
              {ev.icon}
            </div>
            <div className="pt-1.5">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">{ev.date}</div>
              <div className="mt-0.5 font-bold text-ink">{ev.title}</div>
              <div className="text-caption text-ink-secondary">{ev.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S16 — RECOMMENDATIONS
// ═══════════════════════════════════════════════════════════════════════════
export function RecSection() {
  return (
    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
      {RECS.map((rec, i) => (
        <Card key={i} className="p-5">
          <div className="mb-1.5 font-bold text-ink">{rec.title}</div>
          <p className="text-small text-ink-secondary leading-relaxed">{rec.desc}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {rec.tags.map((tag) => (
              <span
                key={tag.text}
                className="rounded-full px-2.5 py-0.5 text-[10.5px] font-bold"
                style={{ background: `${tag.color}18`, color: tag.color }}
              >
                {tag.text}
              </span>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S17 — FUTURE WEALTH PROJECTION
// ═══════════════════════════════════════════════════════════════════════════
export function ProjSection() {
  const [yr, setYr] = React.useState(PROJ_TABS[1]); // default: 10 Years
  const scenarios = PROJ[yr];

  return (
    <Card className="mt-4 p-5">
      {/* Year tabs */}
      <div className="mb-5 flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {PROJ_TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setYr(t)}
            className={cn(
              'shrink-0 whitespace-nowrap rounded-lg px-4 py-2 text-caption font-semibold transition-colors focus-visible:outline-none',
              yr === t ? 'bg-navy text-white' : 'text-ink-muted hover:bg-surface-2 hover:text-ink',
            )}
          >
            {t}
          </button>
        ))}
      </div>
      {/* Chart */}
      <div className="mb-5 overflow-hidden rounded-xl bg-surface-2 p-3">
        <AreaChart seed={yr.length * 7} color={E} width={520} height={180} />
      </div>
      {/* Scenarios */}
      <div className="flex flex-col gap-2.5">
        {scenarios.map((s, i) => (
          <div key={i} className="flex items-center justify-between rounded-xl border border-line bg-surface-2 px-4 py-3">
            <div className="flex items-center gap-2.5">
              <span className="h-3 w-3 rounded-full shrink-0" style={{ background: s.color }} aria-hidden="true" />
              <span className="text-small font-semibold text-ink">{s.name}</span>
            </div>
            <span className="font-sans font-extrabold" style={{ color: s.color }}>{s.val}</span>
          </div>
        ))}
      </div>
      <SoWhat>These projections assume a 15% annualised return (your current XIRR) and that SIPs continue uninterrupted. Actual returns will vary with market conditions.</SoWhat>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S18 — OPPORTUNITIES
// ═══════════════════════════════════════════════════════════════════════════
export function OpportunitiesSection() {
  return (
    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {WATCHLIST.map((w) => (
        <Card key={w.name} className="p-5 flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Logo letter={w.logo} color={w.color} size={36} radius={9} font={13} />
            <div className="min-w-0 flex-1">
              <div className="truncate font-bold text-ink">{w.name}</div>
            </div>
          </div>
          <p className="text-small text-ink-secondary leading-relaxed">{w.why}</p>
          <ul className="flex flex-col gap-1">
            {w.benefits.map((b) => (
              <li key={b} className="flex items-center gap-1.5 text-caption text-ink-secondary">
                <span className="text-emerald-500 font-bold shrink-0">✓</span> {b}
              </li>
            ))}
          </ul>
          <CTA variant="ghost" className="mt-auto self-start">View fund →</CTA>
        </Card>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S19 — AI INSIGHTS FEED
// ═══════════════════════════════════════════════════════════════════════════
export function AiSection() {
  return (
    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
      {AI_FEED.map((text, i) => (
        <Card key={i} className="p-5">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-[13px]" aria-hidden="true">🤖</span>
            <span className="text-[10px] font-bold uppercase tracking-wide text-ink-faint">DhanRadar AI</span>
          </div>
          <p className="text-small text-ink-secondary leading-relaxed">
            <RichText text={text} />
          </p>
        </Card>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S20 — REPORT CENTER
// ═══════════════════════════════════════════════════════════════════════════
export function ReportSection() {
  return (
    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {REPORTS.map((rep) => (
        <Card key={rep.title} className="p-5 flex flex-col items-center gap-3 text-center cursor-pointer hover:border-royal transition-colors">
          <span
            className="grid h-12 w-12 place-items-center rounded-xl text-[22px]"
            style={{ background: `${rep.color}18`, color: rep.color }}
            aria-hidden="true"
          >
            {rep.icon}
          </span>
          <div>
            <div className="font-bold text-ink">{rep.title}</div>
            <div className="text-caption text-ink-muted">{rep.desc}</div>
          </div>
          <CTA variant="ghost" className="w-full text-center">Generate</CTA>
        </Card>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S21 — FAQ
// ═══════════════════════════════════════════════════════════════════════════
export function FaqSection() {
  const [open, setOpen] = React.useState<number | null>(0);
  return (
    <div className="mt-4 flex flex-col gap-2">
      {FAQ.map(([q, a], i) => (
        <div key={i} className="overflow-hidden rounded-xl border border-line bg-surface">
          <button
            type="button"
            onClick={() => setOpen(open === i ? null : i)}
            className="flex w-full items-center justify-between px-5 py-4 text-left text-small font-semibold text-ink hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
            aria-expanded={open === i}
          >
            {q}
            <span className="ml-3 shrink-0 text-ink-faint transition-transform" style={{ transform: open === i ? 'rotate(180deg)' : 'none' }} aria-hidden="true">▼</span>
          </button>
          {open === i && (
            <div className="border-t border-line px-5 pb-5 pt-3 text-small text-ink-secondary leading-relaxed">{a}</div>
          )}
        </div>
      ))}
    </div>
  );
}

// suppress unused import warnings — O is used in PRI_COLOR
void O;
