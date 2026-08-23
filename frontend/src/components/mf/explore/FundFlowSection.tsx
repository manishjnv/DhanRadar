/** S06 "Fund Flow" — category-level inflows + AUM growth.
 * Source: category_inflows (AMFI net flow, category-level only — no per-fund flow source)
 *         aum_growth (fastest-growing funds by month-on-month AUM %).
 * Compliance: copy MUST say "category-level" — never imply per-fund flows.
 */
'use client';
import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { EmptyState } from '@/components/ui/EmptyState';
import { categoryDisplayName } from '@/features/mf/explorer-format';
import { fundName, colorFor, initialOf, metricVal } from '@/components/mf/leaderboard/format';
import type { LbBoard, LbFundRow, LbCategoryInflowRow } from '@/features/mf/types';

function fmtFlow(cr: number): string {
  const sign = cr >= 0 ? '+' : '\u2212';
  const abs = Math.abs(cr);
  if (abs >= 1000) return `${sign}\u20B9${(abs / 1000).toFixed(1)}k Cr`;
  return `${sign}\u20B9${abs.toFixed(0)} Cr`;
}

function InflowLane({ board }: { board: LbBoard<LbCategoryInflowRow> }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-2.5">
        <span className="grid h-8 w-8 place-items-center rounded-lg text-base bg-emerald/10 text-emerald" aria-hidden="true">📥</span>
        <span className="text-small font-semibold text-ink">Category inflows</span>
      </div>
      <ul>
        {board.rows.map((r, i) => (
          <li key={i} className="flex items-center gap-2.5 py-2 border-b border-line last:border-0">
            <span className="flex-1 text-small font-medium text-ink truncate">{categoryDisplayName(r.category)}</span>
            <span className={cn('font-mono text-small font-semibold', r.net_flow_cr >= 0 ? 'text-emerald' : 'text-red')}>
              {fmtFlow(r.net_flow_cr)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AumGrowthLane({ board }: { board: LbBoard<LbFundRow> }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-2.5">
        <span className="grid h-8 w-8 place-items-center rounded-lg text-base bg-royal/10 text-royal" aria-hidden="true">🚀</span>
        <span className="text-small font-semibold text-ink">Fastest growing AUM</span>
      </div>
      <ul>
        {board.rows.map((r) => {
          const name = fundName(r);
          const color = colorFor(r.isin);
          const initial = initialOf(name);
          return (
            <li key={r.isin} className="flex items-center gap-2.5 py-2 border-b border-line last:border-0">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full text-caption font-bold text-white" style={{ background: color }} aria-hidden="true">
                {initial}
              </span>
              <Link href={`/mf/fund/${r.isin}`} className="flex-1 text-small font-medium text-ink truncate hover:text-royal transition-colors">
                {name}
              </Link>
              <span className="font-mono text-small font-semibold text-royal">{metricVal(r)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function FundFlowSection({ categoryInflows, aumGrowth }: {
  categoryInflows?: LbBoard<LbCategoryInflowRow>;
  aumGrowth?: LbBoard<LbFundRow>;
}) {
  if (!categoryInflows && !aumGrowth) {
    return (
      <EmptyState
        title="Fund flow data not available"
        description="Flow data is refreshed nightly."
      />
    );
  }
  return (
    <div>
      <div className={cn('grid gap-3', categoryInflows && aumGrowth ? 'sm:grid-cols-2' : 'sm:grid-cols-1')}>
        {categoryInflows && <InflowLane board={categoryInflows} />}
        {aumGrowth && <AumGrowthLane board={aumGrowth} />}
      </div>
      <p className="mt-2 text-caption text-ink-muted">
        AMFI category-level data; per-scheme flows are not published.
      </p>
    </div>
  );
}
