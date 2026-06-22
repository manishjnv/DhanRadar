'use client';

/**
 * MoodPeriods — COMPLIANCE-CRITICAL "mood over time" icon strip.
 *
 * A toggle (Monthly / Weekly / Daily) over a row of small mood markers, one per
 * period, coloured by that period's representative mood REGIME. Educational
 * trend view only:
 *   - LABELS + colour only. No numeric mood score (non-neg #2). The marker is a
 *     SOLID regime colour — never a proportional/partial fill (which would leak
 *     the 0–100 score). The exact level is in the per-marker tooltip.
 *   - Symmetric attention colour scale (extremes red, fear/greed amber, neutral
 *     cyan); colour is intensity, not direction — the tooltip names the level.
 *   - Descriptive past history, never a forecast or a call to act.
 */

import * as React from 'react';
import { cn } from '@/lib/cn';
import { REGIME_COLOR, REGIME_DISPLAY } from '@/components/mood/MoodGauge';
import type { Regime } from '@/features/mood/types';
import { useMoodHistory } from '@/features/mood/api';

type View = 'monthly' | 'weekly' | 'daily';

const VIEWS: { key: View; label: string; count: number; noun: string }[] = [
  { key: 'monthly', label: 'Monthly', count: 6, noun: 'month' },
  { key: 'weekly',  label: 'Weekly',  count: 8, noun: 'week' },
  { key: 'daily',   label: 'Daily',   count: 10, noun: 'day' },
];

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function startOfWeek(d: Date): Date {
  const x = new Date(d);
  const day = (x.getDay() + 6) % 7; // Monday = 0
  x.setDate(x.getDate() - day);
  x.setHours(0, 0, 0, 0);
  return x;
}

function keyFor(d: Date, v: View): string {
  if (v === 'monthly') return `${d.getFullYear()}-${d.getMonth()}`;
  if (v === 'weekly') return startOfWeek(d).toISOString().slice(0, 10);
  return d.toISOString().slice(0, 10);
}

function labelFor(d: Date, v: View): string {
  if (v === 'monthly') return MONTHS[d.getMonth()].toUpperCase();
  const ref = v === 'weekly' ? startOfWeek(d) : d;
  return `${ref.getDate()} ${MONTHS[ref.getMonth()]}`;
}

// Representative regime for a period = the most frequent reading (ties → latest,
// since the history is newest-first so the first-seen wins).
function modeRegime(regimes: Regime[]): Regime {
  const counts = new Map<Regime, number>();
  for (const r of regimes) counts.set(r, (counts.get(r) ?? 0) + 1);
  let best = regimes[0];
  let bestN = 0;
  for (const [r, n] of counts) {
    if (n > bestN) {
      best = r;
      bestN = n;
    }
  }
  return best;
}

export function MoodPeriods() {
  const [view, setView] = React.useState<View>('monthly');
  // One generous fetch; we re-bucket client-side per view (history is capped by
  // what exists — the engine is only weeks old, so older buckets simply won't show).
  const { data } = useMoodHistory(200);

  const periods = React.useMemo(() => {
    if (!data || data.length === 0) return [];
    const cfg = VIEWS.find((v) => v.key === view) ?? VIEWS[0];
    const groups = new Map<string, { date: Date; regimes: Regime[] }>();
    for (const h of data) {
      const d = new Date(h.snapshot_date);
      if (Number.isNaN(d.getTime())) continue;
      const k = keyFor(d, view);
      const g = groups.get(k);
      if (g) g.regimes.push(h.regime as Regime);
      else groups.set(k, { date: d, regimes: [h.regime as Regime] });
    }
    return [...groups.values()]
      .map((g) => ({ date: g.date, regime: modeRegime(g.regimes), label: labelFor(g.date, view) }))
      .slice(0, cfg.count)
      .reverse();
  }, [data, view]);

  if (periods.length === 0) return null;

  const noun = (VIEWS.find((v) => v.key === view) ?? VIEWS[0]).noun;

  return (
    <section aria-label="Market mood over time" className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="text-small font-medium text-ink">Mood over time</p>
        <div className="inline-flex rounded-md border border-line p-0.5" role="tablist">
          {VIEWS.map((v) => (
            <button
              key={v.key}
              type="button"
              role="tab"
              aria-selected={view === v.key}
              onClick={() => setView(v.key)}
              className={cn(
                'rounded px-2.5 py-0.5 text-caption transition-colors',
                view === v.key
                  ? 'bg-surface-3 font-medium text-ink'
                  : 'text-ink-muted hover:text-ink',
              )}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      <ul className="flex flex-wrap items-end gap-x-3.5 gap-y-3">
        {periods.map((p, idx) => {
          const isLatest = idx === periods.length - 1;
          return (
            <li
              key={`${p.label}-${idx}`}
              className="flex flex-col items-center gap-1.5"
              title={`${p.label}: ${REGIME_DISPLAY[p.regime]}`}
              aria-label={`${p.label}: ${REGIME_DISPLAY[p.regime]}`}
            >
              <span
                className={cn(
                  'inline-block h-8 w-8 rounded-full',
                  isLatest ? 'ring-2 ring-royal/50 ring-offset-2 ring-offset-surface' : '',
                )}
                style={{ backgroundColor: REGIME_COLOR[p.regime] }}
              />
              <span className={cn('text-caption', isLatest ? 'font-medium text-ink' : 'text-ink-muted')}>
                {p.label}
              </span>
            </li>
          );
        })}
      </ul>

      <p className="mt-3 text-caption text-ink-faint">
        Each marker is the most common mood for that {noun} — colour shows the mood level
        (hover or tap for its name). Descriptive history, not a forecast.
      </p>
    </section>
  );
}
