/**
 * Fund Detail V3 — Sections B: Snapshot · Performance · Risk Center.
 *
 * COMPLIANCE: all content from sampleData.ts. Factual stats (returns %, Sharpe,
 * drawdown %, rank, quartile) are DOM-allowed. NO DhanRadar composite score
 * numbers, no advisory verbs (buy/sell/hold/avoid/caution/switch).
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import {
  TabBar, ChipToggle, Accordion, BandBar, InfoTip, Panel,
  WhatThisMeans, PreviewBadge, GrowthChart, RankChart, DrawdownChart,
  TONE_TEXT,
} from './parts';
import {
  SNAPSHOT,
  RETURNS, RETURN_TABLE, RETURN_TABLE_HEAD, GROWTH, SIP, ROLLING, RANK, DRAWDOWN, CONSISTENCY,
  RISK_SIMPLE, RISK_ADV, RISK_MEANING,
} from './sampleData';

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
      <div className="grid grid-cols-2 gap-px sm:grid-cols-4">
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

// ── Returns tab ──────────────────────────────────────────────────────────────
function ReturnsTab() {
  const [range, setRange] = React.useState(GROWTH.ranges[2]); // default 5Y

  return (
    <>
      {/* 8-col return cells */}
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-8">
        {RETURNS.map((r) => (
          <div
            key={r.p}
            className="rounded-xl border border-line bg-surface px-1.5 py-3 text-center"
          >
            <div className="text-[10.5px] font-semibold text-ink-muted">{r.p}</div>
            <div className="mt-1"><ReturnValue v={r.v} /></div>
          </div>
        ))}
      </div>

      {/* Comparison table */}
      <table className="mt-4 w-full border-collapse text-[12.5px]">
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

      {/* Growth chart */}
      <div className="mt-4 rounded-2xl border border-line bg-gradient-to-b from-white to-surface-2 p-4">
        <div className="mb-2 flex items-baseline justify-between">
          <span className="text-[13px] font-semibold text-ink-secondary">
            Growth of {GROWTH.invested}
          </span>
          <span className="font-mono text-[13px] font-bold text-emerald">
            {GROWTH.value}{' '}
            <span className="font-normal text-ink-muted">· {GROWTH.gain}</span>
          </span>
        </div>
        <GrowthChart height={170} />
        {/* Range toggle */}
        <div className="mt-3">
          <ChipToggle
            options={GROWTH.ranges.map((r) => ({ key: r, label: r }))}
            active={range}
            onChange={setRange}
          />
        </div>
        {/* Legend */}
        <div className="mt-3 flex flex-wrap gap-4 text-[11.5px] text-ink-muted">
          <span className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2 w-5 rounded-full" style={{ background: '#1E5EFF' }} aria-hidden="true" />
            This fund
          </span>
          <span className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2 w-5 rounded-full" style={{ background: '#F5A623' }} aria-hidden="true" />
            Category avg
          </span>
          <span className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2 w-5 rounded-full bg-ink-faint" aria-hidden="true" />
            Benchmark
          </span>
        </div>
      </div>

      <WhatThisMeans>
        A passive fund that quietly matches or beats both its benchmark and the active category
        average — mostly because its <b>0.20% expense ratio</b> drags returns less.
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
function RollingTab() {
  return (
    <>
      {/* Tiles */}
      <div className="mb-4 grid grid-cols-3 gap-2">
        {ROLLING.tiles.map((t) => (
          <div key={t.p} className="rounded-xl border border-line bg-surface py-3 text-center">
            <div className="text-[10.5px] font-semibold text-ink-muted">{t.p}</div>
            <div className="mt-1 font-mono text-[14px] font-bold text-emerald">{t.v}</div>
          </div>
        ))}
      </div>

      {/* Comparison table */}
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

      <WhatThisMeans>{ROLLING.meaning}</WhatThisMeans>
    </>
  );
}

// ── Rank Trend tab ────────────────────────────────────────────────────────────
function RankTab() {
  return (
    <>
      {/* 4-up rank cells — gap-px grid with bg-line wrapper */}
      <div className="mb-4 overflow-hidden rounded-2xl border border-line bg-line">
        <div className="grid grid-cols-2 gap-px sm:grid-cols-4">
          {RANK.cells.map((c) => (
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

      {/* Rank trend chart */}
      <RankChart series={RANK.series} height={150} />

      {/* Band strip */}
      <div className="mt-3 flex gap-1.5">
        {RANK.bands.map((b) => (
          <div
            key={b.name}
            className={cn(
              'flex-1 rounded-lg py-1.5 text-center font-mono text-[11px] font-bold',
              b.on ? 'text-white' : 'text-ink-faint opacity-40',
            )}
            style={b.on ? { background: b.color } : { background: b.color }}
          >
            {b.name}
          </div>
        ))}
      </div>

      <WhatThisMeans>{RANK.meaning}</WhatThisMeans>
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

export function PerformanceSection() {
  const [tab, setTab] = React.useState('returns');

  return (
    <Panel className="p-5 sm:p-6">
      <div className="flex items-center justify-between gap-3 mb-4">
        <TabBar tabs={PERF_TABS} active={tab} onChange={setTab} />
        <PreviewBadge className="shrink-0" />
      </div>

      {tab === 'returns'   && <ReturnsTab />}
      {tab === 'sip'       && <SipTab />}
      {tab === 'rolling'   && <RollingTab />}
      {tab === 'rank'      && <RankTab />}
      {tab === 'drawdowns' && <DrawdownsTab />}
      {tab === 'consist'   && <ConsistencyTab />}
    </Panel>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// S12 — RISK CENTER
// ─────────────────────────────────────────────────────────────────────────────

export function RiskCenterSection() {
  return (
    <Panel className="p-5 sm:p-6">
      {/* Simple risk grid — 3-col desktop / 2-col mobile */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {RISK_SIMPLE.map((r) => (
          <div key={r.l} className="rounded-xl bg-surface-2 px-3 py-4 text-center">
            <div className={cn('font-mono text-[15px] font-bold', TONE_TEXT[r.tone])}>
              {r.v}
            </div>
            <div className="mt-1 text-[10px] font-semibold text-ink-muted">{r.l}</div>
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
          {RISK_ADV.map((row) => (
            <div
              key={row.name}
              className="flex items-center gap-3 border-b border-line pb-3 last:border-b-0 last:pb-0"
            >
              {/* Name + tip */}
              <div className="flex min-w-[140px] shrink-0 items-center gap-1.5">
                <span className="text-[12.5px] font-semibold text-ink">{row.name}</span>
                <InfoTip tip={row.tip} />
              </div>
              {/* Decorative band bar (no %) */}
              <div className="flex-1">
                <BandBar band={row.band} width={70} />
              </div>
              {/* Factual value */}
              <div className="w-[56px] shrink-0 text-right font-mono text-[12.5px] font-bold text-ink-secondary">
                {row.value}
              </div>
            </div>
          ))}
        </div>
      </Accordion>

      <WhatThisMeans>{RISK_MEANING}</WhatThisMeans>
    </Panel>
  );
}
