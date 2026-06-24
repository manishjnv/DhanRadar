/**
 * FundCardGrid — V4 card view for the Fund Explorer (desktop 2-col, mobile 1-col).
 *
 * Same data + same navigation target as FundExplorerTable; this is an alternate
 * presentation toggled from the toolbar. Compliance: assessment via the shared
 * FundScoreCell (ring + label, band-driven, NO numeric), no advisory CTA
 * ("View analysis", not "Invest"), returns are factual public data.
 *
 * Each whole card is a single <Link> to the fund detail page (keyboard
 * accessible); no nested interactive elements. Name/AMC formatting matches the
 * table (fund_name_short ?? cleanSchemeName, shortenAmcName, idcw_frequency).
 */
'use client';

import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { FundAvatar } from './FundAvatar';
import { FundScoreCell } from './FundScoreCell';
import { cleanSchemeName, shortenAmcName } from '@/features/mf/explorer-format';
import type { FundExplorerItem } from '@/features/mf/types';
import type { Label } from '@/components/charts/ScoreRing';

const FREQ_LABELS: Record<string, string> = {
  daily: 'Daily',
  weekly: 'Weekly',
  fortnightly: 'Fortnightly',
  monthly: 'Monthly',
  quarterly: 'Quarterly',
  half_yearly: 'Half-Yearly',
  annual: 'Annual',
};

function RetTile({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-lg bg-surface-2 px-2 py-2 text-center">
      {value != null ? (
        <div className={cn('font-mono text-small font-semibold tabular-nums', value >= 0 ? 'text-emerald' : 'text-red')}>
          {value >= 0 ? '+' : ''}{value.toFixed(1)}%
        </div>
      ) : (
        <div className="font-mono text-small text-ink-muted">—</div>
      )}
      <div className="text-caption uppercase tracking-wide text-ink-muted font-semibold mt-0.5">{label}</div>
    </div>
  );
}

function planLabel(p: FundExplorerItem['plan_type']) {
  return p === 'direct' ? 'Direct' : p === 'regular' ? 'Regular' : null;
}
function optionLabel(o: FundExplorerItem['option_type']) {
  switch (o) {
    case 'growth':            return 'Growth';
    case 'idcw':              return 'IDCW';
    case 'dividend_reinvest': return 'Div Reinvest';
    case 'dividend_payout':   return 'Div Payout';
    default:                  return null;
  }
}

function MetaChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded bg-surface-3 border border-line px-1.5 py-px font-mono text-[10px] font-semibold uppercase tracking-wide text-ink-secondary">
      {children}
    </span>
  );
}

export function FundCardGrid({ funds }: { funds: FundExplorerItem[] }) {
  if (funds.length === 0) {
    return (
      <div className="rounded-xl border border-line bg-surface-2 py-16 text-center">
        <p className="text-small font-medium text-ink">No funds match your search</p>
        <p className="text-caption text-ink-muted mt-1">Try a different name or clear the search</p>
      </div>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {funds.map((fund) => {
        const detailHref = `/mf/fund/${fund.isin}?category=${encodeURIComponent(fund.sebi_category)}`;
        const name = fund.fund_name_short ?? cleanSchemeName(fund.scheme_name);
        const plan = planLabel(fund.plan_type);
        const opt = optionLabel(fund.option_type);
        const freq = fund.idcw_frequency && fund.option_type !== 'growth' ? FREQ_LABELS[fund.idcw_frequency] : null;
        return (
          <Link
            key={fund.isin}
            href={detailHref}
            data-testid={`fund-card-${fund.isin}`}
            className={cn(
              'group flex flex-col rounded-xl border border-line bg-surface p-4 shadow-sm transition-colors',
              'hover:border-royal/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
            )}
          >
            {/* Header: avatar + name */}
            <div className="flex items-start gap-3">
              <FundAvatar name={fund.scheme_name} size="md" />
              <div className="min-w-0 flex-1">
                <div className="text-small font-semibold text-ink leading-snug line-clamp-2 group-hover:text-royal transition-colors" title={fund.scheme_name}>
                  {name}
                </div>
                {fund.amc_name && (
                  <div className="font-mono text-caption text-ink-muted mt-0.5 truncate">{shortenAmcName(fund.amc_name)}</div>
                )}
              </div>
            </div>

            {/* Assessment + rank */}
            <div className="mt-3 flex items-center justify-between gap-2">
              <FundScoreCell label={fund.verb_label as Label} confidenceBand={fund.confidence_band} ringSize={34} />
              <span className="whitespace-nowrap tabular-nums text-right">
                <span className="font-mono text-small font-semibold text-ink">#{fund.category_rank}</span>
                <span className="font-mono text-caption text-ink-muted">/{fund.category_total}</span>
              </span>
            </div>

            {/* Plan / option / frequency chips */}
            {(plan || opt || freq) && (
              <div className="mt-2.5 flex flex-wrap gap-1">
                {plan && <MetaChip>{plan}</MetaChip>}
                {opt && <MetaChip>{opt}</MetaChip>}
                {freq && <MetaChip>{freq}</MetaChip>}
              </div>
            )}

            {/* Returns */}
            <div className="mt-3 grid grid-cols-4 gap-1.5">
              <RetTile label="6M" value={fund.return_6m_pct} />
              <RetTile label="1Y" value={fund.return_1y_pct} />
              <RetTile label="3Y" value={fund.return_3y_pct} />
              <RetTile label="5Y" value={fund.return_5y_pct} />
            </div>

            {/* CTA */}
            <div className="mt-3 pt-3 border-t border-line flex items-center justify-end text-small font-medium text-royal">
              View analysis
              <svg className="ml-1" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
