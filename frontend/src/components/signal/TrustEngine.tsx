'use client';

import * as React from 'react';
import type { BehaviourScores, JournalEntry } from '@/features/signal/types';

const SIGNAL_LABEL: Record<string, string> = {
  triggered: 'Triggered',
  watch: 'Watch',
  no_signal: 'No signal',
};
const SIGNAL_BADGE: Record<string, string> = {
  triggered: 'badge badge-pos',
  watch: 'badge badge-warn',
  no_signal: 'badge badge-neutral',
};

const DECISION_BADGE: Record<string, string> = {
  deployed: 'badge badge-pos',
  watched: 'badge badge-warn',
  skipped: 'badge badge-neutral',
};
const DECISION_LABEL: Record<string, string> = {
  deployed: 'Deployed',
  watched: 'Watched',
  skipped: 'Skipped',
};

function isOlderThan90Days(dateStr: string): boolean {
  const entry = new Date(dateStr);
  const now = new Date();
  return (now.getTime() - entry.getTime()) / (1000 * 60 * 60 * 24) >= 90;
}

interface TrustEngineProps {
  scores: BehaviourScores;
  entries: JournalEntry[];
}

export function TrustEngine({ scores, entries }: TrustEngineProps) {
  // Only show rows where signal was triggered and 90+ days have elapsed
  const eligibleRows = entries
    .filter((e) => e.signal_state === 'triggered' && isOlderThan90Days(e.date))
    .slice(0, 10);

  const disclaimer = (
    <div className="mt-3 rounded-md border border-emerald/30 bg-emerald-soft px-3 py-2.5">
      {scores.has_trust_data && (
        <p className="mb-1 text-small font-medium text-ink">
          {scores.trust_wins} of {scores.trust_total} triggered signals beat waiting
        </p>
      )}
      <p className="text-small text-ink-secondary">
        Past accuracy does not predict future outcomes. Educational context only.
      </p>
    </div>
  );

  return (
    <div className="card card-pad flex flex-col gap-3">
      <p className="text-small font-semibold text-ink">Trust Engine</p>

      {!scores.has_trust_data || eligibleRows.length === 0 ? (
        <div className="py-5 text-center">
          <p className="text-small text-ink-secondary">
            Trust Engine activates after 90 days of signals.
          </p>
          <p className="mt-1 text-caption text-ink-faint">
            Keep checking daily — your signal history is building.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="dt w-full min-w-[380px]">
            <thead>
              <tr>
                {['Signal date', 'Signal state', 'Your action', 'Market outcome'].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {eligibleRows.map((row) => (
                <tr key={row.id} className="border-t border-line">
                  <td className="mono text-caption text-ink-muted">{row.date}</td>
                  <td>
                    <span className={SIGNAL_BADGE[row.signal_state ?? ''] ?? 'badge badge-neutral'}>
                      {SIGNAL_LABEL[row.signal_state ?? ''] ?? row.signal_state}
                    </span>
                  </td>
                  <td>
                    <span className={DECISION_BADGE[row.decision] ?? 'badge badge-neutral'}>
                      {DECISION_LABEL[row.decision] ?? row.decision}
                    </span>
                  </td>
                  <td className="mono text-small text-ink-muted">—</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {disclaimer}
    </div>
  );
}
