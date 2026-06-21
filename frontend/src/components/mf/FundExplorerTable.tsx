/**
 * FundExplorerTable — ranked fund comparison table for /mf/explore.
 *
 * Compliance invariants (non-negotiable):
 *   - unified_score NEVER rendered (non-neg #2)
 *   - No advisory language — only educational labels and factual data
 *   - confidence_band rendered as High/Mid/Low badge, never as a float
 *   - Row click → navigates to Fund Detail page (/mf/fund/[isin]?category=...)
 *   - Table scrolls horizontally on mobile — no column collapsing
 *
 * Density notes (founder call 2026-06-21):
 *   - Body type is 12px (deliberate deviation from the ui-system .dt 13px canon
 *     for Bloomberg/TradingView-style density — user instruction wins).
 *   - Per-factor breakdown (consistency/recency/volatility) lives on the Fund
 *     Detail page (WhyThisLabelPanel); here it is consolidated to one Confidence
 *     column to reclaim horizontal space.
 *   - Scheme name is cleaned of the redundant "- Regular Plan - Growth Option"
 *     suffix (already shown as chips) and clamped to one line.
 */

'use client';

import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/cn';
import { LabelChip } from '@/components/ui/LabelChip';
import { cleanSchemeName, shortenAmcName } from '@/features/mf/explorer-format';
import type { FundExplorerItem } from '@/features/mf/types';
import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';

// ---------------------------------------------------------------------------
// Sort types (exported so page.tsx can import SortKey)
// ---------------------------------------------------------------------------

export type SortKey = 'rank' | 'return_3m' | 'return_6m' | 'return_1y' | 'return_3y' | 'return_5y' | 'max_drawdown';

// ---------------------------------------------------------------------------
// Fund avatar — deterministic color from scheme name.
// Uses CSS variables from the brand token set to avoid hardcoded hex.
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
// Confidence band badge — single consolidated column (replaces the 3 factor
// columns). Band-only, never a numeric (non-neg #2, #4).
// ---------------------------------------------------------------------------

const BAND_CONFIG = {
  high:   { text: 'text-emerald', label: 'High', ariaLabel: 'High confidence'   },
  medium: { text: 'text-amber',   label: 'Mid',  ariaLabel: 'Medium confidence' },
  low:    { text: 'text-red',     label: 'Low',  ariaLabel: 'Low confidence'    },
} as const;

function BandCell({ value }: { value: 'high' | 'medium' | 'low' | null | undefined }) {
  if (!value) return <span className="font-mono text-[11px] text-ink-muted">—</span>;
  const cfg = BAND_CONFIG[value];
  return (
    <span
      aria-label={cfg.ariaLabel}
      className={cn(
        'inline-flex items-center px-1.5 py-px rounded border border-current',
        'font-mono text-[11px] font-semibold uppercase tracking-wide',
        cfg.text,
      )}
    >
      {cfg.label}
    </span>
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
        'pb-2.5 px-3 text-right font-mono text-caption uppercase tracking-[0.06em] font-semibold',
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
    <div className="overflow-x-auto">
      {/* min-w ensures horizontal scroll on mobile — never collapses columns.
          table-fixed + colgroup give the fund name room and keep returns tight. */}
      <table
        className="w-full table-fixed border-collapse text-[12px] min-w-[920px]"
        aria-label="Fund rankings — educational data only, not investment advice"
        data-testid="fund-explorer-table"
      >
        <colgroup>
          <col style={{ width: '4%' }} />   {/* # */}
          <col style={{ width: '40%' }} />  {/* Fund */}
          <col style={{ width: '9%' }} />   {/* Rank */}
          <col style={{ width: '14%' }} />  {/* Assessment */}
          <col style={{ width: '8%' }} />   {/* Confidence */}
          <col style={{ width: '5%' }} />   {/* 3M */}
          <col style={{ width: '5%' }} />   {/* 6M */}
          <col style={{ width: '5%' }} />   {/* 1Y */}
          <col style={{ width: '5%' }} />   {/* 3Y */}
          <col style={{ width: '5%' }} />   {/* 5Y */}
        </colgroup>

        {/* thead: .dt th pattern — mono, uppercase, caption, muted, tracking */}
        <thead>
          <tr className="border-b border-line">
            <th scope="col" className="pb-2.5 px-3 text-center font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted">
              #
            </th>
            <th scope="col" className="pb-2.5 px-3 text-left font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted">
              Fund
            </th>
            <SortHeader label="Rank" sortKey="rank" activeSort={activeSort} sortDir={sortDir} onSort={onSort} />
            <th scope="col" className="pb-2.5 px-3 text-left font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted">
              Assessment
            </th>
            <th scope="col" className="pb-2.5 px-3 text-center font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted">
              Confidence
            </th>
            <SortHeader label="3M" sortKey="return_3m" activeSort={activeSort} sortDir={sortDir} onSort={onSort} />
            <SortHeader label="6M" sortKey="return_6m" activeSort={activeSort} sortDir={sortDir} onSort={onSort} />
            <SortHeader label="1Y" sortKey="return_1y" activeSort={activeSort} sortDir={sortDir} onSort={onSort} />
            <SortHeader label="3Y" sortKey="return_3y" activeSort={activeSort} sortDir={sortDir} onSort={onSort} />
            <SortHeader label="5Y" sortKey="return_5y" activeSort={activeSort} sortDir={sortDir} onSort={onSort} />
          </tr>
        </thead>

        {/* tbody: .dt td pattern — text, padding, hover surface-2 */}
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

                {/* Fund — avatar + cleaned name (one line) + plan/option chips.
                    The fund name <Link> is the keyboard-accessible path;
                    the row onClick handles mouse clicks. */}
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
                        {cleanSchemeName(fund.scheme_name)}
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
                      </div>
                    </div>
                  </div>
                </td>

                {/* Rank — #N/M in mono */}
                <td className="py-2.5 px-3 text-right whitespace-nowrap tabular-nums">
                  <span className="font-mono text-[12px] font-semibold text-ink">
                    #{fund.category_rank}
                  </span>
                  <span className="font-mono text-[11px] text-ink-muted">
                    /{fund.category_total}
                  </span>
                </td>

                {/* Assessment label — band moved to its own column, so no
                    confidenceBand here (avoids duplication). */}
                <td className="py-2.5 px-3">
                  <LabelChip label={fund.verb_label as Label} />
                </td>

                {/* Confidence band — single consolidated column */}
                <td className="py-2.5 px-3 text-center">
                  <BandCell value={(fund.confidence_band ?? undefined) as ConfidenceBand | undefined} />
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
              <td colSpan={10} className="py-16 text-center">
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
