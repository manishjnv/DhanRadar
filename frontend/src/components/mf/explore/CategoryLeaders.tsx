/**
 * CategoryLeaders — V4 "Category Leaderboards", scoped to the selected category.
 *
 * Shows the top-ranked funds in the currently-selected SEBI category, derived
 * from the existing /mf/funds endpoint (rank ascending). Compliant: educational
 * label chips, factual returns, no numeric score, no advisory framing.
 * Pure presentational — the page supplies the already-fetched leaders.
 */
'use client';

import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { FundAvatar } from './FundAvatar';
import { LabelChip } from '@/components/ui/LabelChip';
import { cleanSchemeName, shortenAmcName } from '@/features/mf/explorer-format';
import type { FundExplorerItem } from '@/features/mf/types';
import type { Label } from '@/components/charts/ScoreRing';

const MEDAL = ['🥇', '🥈', '🥉'];

export function CategoryLeaders({
  leaders,
  categoryName,
}: {
  leaders: FundExplorerItem[];
  categoryName: string;
}) {
  if (leaders.length === 0) return null;

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {leaders.slice(0, 3).map((fund, i) => {
        const detailHref = `/mf/fund/${fund.isin}?category=${encodeURIComponent(fund.sebi_category)}`;
        const name = fund.fund_name_short ?? cleanSchemeName(fund.scheme_name);
        const r3 = fund.return_3y_pct;
        return (
          <Link
            key={fund.isin}
            href={detailHref}
            className={cn(
              'group rounded-xl border border-line bg-surface p-4 shadow-sm transition-colors',
              'hover:border-royal/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
            )}
          >
            <div className="flex items-center gap-1.5 font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted">
              <span aria-hidden="true">{MEDAL[i]}</span>
              <span className="truncate">Rank #{fund.category_rank} · {categoryName}</span>
            </div>
            <div className="mt-2.5 flex items-center gap-2.5">
              <FundAvatar name={fund.scheme_name} size="md" />
              <div className="min-w-0">
                <div className="text-small font-semibold text-ink leading-snug line-clamp-2 group-hover:text-royal transition-colors" title={fund.scheme_name}>
                  {name}
                </div>
                {fund.amc_name && <div className="font-mono text-caption text-ink-muted mt-0.5 truncate">{shortenAmcName(fund.amc_name)}</div>}
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between gap-2">
              <LabelChip label={fund.verb_label as Label} confidenceBand={fund.confidence_band ?? undefined} />
              {r3 != null && (
                <span className="text-right">
                  <span className={cn('font-mono text-small font-semibold tabular-nums', r3 >= 0 ? 'text-emerald' : 'text-red')}>
                    {r3 >= 0 ? '+' : ''}{r3.toFixed(1)}%
                  </span>
                  <span className="font-mono text-caption text-ink-muted ml-1">3Y</span>
                </span>
              )}
            </div>
          </Link>
        );
      })}
    </div>
  );
}
