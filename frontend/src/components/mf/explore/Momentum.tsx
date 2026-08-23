/** S07 "Momentum Center" — climbing/falling rank columns since last ranking refresh. */
'use client';
import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { EmptyState } from '@/components/ui/EmptyState';
import { fundName, colorFor, initialOf, fmtDelta } from '@/components/mf/leaderboard/format';
import type { LbBoard, LbFundRow } from '@/features/mf/types';

function FundRow({ row, tone }: { row: LbFundRow; tone: 'up' | 'down' }) {
  const name = fundName(row);
  const color = colorFor(row.isin);
  const initial = initialOf(name);
  const delta = Math.abs(row.rank_delta ?? 0);
  return (
    <li className="flex items-center gap-2.5 py-2 border-b border-line last:border-0">
      <span className="grid h-[26px] w-[26px] shrink-0 place-items-center rounded-full text-caption font-bold text-white" style={{ background: color }} aria-hidden="true">
        {initial}
      </span>
      <Link href={`/mf/fund/${row.isin}`} className="flex-1 text-small font-medium text-ink truncate hover:text-royal transition-colors">
        {name}
      </Link>
      <span className={cn('font-mono text-small font-semibold', tone === 'up' ? 'text-emerald' : 'text-red')}>
        {fmtDelta(row.rank_delta)} ranks
      </span>
    </li>
  );
}

function Col({ rows, tone }: { rows: LbFundRow[]; tone: 'up' | 'down' }) {
  return (
    <div>
      <h4 className={cn('text-small font-semibold flex items-center gap-1.5 mb-2', tone === 'up' ? 'text-emerald' : 'text-red')}>
        {tone === 'up' ? '▲ Climbing rankings' : '▼ Falling rankings'}
      </h4>
      <ul>
        {rows.map((r) => <FundRow key={r.isin} row={r} tone={tone} />)}
      </ul>
    </div>
  );
}

export function Momentum({ moversUp, moversDown }: {
  moversUp?: LbBoard<LbFundRow>;
  moversDown?: LbBoard<LbFundRow>;
}) {
  if (!moversUp && !moversDown) {
    return (
      <EmptyState
        title="Momentum data not available"
        description="Rank movers are refreshed nightly."
      />
    );
  }
  return (
    <div>
      <p className="text-caption text-ink-muted mb-3">Since last ranking refresh</p>
      <div className="rounded-xl border border-line bg-surface p-5 shadow-sm grid gap-6 sm:grid-cols-2">
        {moversUp && <Col rows={moversUp.rows} tone="up" />}
        {moversDown && <Col rows={moversDown.rows} tone="down" />}
      </div>
    </div>
  );
}
