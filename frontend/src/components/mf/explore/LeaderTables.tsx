/** Sections 08 "Consistency" + 09 "Low-Cost" — wired to live leaderboard boards. */
'use client';
import * as React from 'react';
import Link from 'next/link';
import { Logo } from './Logo';
import { LabelChip } from '@/components/ui/LabelChip';
import { EmptyState } from '@/components/ui/EmptyState';
import { fundName, colorFor, initialOf, pct1, ter1, metricVal, sipConsistencyWord } from '@/components/mf/leaderboard/format';
import type { LbBoard, LbFundRow } from '@/features/mf/types';

const TH = 'py-2.5 px-3 font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted bg-surface-2 whitespace-nowrap';
const TD = 'py-2.5 px-3 text-small whitespace-nowrap';

// ── Section 08 ─────────────────────────────────────────────────────────────

const THREE_LENS_RULE =
  'Active growth funds in the top quarter of their own category on 3-year return, deepest fall, and cost — all three at once. Categories need at least 8 funds with all three measured.';

function ThreeLensBlock({ board }: { board?: LbBoard<LbFundRow> }) {
  if (!board?.rows.length) return null;
  return (
    <div className="mt-4 overflow-x-auto rounded-xl border border-line bg-surface shadow-sm">
      <div className="px-4 pt-3 pb-1">
        <h3 className="text-small font-semibold text-ink">Strong on All Three Lenses</h3>
        <p className="text-caption text-ink-muted mt-0.5">{THREE_LENS_RULE}</p>
      </div>
      <table className="w-full border-collapse text-small min-w-[560px]">
        <thead>
          <tr className="border-b border-line">
            <th className={`${TH} text-left`}>Fund</th>
            <th className={`${TH} text-right`}>3Y</th>
            <th className={`${TH} text-right`}>Max Drawdown</th>
            <th className={`${TH} text-right`}>TER</th>
          </tr>
        </thead>
        <tbody>
          {board.rows.map((r) => {
            const name = fundName(r);
            return (
              <tr key={r.isin} className="border-b border-line last:border-0 hover:bg-surface-2 transition-colors">
                <td className={TD}>
                  <div className="flex items-center gap-2">
                    <Logo letter={initialOf(name)} color={colorFor(r.isin)} size={22} />
                    <Link href={`/mf/fund/${r.isin}`}
                      className="font-medium text-ink hover:text-royal transition-colors">
                      {name}
                    </Link>
                  </div>
                </td>
                <td className={`${TD} text-right font-mono text-emerald font-semibold`}>{pct1(r.return_3y_pct)}</td>
                <td className={`${TD} text-right font-mono`}>
                  {r.max_drawdown_pct != null ? `${r.max_drawdown_pct.toFixed(1)}%` : '\u2014'}
                </td>
                <td className={`${TD} text-right font-mono`}>{ter1(r.expense_ratio_pct)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function ConsistencyTable({
  sipConsistency,
  threeLens,
}: {
  sipConsistency?: LbBoard<LbFundRow>;
  threeLens?: LbBoard<LbFundRow>;
}) {
  if (!sipConsistency) {
    return (
      <EmptyState
        title="Consistency data not available"
        description="Consistency rankings are refreshed nightly."
      />
    );
  }
  return (
    <>
      <div className="overflow-x-auto rounded-xl border border-line bg-surface shadow-sm">
        <table className="w-full border-collapse text-small min-w-[600px]">
          <thead>
            <tr className="border-b border-line">
              <th className={TH}>#</th>
              <th className={`${TH} text-left`}>Fund</th>
              <th className={`${TH} text-right`}>Consistency</th>
              <th className={`${TH} text-right`}>1Y</th>
              <th className={`${TH} text-right`}>3Y</th>
              <th className={`${TH} text-left`}>Label</th>
            </tr>
          </thead>
          <tbody>
            {sipConsistency.rows.map((r, i) => {
              const name = fundName(r);
              return (
                <tr key={r.isin} className="border-b border-line last:border-0 hover:bg-surface-2 transition-colors">
                  <td className={`${TD} text-center font-mono text-ink-muted`}>{i + 1}</td>
                  <td className={TD}>
                    <div className="flex items-center gap-2.5">
                      <Logo letter={initialOf(name)} color={colorFor(r.isin)} size={26} />
                      <Link href={`/mf/fund/${r.isin}`}
                        className="font-medium text-ink hover:text-royal transition-colors">
                        {name}
                      </Link>
                    </div>
                  </td>
                  <td className={`${TD} text-right font-semibold text-emerald`}>{sipConsistencyWord(r)}</td>
                  <td className={`${TD} text-right font-mono`}>{pct1(r.return_1y_pct)}</td>
                  <td className={`${TD} text-right font-mono text-emerald font-semibold`}>{pct1(r.return_3y_pct)}</td>
                  <td className={TD}>
                    <LabelChip label={r.verb_label} confidenceBand={r.confidence_band} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <ThreeLensBlock board={threeLens} />
    </>
  );
}

// ── Section 09 ─────────────────────────────────────────────────────────────

export function LowCostTable({
  valueTer,
  valueEfficiency,
}: {
  valueTer?: LbBoard<LbFundRow>;
  valueEfficiency?: LbBoard<LbFundRow>;
}) {
  if (!valueTer && !valueEfficiency) {
    return (
      <EmptyState
        title="Low-cost data not available"
        description="Cost rankings are refreshed nightly."
      />
    );
  }
  return (
    <div className="flex flex-col gap-4">
      {valueTer && (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface shadow-sm">
          <div className="px-4 pt-3 pb-1">
            <h3 className="text-small font-semibold text-ink">Lowest Expense Ratio</h3>
          </div>
          <table className="w-full border-collapse text-small min-w-[560px]">
            <thead>
              <tr className="border-b border-line">
                <th className={TH}>#</th>
                <th className={`${TH} text-left`}>Fund</th>
                <th className={`${TH} text-right`}>TER</th>
                <th className={`${TH} text-right`}>Cat Avg TER</th>
                <th className={`${TH} text-right`}>3Y</th>
              </tr>
            </thead>
            <tbody>
              {valueTer.rows.map((r, i) => {
                const name = fundName(r);
                return (
                  <tr key={r.isin} className="border-b border-line last:border-0 hover:bg-surface-2 transition-colors">
                    <td className={`${TD} text-center font-mono text-ink-muted`}>{i + 1}</td>
                    <td className={TD}>
                      <div className="flex items-center gap-2.5">
                        <Logo letter={initialOf(name)} color={colorFor(r.isin)} size={26} />
                        <Link href={`/mf/fund/${r.isin}`}
                          className="font-medium text-ink hover:text-royal transition-colors">
                          {name}
                        </Link>
                      </div>
                    </td>
                    <td className={`${TD} text-right font-mono text-emerald font-semibold`}>{ter1(r.expense_ratio_pct)}</td>
                    <td className={`${TD} text-right font-mono text-ink-muted`}>
                      {r.metric_category_avg != null ? ter1(r.metric_category_avg) : '\u2014'}
                    </td>
                    <td className={`${TD} text-right font-mono`}>{pct1(r.return_3y_pct)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {valueEfficiency && (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface shadow-sm">
          <div className="px-4 pt-3 pb-1">
            <h3 className="text-small font-semibold text-ink">Best Return Efficiency</h3>
          </div>
          <table className="w-full border-collapse text-small min-w-[560px]">
            <thead>
              <tr className="border-b border-line">
                <th className={TH}>#</th>
                <th className={`${TH} text-left`}>Fund</th>
                <th className={`${TH} text-right`}>TER</th>
                <th className={`${TH} text-right`}>3Y</th>
                <th className={`${TH} text-right`}>Return/Cost</th>
              </tr>
            </thead>
            <tbody>
              {valueEfficiency.rows.map((r, i) => {
                const name = fundName(r);
                return (
                  <tr key={r.isin} className="border-b border-line last:border-0 hover:bg-surface-2 transition-colors">
                    <td className={`${TD} text-center font-mono text-ink-muted`}>{i + 1}</td>
                    <td className={TD}>
                      <div className="flex items-center gap-2.5">
                        <Logo letter={initialOf(name)} color={colorFor(r.isin)} size={26} />
                        <Link href={`/mf/fund/${r.isin}`}
                          className="font-medium text-ink hover:text-royal transition-colors">
                          {name}
                        </Link>
                      </div>
                    </td>
                    <td className={`${TD} text-right font-mono`}>{ter1(r.expense_ratio_pct)}</td>
                    <td className={`${TD} text-right font-mono`}>{pct1(r.return_3y_pct)}</td>
                    <td className={`${TD} text-right font-mono text-emerald font-semibold`}>{metricVal(r)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
