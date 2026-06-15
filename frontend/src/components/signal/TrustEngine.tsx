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
    <div
      style={{
        marginTop: 12,
        padding: '10px 12px',
        borderRadius: 8,
        background: 'var(--emerald-soft)',
        border: '1px solid rgba(0,179,134,0.25)',
      }}
    >
      {scores.has_trust_data && (
        <p style={{ fontSize: 12, color: 'var(--text)', fontWeight: 500, marginBottom: 4 }}>
          {scores.trust_wins} of {scores.trust_total} triggered signals beat waiting
        </p>
      )}
      <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
        Past accuracy does not predict future outcomes. Educational context only.
      </p>
    </div>
  );

  return (
    <div className="card card-pad flex flex-col gap-3">
      <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Trust Engine</p>

      {!scores.has_trust_data || eligibleRows.length === 0 ? (
        <div className="empty" style={{ padding: '20px 0', textAlign: 'center' }}>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            Trust Engine activates after 90 days of signals.
          </p>
          <p style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 4 }}>
            Keep checking daily — your signal history is building.
          </p>
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="dt w-full" style={{ minWidth: 380 }}>
            <thead>
              <tr>
                {['Signal date', 'Signal state', 'Your action', 'Market outcome'].map((h) => (
                  <th
                    key={h}
                    style={{
                      fontSize: 10,
                      textTransform: 'uppercase',
                      color: 'var(--text-muted)',
                      letterSpacing: '0.06em',
                      paddingBottom: 6,
                      textAlign: 'left',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {eligibleRows.map((row) => (
                <tr key={row.id} style={{ borderTop: '1px solid var(--border)' }}>
                  <td
                    style={{
                      fontSize: 11,
                      fontFamily: 'var(--dr-font-mono)',
                      color: 'var(--text-muted)',
                      paddingBlock: 8,
                    }}
                  >
                    {row.date}
                  </td>
                  <td style={{ paddingBlock: 8 }}>
                    <span className={SIGNAL_BADGE[row.signal_state ?? ''] ?? 'badge badge-neutral'}>
                      {SIGNAL_LABEL[row.signal_state ?? ''] ?? row.signal_state}
                    </span>
                  </td>
                  <td style={{ paddingBlock: 8 }}>
                    <span className={DECISION_BADGE[row.decision] ?? 'badge badge-neutral'}>
                      {DECISION_LABEL[row.decision] ?? row.decision}
                    </span>
                  </td>
                  <td
                    style={{
                      fontSize: 12,
                      fontFamily: 'var(--dr-font-mono)',
                      fontFeatureSettings: "'tnum'",
                      color: 'var(--text-muted)',
                      paddingBlock: 8,
                    }}
                  >
                    —
                  </td>
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
