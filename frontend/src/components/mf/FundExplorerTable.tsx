/**
 * FundExplorerTable — ranked fund comparison table for /mf/explore.
 *
 * V4 redesign: rounded bordered surface + sticky header, and a band-driven
 * ring + label assessment cell (shared FundScoreCell) that folds the former
 * separate Confidence column into the ring fill. Density, name-cleaning, IDCW
 * disambiguation and all sort/navigation logic are unchanged from main.
 *
 * Compliance invariants (non-negotiable):
 *   - unified_score NEVER rendered (non-neg #2) — the ring is band-driven, no number
 *   - No advisory language — only educational labels and factual data
 *   - confidence band shown as ring fill / word, never as a float
 *   - Row click → navigates to Fund Detail page (/mf/fund/[isin]?category=...)
 *   - Table scrolls horizontally on mobile — no column collapsing
 *
 * Density notes (founder call 2026-06-21, preserved):
 *   - Body type is 12px (deliberate deviation from the ui-system .dt 13px canon
 *     for Bloomberg/TradingView-style density — user instruction wins).
 *   - Per-factor breakdown (consistency/recency/volatility) lives on the Fund
 *     Detail page (WhyThisLabelPanel).
 *   - Scheme name is cleaned of the redundant "- Regular Plan - Growth Option"
 *     suffix (already shown as chips) and clamped to one line.
 */

'use client';

import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/cn';
import { FundScoreCell } from '@/components/mf/explore/FundScoreCell';
import { cleanSchemeName, shortenAmcName } from '@/features/mf/explorer-format';
import type { FundExplorerItem } from '@/features/mf/types';
import type { Label } from '@/components/charts/ScoreRing';

// ---------------------------------------------------------------------------
// Sort types (exported so page.tsx can import SortKey)
// ---------------------------------------------------------------------------

export type SortKey = 'rank' | 'return_3m' | 'return_6m' | 'return_1y' | 'return_3y' | 'return_5y' | 'max_drawdown';

// ---------------------------------------------------------------------------
// Fund avatar — deterministic color from scheme name.
// ---------------------------------------------------------------------------

const AVATAR_VAR_COLORS = [
  'var(--dr-navy,#0B1F3A)',
  'var(--dr-royal,#1E5EFF)',
  '#003E80',
  '#006B7D',
  '#1B4332',
  '#6A1B9A',
  '#B71C1C',
  '#374151',
] as const;

// IDCW payout cadence → short display keyword. Disambiguates funds that share a
// brand + plan + IDCW option but differ only by frequency.
const FREQ_LABELS: Record<string, string> = {
  daily: 'Daily',
  weekly: 'Weekly',
  fortnightly: 'Fortnightly',
  monthly: 'Monthly',
  quarterly: 'Quarterly',
  half_yearly: 'Half-Yearly',
  annual: 'Annual',
};

function FundAvatar({ name }: { name: string }) {
  const idx = ((name.charCodeAt(0) || 0) + (name.charCodeAt(1) || 0)) % AVATAR_VAR_COLORS.length;
  return (
    <div
      className="w-7 h-7 rounded-lg flex items-center justify-center text-white font-bold text-[11px] shrink-0 select-none"
      style={{ background: AVATAR_VAR_COLORS[idx] }}
      aria-hidden="true"
    >
      {name[0]?.toUpperCase() ?? '?'}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sortable column header — accessible: tabIndex + onKeyDown + aria-sort
// ---------------------------------------------------------------------------

function SortHeader({
  label, sortKey, activeSort, sortDir, onSort,
}: {
  label: string;
  sortKey: SortKey;
  activeSort: SortKey;
  sortDir: 'asc' | 'desc';
  onSort: (k: SortKey) => void;
}) {
  const isActive = activeSort === sortKey;
  return (
    <th
      scope="col"
      aria-sort={isActive ? (sortDir === 'desc' ? 'descending' : 'ascending') : 'none'}
      tabIndex={0}
      onClick={() => onSort(sortKey)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSort(sortKey); }
      }}
      className={cn(
        'py-2.5 px-3 text-right font-mono text-caption uppercase tracking-[0.06em] font-semibold bg-surface-2',
        'cursor-pointer select-none whitespace-nowrap transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-royal/40',
        isActive ? 'text-royal' : 'text-ink-muted hover:text-ink',
      )}
    >
      {label}
      <span
        className={cn('ml-1 transition-opacity', isActive ? 'text-royal opacity-100' : 'opacity-30')}
        aria-hidden="true"
      >
        {isActive ? (sortDir === 'desc' ? '▾' : '▴') : '↕'}
      </span>
    </th>
  );
}

const TH = 'py-2.5 px-3 font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted bg-surface-2';

// ---------------------------------------------------------------------------
// Return cell — mono, colored, +/- prefix; em-dash when null
// ---------------------------------------------------------------------------

function ReturnCell({ value }: { value: number | null | undefined }) {
  if (value == null) {
    return (
      <td className="py-2.5 px-3 text-right tabular-nums whitespace-nowrap">
        <span className="font-mono text-[11px] text-ink-muted">—</span>
      </td>
    );
  }
  return (
    <td className="py-2.5 px-3 text-right tabular-nums whitespace-nowrap">
      <span className={cn('font-mono text-[12px] font-semibold', value >= 0 ? 'text-emerald' : 'text-red')}>
        {value >= 0 ? '+' : ''}{value.toFixed(1)}%
      </span>
    </td>
  );
}

// ---------------------------------------------------------------------------
// Main table
// ---------------------------------------------------------------------------

export interface FundExplorerTableProps {
  funds: FundExplorerItem[];
  activeSort: SortKey;
  sortDir: 'asc' | 'desc';
  onSort: (key: SortKey) => void;
}

export function FundExplorerTable({ funds, activeSort, sortDir, onSort }: FundExplorerTableProps) {
  const router = useRouter();

  const handleRowClick = React.useCallback((fund: FundExplorerItem) => {
    const params = new URLSearchParams({ category: fund.sebi_category });
    router.push(`/mf/fund/${fund.isin}?${params.toString()}`);
  }, [router]);

  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-surface shadow-sm">
      {/* min-w ensures horizontal scroll on mobile — never collapses columns.
          table-fixed + colgroup give the fund name room and keep returns tight. */}
      <table
        className="w-full table-fixed border-collapse text-[12px] min-w-[960px]"
        aria-label="Fund rankings — educational data only, not investment advice"
        data-testid="fund-explorer-table"
      >
        <colgroup>
          <col style={{ width: '4%' }} />   {/* # */}
          <col style={{ width: '38%' }} />  {/* Fund */}
          <col style={{ width: '9%' }} />   {/* Rank */}
          <col style={{ width: '22%' }} />  {/* Assessment (ring + label + band) */}
          <col style={{ width: '5.4%' }} />  {/* 3M */}
          <col style={{ width: '5.4%' }} />  {/* 6M */}
          <col style={{ width: '5.4%' }} />  {/* 1Y */}
          <col style={{ width: '5.4%' }} />  {/* 3Y */}
          <col style={{ width: '5.4%' }} />  {/* 5Y */}
        </colgroup>

        {/* thead: sticky, surface-2 background, mono uppercase headers */}
        <thead className="sticky top-0 z-[1]">
          <tr className="border-b border-line">
            <th scope="col" className={cn(TH, 'text-center')}>#</th>
            <th scope="col" className={cn(TH, 'text-left')}>Fund</th>
            <SortHeader label="Rank" sortKey="rank" activeSort={activeSort} sortDir={sortDir} onSort={onSort} />
            <th scope="col" className={cn(TH, 'text-left')}>Assessment</th>
            <SortHeader label="3M" sortKey="return_3m" activeSort={activeSort} sortDir={sortDir} onSort={onSort} />
            <SortHeader label="6M" sortKey="return_6m" activeSort={activeSort} sortDir={sortDir} onSort={onSort} />
            <SortHeader label="1Y" sortKey="return_1y" activeSort={activeSort} sortDir={sortDir} onSort={onSort} />
            <SortHeader label="3Y" sortKey="return_3y" activeSort={activeSort} sortDir={sortDir} onSort={onSort} />
            <SortHeader label="5Y" sortKey="return_5y" activeSort={activeSort} sortDir={sortDir} onSort={onSort} />
          </tr>
        </thead>

        <tbody>
          {funds.map((fund, idx) => {
            const detailHref = `/mf/fund/${fund.isin}?category=${encodeURIComponent(fund.sebi_category)}`;
            return (
              <tr
                key={fund.isin}
                className="border-b border-line last:border-0 hover:bg-surface-2 cursor-pointer transition-colors group"
                onClick={() => handleRowClick(fund)}
                data-testid={`fund-row-${fund.isin}`}
              >
                {/* Row number */}
                <td className="py-2.5 px-3 text-center font-mono text-[11px] text-ink-muted tabular-nums">
                  {idx + 1}
                </td>

                {/* Fund — avatar + cleaned name (one line) + plan/option/freq chips */}
                <td className="py-2.5 px-3">
                  <div className="flex items-center gap-2.5">
                    <FundAvatar name={fund.scheme_name} />
                    <div className="min-w-0">
                      <Link
                        href={detailHref}
                        onClick={(e) => e.stopPropagation()}
                        title={fund.scheme_name}
                        className="font-medium text-ink leading-tight group-hover:text-royal transition-colors line-clamp-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded"
                      >
                        {fund.fund_name_short ?? cleanSchemeName(fund.scheme_name)}
                      </Link>
                      <div className="flex items-center flex-wrap gap-1 mt-0.5">
                        {fund.amc_name && (
                          <span className="font-mono text-[11px] text-ink-muted truncate max-w-[180px]">{shortenAmcName(fund.amc_name)}</span>
                        )}
                        {fund.plan_type && (
                          <span className="inline-flex items-center px-1.5 py-px rounded bg-surface-3 border border-line font-mono text-[10px] font-semibold uppercase tracking-wide text-ink-secondary">
                            {fund.plan_type === 'direct' ? 'Direct' : 'Regular'}
                          </span>
                        )}
                        {fund.option_type && (
                          <span className="inline-flex items-center px-1.5 py-px rounded bg-surface-3 border border-line font-mono text-[10px] font-semibold uppercase tracking-wide text-ink-secondary">
                            {fund.option_type === 'growth' ? 'Growth'
                              : fund.option_type === 'idcw' ? 'IDCW'
                              : fund.option_type === 'dividend_reinvest' ? 'Div Reinvest'
                              : 'Div Payout'}
                          </span>
                        )}
                        {fund.idcw_frequency && fund.option_type !== 'growth' && FREQ_LABELS[fund.idcw_frequency] && (
                          <span className="inline-flex items-center px-1.5 py-px rounded bg-surface-3 border border-line font-mono text-[10px] font-semibold uppercase tracking-wide text-ink-secondary">
                            {FREQ_LABELS[fund.idcw_frequency]}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </td>

                {/* Rank — #N/M in mono */}
                <td className="py-2.5 px-3 text-right whitespace-nowrap tabular-nums">
                  <span className="font-mono text-[12px] font-semibold text-ink">#{fund.category_rank}</span>
                  <span className="font-mono text-[11px] text-ink-muted">/{fund.category_total}</span>
                </td>

                {/* Assessment — band-driven ring + label (folds the old Confidence column) */}
                <td className="py-2.5 px-3">
                  <FundScoreCell label={fund.verb_label as Label} confidenceBand={fund.confidence_band} ringSize={26} />
                </td>

                {/* Returns */}
                <ReturnCell value={fund.return_3m_pct} />
                <ReturnCell value={fund.return_6m_pct} />
                <ReturnCell value={fund.return_1y_pct} />
                <ReturnCell value={fund.return_3y_pct} />
                <ReturnCell value={fund.return_5y_pct} />
              </tr>
            );
          })}

          {funds.length === 0 && (
            <tr>
              <td colSpan={9} className="py-16 text-center">
                <p className="text-small font-medium text-ink">No funds match your search</p>
                <p className="text-caption text-ink-muted mt-1">Try a different name or clear the search</p>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
