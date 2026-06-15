'use client';

import * as React from 'react';
import type { JournalEntry } from '@/features/signal/types';

const DECISION_LABEL: Record<string, string> = {
  deployed: 'Deployed',
  watched: 'Watched',
  skipped: 'Skipped',
};

const DECISION_BADGE: Record<string, string> = {
  deployed: 'badge badge-pos',
  watched: 'badge badge-warn',
  skipped: 'badge badge-neutral',
};

const SIGNAL_BADGE: Record<string, string> = {
  triggered: 'badge badge-pos',
  watch: 'badge badge-warn',
  no_signal: 'badge badge-neutral',
};

const SIGNAL_LABEL: Record<string, string> = {
  triggered: 'Triggered',
  watch: 'Watch',
  no_signal: 'No signal',
};

const EMOTION_LABEL: Record<string, string> = {
  fearful: 'Fearful',
  calm: 'Calm',
  excited: 'Excited',
  fomo: 'FOMO',
  disciplined: 'Disciplined',
};

function fmt(n: number | null | undefined, digits = 1): string {
  if (n == null) return '—';
  return n.toFixed(digits);
}

interface JournalEntryCardProps {
  entry: JournalEntry;
}

export function JournalEntryCard({ entry }: JournalEntryCardProps) {
  const decisionClass = entry.decision ?? 'skipped';

  return (
    <div className={`j-entry ${decisionClass}`}>
      {/* Header row */}
      <div className="flex items-center gap-2 flex-wrap">
        <span
          style={{ fontSize: 11, fontFamily: 'var(--dr-font-mono)', color: 'var(--text-muted)' }}
        >
          {entry.date}
        </span>
        <span className={DECISION_BADGE[decisionClass] ?? 'badge badge-neutral'}>
          {DECISION_LABEL[decisionClass] ?? decisionClass}
        </span>
        {(entry.emotions ?? []).map((em) => (
          <span key={em} className="chip">
            {EMOTION_LABEL[em] ?? em}
          </span>
        ))}
      </div>

      {/* Note */}
      {entry.notes && (
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>
          {entry.notes}
        </p>
      )}

      {/* Market snapshot */}
      <div
        className="flex items-center gap-3 flex-wrap"
        style={{ marginTop: 8, fontSize: 11, fontFamily: 'var(--dr-font-mono)', color: 'var(--text-muted)' }}
      >
        <span>Nifty {fmt(entry.nifty_pct)}%</span>
        <span>VIX {fmt(entry.vix_level)}</span>
        <span>A/D {fmt(entry.breadth_ratio)}</span>
        {entry.signal_state && (
          <span className={SIGNAL_BADGE[entry.signal_state] ?? 'badge badge-neutral'}>
            {SIGNAL_LABEL[entry.signal_state] ?? entry.signal_state}
          </span>
        )}
      </div>
    </div>
  );
}
