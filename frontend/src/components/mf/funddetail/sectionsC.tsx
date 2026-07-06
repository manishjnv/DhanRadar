/**
 * Fund Detail V3 — Sections C: Holdings, Fund Flow, Manager, AMC.
 * S13 · S14 · S15 · S16
 *
 * COMPLIANCE (hard, CI-enforced):
 *   - NO DhanRadar score / grade / percentile in DOM (non-neg #2).
 *     AMC "bars" are decorative educational bands — no numeric value rendered.
 *   - NO advisory verbs (non-neg #1).
 *   - Portfolio weights %, AUM ₹Cr, tracking error %, flows ₹Cr are FACTUAL → allowed.
 *   - Chart/legend colors sourced from sampleData item.color (data-viz palette, allowed via style).
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { FundAvatar } from '@/components/mf/explore/FundAvatar';
import { useFundComposition, useFundPeople } from '@/features/mf/api';
import { DataState } from '@/components/ui/DataState';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  Panel, TabBar, ChipToggle, StackBar, FlowBars, BandBar, WhatThisMeans,
} from './parts';
import { FLOW, AMC, HOLD_CAP, HOLD_ASSET, HOLD_CAP_NOTE, STYLE_BOX } from './sampleData';

// ─── shared helpers ──────────────────────────────────────────────────────────

const TONE_TEXT: Record<string, string> = {
  emerald: 'text-emerald',
  red: 'text-red',
  amber: 'text-amber',
  cyan: 'text-cyan',
  royal: 'text-royal',
  ink: 'text-ink',
};

// ═══════════════════════════════════════════════════════════════════════════
// S13 — HOLDINGS
// ═══════════════════════════════════════════════════════════════════════════

const HOLD_TABS = [
  { key: 'stocks',  label: 'Top Holdings' },
  { key: 'sectors', label: 'Sectors' },
  { key: 'cap',     label: 'Market Cap' },
  { key: 'asset',   label: 'Asset Mix' },
  { key: 'style',   label: 'Style Box' },
];

/** Real top-holdings pane (W1). The per-stock daily-change column isn't sourced yet
 * (would need a live equity-price feed) — shows "—" rather than a fabricated %. */
function HoldingsStocksPane({ holdings, maxWeight }: { holdings: { name: string; sector: string | null; weight_pct: number | null }[]; maxWeight: number }) {
  return (
    <div>
      {holdings.map((s) => (
        <div
          key={s.name}
          className="flex items-center gap-3 border-b border-line py-2.5 last:border-b-0"
        >
          {/* avatar */}
          <FundAvatar name={s.name} size="sm" />

          {/* name + sector */}
          <div className="min-w-0 flex-1">
            <div className="text-small font-semibold text-ink leading-tight truncate">{s.name}</div>
            <div className="text-caption text-ink-muted">{s.sector ?? 'Sector not disclosed'}</div>
          </div>

          {/* daily chg — not sourced yet (needs a live equity-price feed, W2+) */}
          <span className="w-12 shrink-0 text-right font-mono text-caption font-semibold text-ink-faint">
            —
          </span>

          {/* weight bar */}
          <div
            className="hidden h-[7px] w-[70px] shrink-0 overflow-hidden rounded bg-surface-2 sm:block"
            aria-hidden="true"
          >
            <div
              className="h-full rounded"
              style={{
                width: `${maxWeight > 0 ? ((s.weight_pct ?? 0) / maxWeight) * 100 : 0}%`,
                background: 'var(--dr-royal,#1E5EFF)',
              }}
            />
          </div>

          {/* weight % */}
          <span className="w-10 shrink-0 text-right font-mono text-small font-semibold text-ink">
            {s.weight_pct != null ? `${s.weight_pct}%` : '—'}
          </span>
        </div>
      ))}
    </div>
  );
}

function LegendList({ items }: { items: { name: string; wt: number; color: string }[] }) {
  return (
    <div>
      {items.map((it) => (
        <div
          key={it.name}
          className="flex items-center gap-2.5 border-b border-line py-2 last:border-b-0 text-small"
        >
          {/* color swatch */}
          <span
            className="h-2.5 w-2.5 shrink-0 rounded-sm"
            style={{ background: it.color }}
            aria-hidden="true"
          />
          <span className="flex-1 font-medium text-ink">{it.name}</span>
          <span className="font-mono font-semibold text-ink-secondary">{it.wt}%</span>
        </div>
      ))}
    </div>
  );
}

// Deterministic sector-legend palette (data-viz colors, cycled — not fabricated data).
const SECTOR_COLORS = ['#1E5EFF', '#00C2FF', '#00B386', '#F5A623', '#F97316', '#0B1F3A', '#64748B'];

// ─── Preview panes preserved, not rendered (founder no-deletion rule 2026-07-04) ────
// Market Cap / Asset Mix / Style Box need a stock master we don't have (plan §11), so
// their tabs show an honest no-data state. The built panes stay here, exported, to be
// re-wired with real data in W3 — do not delete.

const STYLE_COL_LABELS = ['Value', 'Blend', 'Growth'];

export function CapMixPreviewPane() {
  return (
    <div>
      <StackBar items={HOLD_CAP} />
      <LegendList items={HOLD_CAP} />
      <p className="mt-3 text-caption leading-relaxed text-ink-muted">{HOLD_CAP_NOTE}</p>
    </div>
  );
}

export function AssetMixPreviewPane() {
  return (
    <div>
      <StackBar items={HOLD_ASSET} />
      <LegendList items={HOLD_ASSET} />
    </div>
  );
}

export function StyleBoxPane() {
  return (
    <div className="flex flex-col items-center">
      <p className="mb-4 text-caption text-ink-muted self-start">
        Morningstar-style box — where the portfolio sits by size &amp; style:
      </p>

      {/* 3×3 grid */}
      <div
        className="grid gap-1"
        style={{ gridTemplateColumns: 'repeat(3, 1fr)', maxWidth: 260 }}
        role="grid"
        aria-label="Style box"
      >
        {Array.from({ length: 9 }).map((_, i) => {
          const isHot = i === STYLE_BOX.hotIndex;
          const isBottomRow = i >= 6;
          const colLabel = isBottomRow ? STYLE_COL_LABELS[i - 6] : '';
          return (
            <div
              key={i}
              role="gridcell"
              aria-selected={isHot}
              className={cn(
                'flex aspect-[1.4] items-center justify-center rounded-md border text-caption font-bold',
                isHot
                  ? 'border-transparent text-white'
                  : 'border-line bg-surface-2 text-ink-faint',
              )}
              style={isHot ? { background: 'var(--dr-royal,#1E5EFF)' } : undefined}
            >
              {isHot ? '●' : colLabel}
            </div>
          );
        })}
      </div>

      <p className="mt-3 text-caption text-ink-muted">{STYLE_BOX.caption}</p>
    </div>
  );
}

export function HoldingsSection({ isin }: { isin: string }) {
  const [tab, setTab] = React.useState('stocks');
  const { data: env, isLoading, isError, refetch } = useFundComposition(isin);
  const composition = env?.data ?? null;
  const rawStatus = isLoading ? 'loading' : isError ? 'error' : (env?.status ?? 'empty');
  const hasHoldings = (composition?.holdings.length ?? 0) > 0;
  // Present-but-zero-holdings (uncovered AMC) reads as empty; loading/error pass through.
  const status = rawStatus === 'present' && !hasHoldings ? 'empty' : rawStatus;

  const maxWeight = composition?.holdings.reduce((m, h) => Math.max(m, h.weight_pct ?? 0), 0) ?? 0;
  const sectorItems = (composition?.sectors ?? []).map((s, i) => ({
    name: s.name, wt: s.weight_pct, color: SECTOR_COLORS[i % SECTOR_COLORS.length],
  }));

  return (
    <Panel className="p-5 sm:p-6">
      <TabBar tabs={HOLD_TABS} active={tab} onChange={setTab} />

      <div className="mt-4">
        {(tab === 'stocks' || tab === 'sectors') && (
          <DataState
            status={status}
            emptyCopy="This fund house doesn't publish holdings where we can read them yet."
            onRetry={refetch}
            skeleton={<Skeleton className="h-48 w-full rounded-xl" />}
          >
            {tab === 'stocks' && (
              <HoldingsStocksPane holdings={composition?.holdings ?? []} maxWeight={maxWeight} />
            )}
            {tab === 'sectors' && (
              <div>
                <StackBar items={sectorItems} />
                <LegendList items={sectorItems} />
              </div>
            )}
          </DataState>
        )}

        {/* Market Cap / Asset Mix / Style Box — need a stock master we don't have (blocked, §11) */}
        {(tab === 'cap' || tab === 'asset' || tab === 'style') && (
          <DataState status="empty" emptyCopy="We don't have this breakdown yet.">
            <></>
          </DataState>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S14 — FUND FLOW INTELLIGENCE
// ═══════════════════════════════════════════════════════════════════════════

export function FundFlowSection() {
  const [range, setRange] = React.useState(FLOW.ranges[2]); // default 1Y

  const rangeOpts = FLOW.ranges.map((r) => ({ key: r, label: r }));

  return (
    <Panel className="p-5 sm:p-6">
      {/* range toggle */}
      <ChipToggle
        options={rangeOpts}
        active={range}
        onChange={setRange}
      />

      {/* 3-up stat grid */}
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {FLOW.cells.map((c) => (
          <div
            key={c.l}
            className="rounded-2xl border border-line p-3.5 text-center"
          >
            <div
              className={cn(
                'font-mono text-[17px] font-bold leading-none',
                c.tone ? (TONE_TEXT[c.tone] ?? 'text-ink') : 'text-ink',
              )}
            >
              {c.v}
            </div>
            <div className="mt-1 text-caption font-semibold text-ink-muted">{c.l}</div>
          </div>
        ))}
      </div>

      {/* chart wrapper */}
      <div className="mt-4 rounded-xl border border-line p-3.5" style={{ background: 'linear-gradient(180deg,#fff,#FAFBFD)' }}>
        <div className="mb-2 text-caption font-semibold text-ink-muted">
          Net monthly flows · last 12 months (₹ Cr)
        </div>
        <FlowBars series={FLOW.series} />
      </div>

      {/* badge row */}
      <div className="mt-3.5 flex flex-wrap items-center gap-2.5">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald px-2.5 py-1 text-caption font-semibold text-emerald">
          <span
            className="grid h-3.5 w-3.5 shrink-0 place-items-center rounded-full bg-emerald text-[9px] text-white"
            aria-hidden="true"
          >
            ✓
          </span>
          {FLOW.badge}
        </span>
        <span className="text-small text-ink-muted">{FLOW.badgeNote}</span>
      </div>

      <WhatThisMeans>{FLOW.meaning}</WhatThisMeans>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S15 — FUND MANAGER
// ═══════════════════════════════════════════════════════════════════════════

export function ManagerSection({ isin }: { isin: string }) {
  const { data, isLoading, isError, refetch } = useFundPeople(isin);
  const people = data?.people.data ?? null;
  const managers = people?.managers ?? [];
  const status = isLoading ? 'loading' : isError ? 'error' : (managers.length ? 'present' : 'empty');

  const name = managers.map((m) => m.name).join(' & ') || null;
  const initials = managers.slice(0, 2).map((m) => m.name.trim()[0] ?? '').join('').toUpperCase() || '—';
  const tenureYears = managers.length ? Math.max(...managers.map((m) => m.tenure_years)) : null;
  const sub = managers.length > 1 ? `Co-managing · ${managers.length} managers` : managers.length === 1 ? 'Fund manager' : undefined;

  // The longest-tenured manager with a computed tenure_return_pct (facts only,
  // no advisory framing) — omitted server-side when NAV history doesn't reach
  // back to their start_date (fail-closed), so this may be undefined.
  const tenureReturnManager = managers.length
    ? managers.reduce((longest, m) => (m.tenure_years > longest.tenure_years ? m : longest), managers[0])
    : null;
  const tenureReturnPct = tenureReturnManager?.tenure_return_pct;
  const tenureReturnAsOf = tenureReturnManager?.tenure_return_as_of;

  const stats = [
    { v: tenureYears != null ? `${tenureYears.toFixed(1)}y` : '—', l: 'Tenure' },
    { v: '—', l: 'Avg tracking err' },
    { v: '—', l: 'Manager quality' },
    { v: people ? String(people.manager_changes_5y) : '—', l: 'Mgr changes' },
  ];

  const meaning = name
    ? `${name} ${managers.length > 1 ? 'have' : 'has'} been managing this fund${tenureYears != null ? ` for about ${tenureYears.toFixed(1)} years` : ''}. Manager changes are tracked because turnover can affect consistency.`
    : "We don't have fund manager information for this fund house yet.";

  return (
    <Panel className="p-5 sm:p-6">
      <DataState
        status={status}
        emptyCopy="We don't have fund manager information for this fund house yet."
        onRetry={refetch}
        skeleton={<Skeleton className="h-24 w-full rounded-2xl" />}
      >
        {/* header row */}
        <div className="flex flex-wrap items-center gap-4">
          {/* gradient avatar */}
          <div
            className="grid h-[62px] w-[62px] shrink-0 place-items-center rounded-2xl text-[22px] font-bold text-white"
            style={{ background: 'linear-gradient(135deg,#2563EB,#10B981)' }}
            aria-hidden="true"
          >
            {initials}
          </div>

          {/* name + sub */}
          <div className="min-w-0 flex-1">
            <div className="text-body font-bold text-ink leading-tight">{name ?? '—'}</div>
            {sub && <div className="mt-0.5 text-caption text-ink-muted">{sub}</div>}
          </div>

          {/* 4-up stat grid */}
          <div className="flex flex-wrap gap-5 sm:gap-6">
            {stats.map((s) => (
              <div key={s.l} className="text-center">
                <div className="font-mono text-[17px] font-bold leading-none text-ink">
                  {s.v}
                </div>
                <div className="mt-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
                  {s.l}
                </div>
              </div>
            ))}
          </div>
        </div>

        {tenureReturnPct != null && tenureReturnManager && (
          <div className="mt-3 text-small text-ink">
            Return since {tenureReturnManager.name} took over:{' '}
            <span className="font-mono font-semibold">
              {tenureReturnPct > 0 ? '+' : ''}
              {tenureReturnPct.toFixed(1)}%
            </span>
            {tenureReturnAsOf && (
              <span className="text-ink-muted"> (as of {tenureReturnAsOf})</span>
            )}
          </div>
        )}

        <WhatThisMeans>{meaning}</WhatThisMeans>
      </DataState>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S16 — AMC QUALITY
// ═══════════════════════════════════════════════════════════════════════════

export function AmcSection({ isin, amcName = 'This fund house' }: { isin: string; amcName?: string }) {
  const { data } = useFundPeople(isin);
  const amc = data?.amc.data ?? null;
  const factsLine = amc
    ? `${amc.scheme_count} scheme${amc.scheme_count === 1 ? '' : 's'} across ${amc.category_count} categor${amc.category_count === 1 ? 'y' : 'ies'} on DhanRadar`
    : null;
  // "Total AUM" is source-blocked (B67/ADR-0035) — never fabricate it; every other
  // stat stays the existing decorative preview (no numeric DhanRadar score, non-neg #2).
  const stats = AMC.stats.map((s) => (s.l === 'Total AUM' ? { ...s, v: '—' } : s));

  return (
    <Panel className="p-5 sm:p-6">
      {/* header row */}
      <div className="flex flex-wrap items-center gap-3.5">
        {/* square logo block */}
        <div
          className="grid h-[54px] w-[54px] shrink-0 place-items-center rounded-2xl bg-surface-2 text-[18px] font-bold"
          style={{ color: 'var(--dr-navy,#0B1F3A)' }}
          aria-hidden="true"
        >
          {AMC.initial}
        </div>

        {/* title + sub */}
        <div className="min-w-0 flex-1">
          <div className="text-body font-bold text-ink leading-tight">{amcName}</div>
          <div className="mt-0.5 text-caption text-ink-muted">{AMC.est}</div>
          {factsLine && <div className="mt-0.5 text-caption font-semibold text-ink-secondary">{factsLine}</div>}
        </div>

        {/* 4-up stat grid */}
        <div className="flex flex-wrap gap-5 sm:gap-6">
          {stats.map((s) => (
            <div key={s.l} className="text-center">
              <div
                className={cn(
                  'font-mono text-[17px] font-bold leading-none',
                  'tone' in s && s.tone ? (TONE_TEXT[s.tone] ?? 'text-ink') : 'text-ink',
                )}
              >
                {s.v}
              </div>
              <div className="mt-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
                {s.l}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* bar rows — decorative bands only, NO numeric value rendered (non-neg #2) */}
      <div className="mt-5 flex flex-col gap-3">
        {AMC.bars.map((b) => (
          <div key={b.l} className="flex items-center gap-3">
            <span className="w-[140px] shrink-0 text-small text-ink-secondary font-medium">
              {b.l}
            </span>
            {/* BandBar is decorative — width controlled by band word, no number shown */}
            <BandBar band={b.band} width={120} />
          </div>
        ))}
      </div>

      <WhatThisMeans>{AMC.meaning}</WhatThisMeans>
    </Panel>
  );
}
