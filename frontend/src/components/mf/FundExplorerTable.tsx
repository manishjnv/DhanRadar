/**
 * FundExplorerTable — ranked fund comparison table for /mf/explore.
 *
 * Compliance invariants (non-negotiable):
 *   - unified_score NEVER rendered (non-neg #2)
 *   - No advisory language — only educational labels and factual data
 *   - confidence_factors rendered as High/Mid/Low badge, never as a float
 *   - Row click → navigates to Fund Detail page (/mf/fund/[isin]?category=...)
 *   - Table scrolls horizontally on mobile — no column collapsing
 */

'use client';

import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/cn';
import { LabelChip } from '@/components/ui/LabelChip';
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
      className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-caption shrink-0 select-none"
      style={{ background: AVATAR_VAR_COLORS[idx] }}
      aria-hidden="true"
    >
      {name[0]?.toUpperCase() ?? '?'}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Factor badge — .badge style: bordered pill, mono text, color-coded
// ---------------------------------------------------------------------------

const FACTOR_CONFIG = {
  high:   { text: 'text-emerald', label: 'High',   ariaLabel: 'High confidence' },
  medium: { text: 'text-amber',   label: 'Mid',    ariaLabel: 'Medium confidence' },
  low:    { text: 'text-red',     label: 'Low',    ariaLabel: 'Low confidence'  },
} as const;

function FactorCell({ value }: { value: 'high' | 'medium' | 'low' | null | undefined }) {
  if (!value) return <span className="font-mono text-caption text-ink-muted">—</span>;
  const cfg = FACTOR_CONFIG[value];
  return (
    <span
      aria-label={cfg.ariaLabel}
      className={cn(
        'inline-flex items-center px-1.5 py-px rounded border border-current',
        'font-mono text-caption font-semibold uppercase tracking-wide',
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
  label, sortKey, activeSort, onSort,
}: {
  label: string;
  sortKey: SortKey;
  activeSort: SortKey;
  onSort: (k: SortKey) => void;
}) {
  const isActive = activeSort === sortKey;
  return (
    <th
      scope="col"
      aria-sort={isActive ? 'ascending' : 'none'}
      tabIndex={0}
      onClick={() => onSort(sortKey)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSort(sortKey); }
      }}
      className={cn(
        'pb-3 px-3 text-right font-mono text-caption uppercase tracking-[0.06em] font-semibold',
        'cursor-pointer select-none whitespace-nowrap transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-royal/40',
        isActive ? 'text-ink' : 'text-ink-muted hover:text-ink-secondary',
      )}
    >
      {label}
      <span className={cn('ml-1 text-royal transition-opacity', isActive ? 'opacity-100' : 'opacity-0')} aria-hidden="true">
        ▴
      </span>
    </th>
  );
}

// ---------------------------------------------------------------------------
// Main table
// ---------------------------------------------------------------------------

export interface FundExplorerTableProps {
  funds: FundExplorerItem[];
  activeSort: SortKey;
  onSort: (key: SortKey) => void;
}

export function FundExplorerTable({ funds, activeSort, onSort }: FundExplorerTableProps) {
  const router = useRouter();

  const handleRowClick = React.useCallback((fund: FundExplorerItem) => {
    const params = new URLSearchParams({ category: fund.sebi_category });
    router.push(`/mf/fund/${fund.isin}?${params.toString()}`);
  }, [router]);

  return (
    <div className="overflow-x-auto">
      {/* min-w ensures horizontal scroll on mobile — never collapses columns */}
      <table
        className="w-full border-collapse text-small min-w-[1100px]"
        aria-label="Fund rankings — educational data only, not investment advice"
        data-testid="fund-explorer-table"
      >
        {/* thead: .dt th pattern — mono, uppercase, caption, muted, tracking */}
        <thead>
          <tr className="border-b border-line">
            <th scope="col" className="pb-3 px-3 w-10 text-center font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted">
              #
            </th>
            <th scope="col" className="pb-3 px-3 text-left font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted">
              Fund
            </th>
            <SortHeader label="Rank"   sortKey="rank"         activeSort={activeSort} onSort={onSort} />
            <th scope="col" className="pb-3 px-3 text-left font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted">
              Assessment
            </th>
            <th scope="col" className="pb-3 px-3 text-right font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted">
              Consistency
            </th>
            <th scope="col" className="pb-3 px-3 text-right font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted">
              Recency
            </th>
            <th scope="col" className="pb-3 px-3 text-right font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted">
              Volatility
            </th>
            <SortHeader label="3M Ret" sortKey="return_3m"  activeSort={activeSort} onSort={onSort} />
            <SortHeader label="6M Ret" sortKey="return_6m"  activeSort={activeSort} onSort={onSort} />
            <SortHeader label="1Y Ret" sortKey="return_1y"  activeSort={activeSort} onSort={onSort} />
            <SortHeader label="3Y Ret" sortKey="return_3y"  activeSort={activeSort} onSort={onSort} />
            <SortHeader label="5Y Ret" sortKey="return_5y"  activeSort={activeSort} onSort={onSort} />
          </tr>
        </thead>

        {/* tbody: .dt td pattern — text-small, padding, hover surface-2 */}
        <tbody>
          {funds.map((fund, idx) => {
            const cf = fund.confidence_factors;
            const detailHref = `/mf/fund/${fund.isin}?category=${encodeURIComponent(fund.sebi_category)}`;
            return (
              <tr
                key={fund.isin}
                className="border-b border-line last:border-0 hover:bg-surface-2 cursor-pointer transition-colors group"
                onClick={() => handleRowClick(fund)}
                data-testid={`fund-row-${fund.isin}`}
              >
                {/* Row number */}
                <td className="py-3 px-3 text-center font-mono text-caption text-ink-muted tabular-nums">
                  {idx + 1}
                </td>

                {/* Fund — .tk pattern: avatar + name + plan/option chips.
                    The fund name <Link> is the keyboard-accessible path;
                    the row onClick handles mouse clicks. */}
                <td className="py-3 px-3">
                  <div className="flex items-center gap-2.5">
                    <FundAvatar name={fund.scheme_name} />
                    <div className="min-w-0">
                      <Link
                        href={detailHref}
                        onClick={(e) => e.stopPropagation()}
                        className="font-medium text-ink leading-snug group-hover:text-royal transition-colors line-clamp-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded"
                      >
                        {fund.scheme_name}
                      </Link>
                      {fund.amc_name && (
                        <p className="font-mono text-caption text-ink-muted mt-0.5">{fund.amc_name}</p>
                      )}
                      {(fund.plan_type || fund.option_type || fund.amc_level_aum_crore != null) && (
                        <div className="flex items-center flex-wrap gap-1 mt-1">
                          {fund.plan_type && (
                            <span className="inline-flex items-center px-1.5 py-px rounded bg-surface-3 border border-line font-mono text-caption font-semibold uppercase tracking-wide text-ink-secondary">
                              {fund.plan_type === 'direct' ? 'Direct' : 'Regular'}
                            </span>
                          )}
                          {fund.option_type && (
                            <span className="inline-flex items-center px-1.5 py-px rounded bg-surface-3 border border-line font-mono text-caption font-semibold uppercase tracking-wide text-ink-secondary">
                              {fund.option_type === 'growth' ? 'Growth'
                                : fund.option_type === 'idcw' ? 'IDCW'
                                : fund.option_type === 'dividend_reinvest' ? 'Div Reinvest'
                                : 'Div Payout'}
                            </span>
                          )}
                          {fund.amc_level_aum_crore != null && (
                            <span className="font-mono text-caption text-ink-muted">
                              AMC AUM: ₹{fund.amc_level_aum_crore.toLocaleString('en-IN', { maximumFractionDigits: 0 })} Cr
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </td>

                {/* Rank — #N/M in mono */}
                <td className="py-3 px-3 text-right whitespace-nowrap tabular-nums">
                  <span className="font-mono text-small font-semibold text-ink">
                    #{fund.category_rank}
                  </span>
                  <span className="font-mono text-caption text-ink-muted">
                    /{fund.category_total}
                  </span>
                </td>

                {/* Assessment label */}
                <td className="py-3 px-3">
                  <LabelChip
                    label={fund.verb_label as Label}
                    confidenceBand={(fund.confidence_band ?? undefined) as ConfidenceBand | undefined}
                  />
                </td>

                {/* Factor badges */}
                <td className="py-3 px-3 text-right">
                  <FactorCell value={cf?.consistency} />
                </td>
                <td className="py-3 px-3 text-right">
                  <FactorCell value={cf?.recency} />
                </td>
                <td className="py-3 px-3 text-right">
                  <FactorCell value={cf?.volatility} />
                </td>

                {/* Returns — mono, colored, +/- prefix */}
                {/* 3M return */}
                <td className="py-3 px-3 text-right tabular-nums whitespace-nowrap">
                  {fund.return_3m_pct != null ? (
                    <span className={cn(
                      'font-mono text-[13px] font-semibold',
                      fund.return_3m_pct >= 0 ? 'text-emerald' : 'text-red',
                    )}>
                      {fund.return_3m_pct >= 0 ? '+' : ''}{fund.return_3m_pct.toFixed(1)}%
                    </span>
                  ) : (
                    <span className="font-mono text-[11px] text-ink-muted">—</span>
                  )}
                </td>
                {/* 6M return */}
                <td className="py-3 px-3 text-right tabular-nums whitespace-nowrap">
                  {fund.return_6m_pct != null ? (
                    <span className={cn(
                      'font-mono text-[13px] font-semibold',
                      fund.return_6m_pct >= 0 ? 'text-emerald' : 'text-red',
                    )}>
                      {fund.return_6m_pct >= 0 ? '+' : ''}{fund.return_6m_pct.toFixed(1)}%
                    </span>
                  ) : (
                    <span className="font-mono text-[11px] text-ink-muted">—</span>
                  )}
                </td>
                {/* 1Y return */}
                <td className="py-3 px-3 text-right tabular-nums whitespace-nowrap">
                  {fund.return_1y_pct != null ? (
                    <span className={cn(
                      'font-mono text-[13px] font-semibold',
                      fund.return_1y_pct >= 0 ? 'text-emerald' : 'text-red',
                    )}>
                      {fund.return_1y_pct >= 0 ? '+' : ''}{fund.return_1y_pct.toFixed(1)}%
                    </span>
                  ) : (
                    <span className="font-mono text-[11px] text-ink-muted">—</span>
                  )}
                </td>
                {/* 3Y return */}
                <td className="py-3 px-3 text-right tabular-nums whitespace-nowrap">
                  {fund.return_3y_pct != null ? (
                    <span className={cn(
                      'font-mono text-[13px] font-semibold',
                      fund.return_3y_pct >= 0 ? 'text-emerald' : 'text-red',
                    )}>
                      {fund.return_3y_pct >= 0 ? '+' : ''}{fund.return_3y_pct.toFixed(1)}%
                    </span>
                  ) : (
                    <span className="font-mono text-[11px] text-ink-muted">—</span>
                  )}
                </td>
                {/* 5Y return */}
                <td className="py-3 px-3 text-right tabular-nums whitespace-nowrap">
                  {fund.return_5y_pct != null ? (
                    <span className={cn(
                      'font-mono text-[13px] font-semibold',
                      fund.return_5y_pct >= 0 ? 'text-emerald' : 'text-red',
                    )}>
                      {fund.return_5y_pct >= 0 ? '+' : ''}{fund.return_5y_pct.toFixed(1)}%
                    </span>
                  ) : (
                    <span className="font-mono text-[11px] text-ink-muted">—</span>
                  )}
                </td>
              </tr>
            );
          })}

          {funds.length === 0 && (
            <tr>
              <td colSpan={12} className="py-16 text-center">
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
