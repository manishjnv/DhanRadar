/**
 * Leaderboards — S9 "Category Leaderboards" (illustrative).
 * One winner card per category: ring+label (band-driven, no numeric), 3Y return,
 * risk band, and an educational "why" line.
 */
'use client';
import * as React from 'react';
import { cn } from '@/lib/cn';
import { Logo } from './Logo';
import { FundScoreCell } from './FundScoreCell';
import { LEADERBOARDS } from './sampleData';

export function Leaderboards() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {LEADERBOARDS.map((l) => (
        <div key={l.cat} className="rounded-xl border border-line bg-surface p-4 shadow-sm">
          <div className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted">🏆 {l.cat}</div>
          <div className="mt-2.5 flex items-center gap-2.5">
            <Logo letter={l.logo} color={l.color} size={36} />
            <div className="min-w-0 flex-1">
              <div className="text-small font-semibold text-ink truncate">{l.short}</div>
              <div className="font-mono text-caption text-ink-muted truncate">{l.amc}</div>
            </div>
            <FundScoreCell label={l.label} confidenceBand={l.band} ringSize={30} className="!gap-0" stacked />
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2">
            <div className="rounded-lg bg-surface-2 px-2 py-1.5 text-center">
              <div className="font-mono text-small font-semibold text-emerald tabular-nums">{l.ret}</div>
              <div className="text-caption uppercase tracking-wide text-ink-muted font-semibold">3Y</div>
            </div>
            <div className="rounded-lg bg-surface-2 px-2 py-1.5 text-center">
              <div className="text-small font-semibold text-ink">{l.risk}</div>
              <div className="text-caption uppercase tracking-wide text-ink-muted font-semibold">Risk</div>
            </div>
            <div className="rounded-lg bg-surface-2 px-2 py-1.5 text-center">
              <div className="text-small font-semibold text-ink">#1</div>
              <div className="text-caption uppercase tracking-wide text-ink-muted font-semibold">Rank</div>
            </div>
          </div>
          <div className={cn('mt-3 flex gap-2 text-small text-ink-secondary leading-relaxed')}>
            <span aria-hidden="true" className="text-emerald font-bold">✓</span>
            <span>{l.why}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
