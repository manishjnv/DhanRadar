'use client';

import * as React from 'react';
import type { JournalEntry } from '@/features/signal/types';

interface BehaviourSummaryProps {
  entries: JournalEntry[];
}

export function BehaviourSummary({ entries }: BehaviourSummaryProps) {
  const total = entries.length;
  const prematureCount = entries.filter((e) => e.premature).length;
  const fomoAvoidedCount = entries.filter((e) => e.fomo_avoided).length;
  const daysOnRules = total - prematureCount;

  const rows: { label: string; value: number; positive: boolean }[] = [
    { label: 'Days following rules', value: daysOnRules, positive: true },
    { label: 'FOMO avoided', value: fomoAvoidedCount, positive: true },
    { label: 'Premature deployments', value: prematureCount, positive: false },
    { label: 'SIP streak (months)', value: 0, positive: true },
  ];

  return (
    <div className="card card-pad flex flex-col gap-3">
      <p className="text-small font-semibold text-ink">Behaviour Summary</p>

      <table className="dt w-full">
        <tbody>
          {rows.map(({ label, value, positive }) => (
            <tr key={label}>
              <td className="text-small text-ink-secondary">{label}</td>
              <td className="right">
                <span
                  className={`mono text-body font-bold ${
                    positive ? 'text-emerald' : 'text-amber'
                  }`}
                >
                  {value}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
