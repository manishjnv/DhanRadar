/**
 * Fund Detail V3 — Section group A (S4, S5, S7, S8).
 *
 * COMPLIANCE: no 0–100 numeric score/grade/percentile/weight rendered.
 * No advisory verbs (buy/sell/hold/avoid/caution/switch) as visible text,
 * string literals, or object keys. Factual values (%, ₹, NAV) are allowed.
 * All content comes from sampleData exports — nothing invented here.
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { Panel, WhatThisMeans, PreviewBadge, TONE_TEXT } from './parts';
import { FIT, MINE, HEALTH, CHANGES } from './sampleData';

// ═══════════════════════════════════════════════════════════════════════════
// S4 — PORTFOLIO FIT
// ═══════════════════════════════════════════════════════════════════════════
export function PortfolioFitSection() {
  // Allocation bar geometry — all values come from sampleData FIT constants.
  // Map [0, 20]% exposure range → [0, 100]% track width (max shown = 20%).
  const RANGE_MAX = 20; // max % shown on the track
  const curFill   = (FIT.currentPct / RANGE_MAX) * 100;
  const aftFill   = (FIT.afterPct   / RANGE_MAX) * 100;
  const recLeft   = (FIT.recLow     / RANGE_MAX) * 100;
  const recRight  = ((RANGE_MAX - FIT.recHigh) / RANGE_MAX) * 100; // right edge inset

  return (
    <Panel className="p-5 sm:p-6">
      {/* card header: icon + match word + preview badge */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {/* green icon pill */}
          <span
            aria-hidden="true"
            className="grid h-11 w-11 shrink-0 place-items-center rounded-[13px] bg-emerald/10 text-emerald"
          >
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.9"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
              focusable="false"
            >
              <path d="M20 6 L9 17 L4 12" />
            </svg>
          </span>
          <div>
            <div className="font-mono text-[19px] font-extrabold text-emerald leading-none">
              {FIT.match}
            </div>
            <div className="mt-1 text-caption text-ink-muted">{FIT.matchSub}</div>
          </div>
        </div>
        <PreviewBadge />
      </div>

      {/* Allocation bar */}
      <div className="mt-5">
        <div className="mb-2 flex justify-between text-[11px] font-semibold text-ink-muted">
          <span>Small-cap exposure</span>
          <span>Recommended {FIT.recLow}–{FIT.recHigh}%</span>
        </div>
        <div className="relative h-8 overflow-hidden rounded-[9px] bg-surface-2">
          {/* recommended band (emerald tint, dashed borders) */}
          <div
            aria-hidden="true"
            className="absolute inset-y-0 border-l-2 border-r-2 border-dashed border-emerald bg-emerald/10"
            style={{ left: `${recLeft}%`, right: `${recRight}%` }}
          />
          {/* current fill (royal blue) */}
          <div
            aria-hidden="true"
            className="absolute inset-y-0 left-0 rounded-l-[9px]"
            style={{ width: `${curFill}%`, background: 'var(--dr-royal,#1E5EFF)' }}
          />
          {/* after fill (royal blue tint) */}
          <div
            aria-hidden="true"
            className="absolute inset-y-0"
            style={{
              left:  `${curFill}%`,
              width: `${aftFill - curFill}%`,
              background: 'rgba(30,94,255,0.35)',
            }}
          />
        </div>
        {/* legend */}
        <div className="mt-3 flex flex-wrap gap-4 text-[11.5px] text-ink-muted">
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block h-2.5 w-2.5 shrink-0 rounded-[2px]"
              style={{ background: 'var(--dr-royal,#1E5EFF)' }}
            />
            Current {FIT.currentPct}%
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block h-2.5 w-2.5 shrink-0 rounded-[2px] bg-royal/40"
            />
            After {FIT.afterPct}%
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block h-2.5 w-2.5 shrink-0 rounded-[2px] bg-emerald/50"
            />
            Recommended {FIT.recLow}–{FIT.recHigh}%
          </span>
        </div>
      </div>

      {/* 3-up stat row */}
      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {FIT.stats.map((s) => (
          <div
            key={s.l}
            className="rounded-[11px] bg-surface-2 px-3 py-3 text-center"
          >
            <div
              className={cn(
                'font-mono text-[18px] font-bold leading-none',
                s.tone === 'emerald' ? 'text-emerald' : 'text-ink',
              )}
            >
              {s.v}
            </div>
            <div className="mt-1.5 text-[10.5px] font-semibold text-ink-muted">
              {s.l}
            </div>
          </div>
        ))}
      </div>

      <WhatThisMeans>{FIT.meaning}</WhatThisMeans>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S5 — MY INVESTMENT
// ═══════════════════════════════════════════════════════════════════════════
export function MyInvestmentSection() {
  return (
    <div
      className="relative overflow-hidden rounded-2xl p-6 text-white shadow-lg"
      style={{
        background: 'linear-gradient(135deg,var(--dr-navy,#0B1F3A),#1E3A6E)',
      }}
    >
      {/* decorative radial glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-8 -top-12 h-48 w-48 rounded-full"
        style={{
          background: 'radial-gradient(circle, rgba(16,185,129,.22), transparent 70%)',
        }}
      />

      {/* top row: current value left, XIRR right */}
      <div className="relative flex flex-wrap items-start justify-between gap-3.5">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-white/60">
            Current Value
          </div>
          <div className="mt-1.5 font-mono text-[32px] font-extrabold leading-none tracking-[-0.025em] text-white">
            {MINE.currentValue}
          </div>
          <div className="mt-2 font-mono text-small font-bold text-emerald">
            {MINE.pl}{' '}
            <span style={{ color: '#6EE7B7' }}>{MINE.plToday}</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-white/60">
            XIRR
          </div>
          <div
            className="mt-1.5 font-mono text-[26px] font-extrabold leading-none tracking-[-0.02em]"
            style={{ color: '#6EE7B7' }}
          >
            {MINE.xirr}
          </div>
        </div>
      </div>

      {/* preview badge */}
      <div className="relative mt-3">
        <PreviewBadge className="border-white/15 bg-white/10 text-white/60" />
      </div>

      {/* 4-col (2-col mobile) data grid */}
      <div className="relative mt-5 grid grid-cols-2 gap-x-5 gap-y-4 border-t border-white/[0.14] pt-5 sm:grid-cols-4">
        {MINE.grid.map((item) => (
          <div key={item.l}>
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-white/50">
              {item.l}
            </div>
            <div className="mt-1.5 font-mono text-[15px] font-bold text-white">
              {item.v}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S7 — FUND HEALTH DASHBOARD (traffic-light grid)
// ═══════════════════════════════════════════════════════════════════════════
const LIGHT_DOT: Record<'g' | 'y' | 'r', string> = {
  g: 'bg-emerald',
  y: 'bg-amber',
  r: 'bg-red',
};
const LIGHT_RING: Record<'g' | 'y' | 'r', string> = {
  g: 'shadow-[0_0_0_4px_rgba(0,179,134,0.15)]',
  y: 'shadow-[0_0_0_4px_rgba(245,166,35,0.15)]',
  r: 'shadow-[0_0_0_4px_rgba(229,72,77,0.15)]',
};

export function FundHealthSection() {
  return (
    <Panel className="p-5 sm:p-6">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {HEALTH.map((item) => (
          <div
            key={item.name}
            className="flex items-start gap-3 rounded-[13px] border border-line p-3.5"
          >
            {/* traffic-light dot with soft ring */}
            <span
              aria-hidden="true"
              className={cn(
                'mt-[3px] h-3 w-3 shrink-0 rounded-full',
                LIGHT_DOT[item.light],
                LIGHT_RING[item.light],
              )}
            />
            <div className="min-w-0">
              <div className="text-small font-bold text-ink">{item.name}</div>
              <div className="mt-[3px] text-caption leading-snug text-ink-muted">
                {item.note}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S8 — WHAT CHANGED THIS MONTH (vertical timeline)
// ═══════════════════════════════════════════════════════════════════════════
const CHANGE_DOT: Record<'up' | 'down' | 'info', string> = {
  up:   'bg-emerald',
  down: 'bg-red',
  info: 'bg-royal',
};

export function WhatChangedSection() {
  return (
    <Panel className="p-5 sm:p-6">
      {/* timeline rail: relative container with left border as the line */}
      <div className="relative pl-[22px]">
        {/* vertical rail line */}
        <div
          aria-hidden="true"
          className="absolute bottom-[6px] left-[5px] top-[6px] w-[2px] bg-line"
        />

        {CHANGES.map((c, i) => (
          <div
            key={i}
            className={cn('relative pb-4 last:pb-0')}
          >
            {/* colored dot */}
            <span
              aria-hidden="true"
              className={cn(
                'absolute -left-[22px] top-[3px] h-3 w-3 shrink-0 rounded-full border-2 border-surface',
                CHANGE_DOT[c.tone],
              )}
            />

            {/* text (only <b> tags inside — safe to use dangerouslySetInnerHTML) */}
            <div
              className="text-small leading-relaxed text-ink-secondary [&_b]:font-semibold [&_b]:text-ink"
              dangerouslySetInnerHTML={{ __html: c.html }}
            />
            <div className="mt-0.5 font-mono text-[11px] text-ink-faint">
              {c.time}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}
