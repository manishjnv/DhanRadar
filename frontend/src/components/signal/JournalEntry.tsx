'use client';

import * as React from 'react';
import { X } from 'lucide-react';
import type { JournalEntry } from '@/features/signal/types';
import { useDeleteJournal } from '@/features/signal/api';

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
  const deleteJournal = useDeleteJournal();
  const [confirming, setConfirming] = React.useState(false);

  function handleDelete() {
    deleteJournal.mutate(entry.id, { onSuccess: () => setConfirming(false) });
  }

  return (
    <div className={`j-entry ${decisionClass}`}>
      {/* Header row */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="mono text-caption text-ink-muted">{entry.date}</span>
        <span className={DECISION_BADGE[decisionClass] ?? 'badge badge-neutral'}>
          {DECISION_LABEL[decisionClass] ?? decisionClass}
        </span>
        {(entry.emotions ?? []).map((em) => (
          <span key={em} className="chip">
            {EMOTION_LABEL[em] ?? em}
          </span>
        ))}

        {/* Delete control — pushed to the right */}
        <div className="ml-auto flex items-center gap-2">
          {confirming ? (
            <>
              <span className="text-caption text-ink-secondary">Delete?</span>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleteJournal.isPending}
                className="cursor-pointer border-0 bg-transparent p-0 text-caption font-semibold text-red"
              >
                {deleteJournal.isPending ? '…' : 'Yes'}
              </button>
              <button
                type="button"
                onClick={() => setConfirming(false)}
                className="cursor-pointer border-0 bg-transparent p-0 text-caption text-ink-muted"
              >
                No
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setConfirming(true)}
              aria-label="Delete entry"
              className="cursor-pointer border-0 bg-transparent p-0 leading-none text-ink-faint hover:text-ink"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Note */}
      {entry.notes && (
        <p className="mt-1.5 text-small text-ink-secondary">{entry.notes}</p>
      )}

      {/* Market snapshot */}
      <div className="mono mt-2 flex items-center gap-3 flex-wrap text-caption text-ink-muted">
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
