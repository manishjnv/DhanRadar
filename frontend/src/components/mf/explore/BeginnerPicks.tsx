/**
 * Section 10 "Steady SIP Starters" — wired to sip_beginner board.
 * D4 published rule stated once at section level; no per-fund suitability prose.
 */
'use client';
import * as React from 'react';
import Link from 'next/link';
import { Logo } from './Logo';
import { LabelChip } from '@/components/ui/LabelChip';
import { EmptyState } from '@/components/ui/EmptyState';
import { fundName, colorFor, initialOf, pct1 } from '@/components/mf/leaderboard/format';
import type { LbBoard, LbFundRow } from '@/features/mf/types';

const D4_RULE =
  'Listed using the D4 published criteria: direct, equity, 3Y+ history, consistent positive SIP XIRR. Educational observation only — not a recommendation.';

export function BeginnerPicks({ sipBeginner }: { sipBeginner?: LbBoard<LbFundRow> }) {
  if (!sipBeginner) {
    return (
      <EmptyState
        title="Steady SIP Starters not available"
        description="This list is refreshed nightly."
      />
    );
  }
  return (
    <>
      <p className="text-small text-ink-secondary leading-relaxed mb-4">{D4_RULE}</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {sipBeginner.rows.map((b) => {
          const name = fundName(b);
          return (
            <Link key={b.isin} href={`/mf/fund/${b.isin}`}
              className="rounded-xl border border-line bg-surface p-4 shadow-sm hover:border-royal transition-colors block">
              <div className="flex items-center gap-2.5">
                <Logo letter={initialOf(name)} color={colorFor(b.isin)} size={36} />
                <div className="min-w-0 flex-1">
                  <div className="text-small font-semibold text-ink truncate">{name}</div>
                  <div className="font-mono text-caption text-ink-muted truncate">{b.riskometer ?? '\u2014'}</div>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded-lg bg-surface-2 px-2 py-1.5 text-center">
                  <div className="font-mono text-small font-semibold text-emerald tabular-nums">
                    {b.metric_value != null ? `${b.metric_value.toFixed(1)}%` : '\u2014'}
                  </div>
                  <div className="text-caption uppercase tracking-wide text-ink-muted font-semibold">3Y SIP XIRR</div>
                  {b.metric_category_avg != null && (
                    <div className="text-caption text-ink-muted">cat avg {b.metric_category_avg.toFixed(1)}%</div>
                  )}
                </div>
                <div className="rounded-lg bg-surface-2 px-2 py-1.5 text-center">
                  <div className="font-mono text-small font-semibold tabular-nums">{pct1(b.return_3y_pct)}</div>
                  <div className="text-caption uppercase tracking-wide text-ink-muted font-semibold">3Y</div>
                </div>
              </div>
              <div className="mt-2.5">
                <LabelChip label={b.verb_label} confidenceBand={b.confidence_band} />
              </div>
            </Link>
          );
        })}
      </div>
    </>
  );
}
