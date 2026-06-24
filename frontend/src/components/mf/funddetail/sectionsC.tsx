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
import {
  Panel, TabBar, ChipToggle, StackBar, FlowBars, BandBar, WhatThisMeans,
} from './parts';
import {
  HOLD_STOCKS, HOLD_SECTORS, HOLD_CAP, HOLD_ASSET, HOLD_CAP_NOTE,
  STYLE_BOX, FLOW, MANAGER, AMC,
} from './sampleData';

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

// 3×3 style-box column labels (bottom row only)
const STYLE_COL_LABELS = ['Value', 'Blend', 'Growth'];

function HoldingsStocksPane() {
  return (
    <div>
      {HOLD_STOCKS.map((s) => (
        <div
          key={s.ticker}
          className="flex items-center gap-3 border-b border-line py-2.5 last:border-b-0"
        >
          {/* avatar */}
          <FundAvatar name={s.ticker} size="sm" />

          {/* name + sector */}
          <div className="min-w-0 flex-1">
            <div className="text-small font-semibold text-ink leading-tight truncate">{s.name}</div>
            <div className="text-caption text-ink-muted">{s.sector}</div>
          </div>

          {/* daily chg */}
          <span
            className={cn(
              'w-12 shrink-0 text-right font-mono text-caption font-semibold',
              s.chg >= 0 ? 'text-emerald' : 'text-red',
            )}
          >
            {s.chg >= 0 ? '+' : ''}{s.chg}%
          </span>

          {/* weight bar */}
          <div
            className="hidden h-[7px] w-[70px] shrink-0 overflow-hidden rounded bg-surface-2 sm:block"
            aria-hidden="true"
          >
            <div
              className="h-full rounded"
              style={{
                width: `${(s.wt / 1.9) * 100}%`,
                background: 'var(--dr-royal,#1E5EFF)',
              }}
            />
          </div>

          {/* weight % */}
          <span className="w-10 shrink-0 text-right font-mono text-small font-semibold text-ink">
            {s.wt}%
          </span>
        </div>
      ))}

      <button
        className={cn(
          'mt-3 w-full rounded-xl border border-line bg-surface-2 px-4 py-2.5',
          'text-small font-semibold text-ink-muted transition-colors hover:text-ink',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
        )}
      >
        View all 250 holdings →
      </button>
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

function StyleBoxPane() {
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

export function HoldingsSection() {
  const [tab, setTab] = React.useState('stocks');

  return (
    <Panel className="p-5 sm:p-6">
      <TabBar tabs={HOLD_TABS} active={tab} onChange={setTab} />

      <div className="mt-4">
        {tab === 'stocks' && <HoldingsStocksPane />}

        {tab === 'sectors' && (
          <div>
            <StackBar items={HOLD_SECTORS} />
            <LegendList items={HOLD_SECTORS} />
          </div>
        )}

        {tab === 'cap' && (
          <div>
            <StackBar items={HOLD_CAP} />
            <LegendList items={HOLD_CAP} />
            <p className="mt-3 text-caption leading-relaxed text-ink-muted">{HOLD_CAP_NOTE}</p>
          </div>
        )}

        {tab === 'asset' && (
          <div>
            <StackBar items={HOLD_ASSET} />
            <LegendList items={HOLD_ASSET} />
          </div>
        )}

        {tab === 'style' && <StyleBoxPane />}
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

export function ManagerSection() {
  return (
    <Panel className="p-5 sm:p-6">
      {/* header row */}
      <div className="flex flex-wrap items-center gap-4">
        {/* gradient avatar */}
        <div
          className="grid h-[62px] w-[62px] shrink-0 place-items-center rounded-2xl text-[22px] font-bold text-white"
          style={{ background: 'linear-gradient(135deg,#2563EB,#10B981)' }}
          aria-hidden="true"
        >
          {MANAGER.initials}
        </div>

        {/* name + sub */}
        <div className="min-w-0 flex-1">
          <div className="text-body font-bold text-ink leading-tight">{MANAGER.name}</div>
          <div className="mt-0.5 text-caption text-ink-muted">{MANAGER.sub}</div>
        </div>

        {/* 4-up stat grid */}
        <div className="flex flex-wrap gap-5 sm:gap-6">
          {MANAGER.stats.map((s) => (
            <div key={s.l} className="text-center">
              <div
                className={cn(
                  'font-mono text-[17px] font-bold leading-none',
                  s.tone ? (TONE_TEXT[s.tone] ?? 'text-ink') : 'text-ink',
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

      <WhatThisMeans>{MANAGER.meaning}</WhatThisMeans>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S16 — AMC QUALITY
// ═══════════════════════════════════════════════════════════════════════════

export function AmcSection({ amcName = 'This fund house' }: { amcName?: string }) {
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
        </div>

        {/* 4-up stat grid */}
        <div className="flex flex-wrap gap-5 sm:gap-6">
          {AMC.stats.map((s) => (
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
