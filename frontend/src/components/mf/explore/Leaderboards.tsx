/**
 * Leaderboards — section 04 "Category Leaderboards" wired to champions board.
 * One winner card per category: label+band, 3Y return, risk band, educational why.
 */
'use client';
import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { Logo } from './Logo';
import { FundScoreCell } from './FundScoreCell';
import { EmptyState } from '@/components/ui/EmptyState';
import { fundName, colorFor, initialOf, pct1 } from '@/components/mf/leaderboard/format';
import type { LbBoard, LbChampionRow } from '@/features/mf/types';

function catLabel(cat: string): string {
  return cat.replace(/^(Equity|Debt|Hybrid|Solution Oriented|Other) Scheme\s*[-\u2013]\s*/i, '');
}

export function Leaderboards({ champions }: { champions?: LbBoard<LbChampionRow> }) {
  if (!champions) {
    return (
      <EmptyState
        title="Category Leaderboards not available"
        description="Rankings are refreshed nightly."
      />
    );
  }
  const rows = champions.rows.slice(0, 12);
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        {rows.map((row) => {
          const w = row.winner;
          const name = fundName(w);
          const letter = initialOf(name);
          const color = colorFor(w.isin);
          return (
            <div key={row.category} className="rounded-xl border border-line bg-surface p-4 shadow-sm">
              <div className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted truncate">
                {catLabel(row.category)}
              </div>
              <div className="mt-2.5 flex items-center gap-2.5">
                <Logo letter={letter} color={color} size={36} />
                <div className="min-w-0 flex-1">
                  <Link href={`/mf/fund/${w.isin}`}
                    className="text-small font-semibold text-ink hover:text-royal transition-colors block truncate">
                    {name}
                  </Link>
                  <div className="font-mono text-caption text-ink-muted truncate">{w.amc_name}</div>
                </div>
                <FundScoreCell label={w.verb_label} confidenceBand={w.confidence_band}
                  ringSize={30} className="!gap-0" stacked />
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2">
                <div className="rounded-lg bg-surface-2 px-2 py-1.5 text-center">
                  <div className="font-mono text-small font-semibold text-emerald tabular-nums">
                    {pct1(w.return_3y_pct)}
                  </div>
                  <div className="text-caption uppercase tracking-wide text-ink-muted font-semibold">3Y</div>
                </div>
                <div className="rounded-lg bg-surface-2 px-2 py-1.5 text-center">
                  <div className="text-small font-semibold text-ink truncate text-center">
                    {w.riskometer ?? '\u2014'}
                  </div>
                  <div className="text-caption uppercase tracking-wide text-ink-muted font-semibold">Risk</div>
                </div>
                <div className="rounded-lg bg-surface-2 px-2 py-1.5 text-center">
                  <div className="text-small font-semibold text-royal">#1</div>
                  <div className="text-caption uppercase tracking-wide text-ink-muted font-semibold">Rank</div>
                </div>
              </div>
              {row.why && (
                <div className={cn('mt-3 flex gap-2 text-small text-ink-secondary leading-relaxed')}>
                  <span aria-hidden="true" className="text-emerald font-bold shrink-0">✓</span>
                  <span>{row.why}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-3 flex justify-end">
        <Link href="/mf/leaderboard"
          className="text-small font-medium text-royal hover:underline transition-colors">
          View all →
        </Link>
      </div>
    </>
  );
}
