'use client';

/**
 * MoodTimeline — COMPLIANCE-CRITICAL "how the mood has moved" table.
 *
 * Shows, for a few look-back windows (yesterday / last week / last month), how
 * the market-mood REGIME LABEL changed up to today — e.g. "Last week: Fear →
 * Greed". This is the educational reframe of the rejected DMMI "MMI vs NIFTY"
 * table (MOOD_IMPROVEMENT_PLAN §5.2):
 *
 *   - LABELS ONLY. No numeric mood score (non-neg #2 — no numeric in DOM).
 *   - NO market-return / "NIFTY returned X%" column. Tying mood to returns is
 *     the predictive / performance-correlation the plan explicitly dropped, and
 *     sits outside the ARN-distributor (non-advisory) boundary (non-neg #1).
 *   - Descriptive past-tense history only — never a forecast or a call to act.
 */

import * as React from 'react';
import { REGIME_DISPLAY } from '@/components/mood/MoodGauge';
import type { Regime } from '@/features/mood/types';
import { useMoodHistory } from '@/features/mood/api';

const PERIODS: { label: string; days: number }[] = [
  { label: 'Since yesterday', days: 1 },
  { label: 'Since last week', days: 7 },
  { label: 'Since last month', days: 30 },
];

function label(regime: string): string {
  return REGIME_DISPLAY[regime as Regime] ?? REGIME_DISPLAY.insufficient_data;
}

export interface MoodTimelineProps {
  /** Today's regime (from the current snapshot). */
  todayRegime: Regime;
  /** Today's snapshot date (ISO date string) — the anchor for the look-backs. */
  todayDate: string;
}

export function MoodTimeline({ todayRegime, todayDate }: MoodTimelineProps) {
  // Enough daily snapshots to reach back a month.
  const { data } = useMoodHistory(35);

  const rows = React.useMemo(() => {
    if (!data || data.length === 0) return [];
    const today = new Date(todayDate);
    if (Number.isNaN(today.getTime())) return [];
    return PERIODS.map((p) => {
      const cutoff = new Date(today);
      cutoff.setDate(cutoff.getDate() - p.days);
      // History is newest-first; the most recent snapshot at least `days` old is
      // the reading for that look-back window.
      const prior = data.find((h) => new Date(h.snapshot_date) <= cutoff);
      return { label: p.label, then: prior?.regime ?? null };
    }).filter((r): r is { label: string; then: Regime } => r.then != null);
  }, [data, todayDate]);

  if (rows.length === 0) return null;

  return (
    <section aria-label="How the market mood has moved" className="rounded-lg border border-line bg-surface">
      <p className="border-b border-line px-4 py-3 text-small font-medium text-ink">
        How the mood has moved
      </p>
      <div className="divide-y divide-line">
        {rows.map((r) => {
          const changed = r.then !== todayRegime;
          return (
            <div key={r.label} className="flex items-center justify-between gap-3 px-4 py-2.5">
              <span className="text-caption text-ink-muted">{r.label}</span>
              <span className="inline-flex items-center gap-2 text-small text-ink">
                <span className={changed ? 'text-ink-secondary' : 'text-ink'}>{label(r.then)}</span>
                <span className="text-ink-muted" aria-hidden="true">→</span>
                <span className="font-medium">{label(todayRegime)}</span>
              </span>
            </div>
          );
        })}
      </div>
      <p className="px-4 py-2.5 text-caption text-ink-faint">
        A plain history of the sentiment label over time — no scores, and not a forecast.
      </p>
    </section>
  );
}
