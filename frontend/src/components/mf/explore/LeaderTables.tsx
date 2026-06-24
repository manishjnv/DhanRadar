/** S13 "Consistency" + S14 "Low-Cost" leaderboards — illustrative tables. */
'use client';
import * as React from 'react';
import { Logo } from './Logo';
import { CONSISTENCY, LOW_COST } from './sampleData';

const TH = 'py-2.5 px-3 font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted bg-surface-2 whitespace-nowrap';
const TD = 'py-2.5 px-3 text-small whitespace-nowrap';

export function ConsistencyTable() {
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-surface shadow-sm">
      <table className="w-full border-collapse text-small min-w-[680px]">
        <thead>
          <tr className="border-b border-line">
            <th className={TH}>#</th>
            <th className={`${TH} text-left`}>Fund</th>
            <th className={`${TH} text-right`}>Yrs beat cat</th>
            <th className={`${TH} text-right`}>Rank stability</th>
            <th className={`${TH} text-right`}>Persistence</th>
            <th className={`${TH} text-right`}>Mgr changes</th>
          </tr>
        </thead>
        <tbody>
          {CONSISTENCY.map((r) => (
            <tr key={r.rank} className="border-b border-line last:border-0 hover:bg-surface-2 transition-colors">
              <td className={`${TD} text-center font-mono text-ink-muted`}>{r.rank}</td>
              <td className={TD}>
                <div className="flex items-center gap-2.5"><Logo letter={r.logo} color={r.color} size={26} /><span className="font-medium text-ink">{r.name}</span></div>
              </td>
              <td className={`${TD} text-right font-mono text-emerald font-semibold`}>{r.yrsBeat}</td>
              <td className={`${TD} text-right`}>{r.stability}</td>
              <td className={`${TD} text-right font-mono text-emerald`}>{r.persistence}</td>
              <td className={`${TD} text-right font-mono`}>{r.mgrChanges}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function LowCostTable() {
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-surface shadow-sm">
      <table className="w-full border-collapse text-small min-w-[680px]">
        <thead>
          <tr className="border-b border-line">
            <th className={TH}>#</th>
            <th className={`${TH} text-left`}>Fund</th>
            <th className={`${TH} text-right`}>Expense</th>
            <th className={`${TH} text-right`}>15Y fee (₹10L)</th>
            <th className={`${TH} text-right`}>Perf. retained</th>
            <th className={`${TH} text-right`}>Efficiency</th>
          </tr>
        </thead>
        <tbody>
          {LOW_COST.map((r) => (
            <tr key={r.rank} className="border-b border-line last:border-0 hover:bg-surface-2 transition-colors">
              <td className={`${TD} text-center font-mono text-ink-muted`}>{r.rank}</td>
              <td className={TD}>
                <div className="flex items-center gap-2.5"><Logo letter={r.logo} color={r.color} size={26} /><span className="font-medium text-ink">{r.name}</span></div>
              </td>
              <td className={`${TD} text-right font-mono text-emerald font-semibold`}>{r.expense}</td>
              <td className={`${TD} text-right font-mono`}>{r.fee15y}</td>
              <td className={`${TD} text-right font-mono text-emerald`}>{r.retained}</td>
              <td className={`${TD} text-right`}>{r.efficiency}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
