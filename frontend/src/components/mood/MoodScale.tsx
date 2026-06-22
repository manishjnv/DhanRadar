'use client';

/**
 * MoodScale — "How to read it" labelled gradient scale.
 *
 * The fear→greed scale as a green→red gradient bar with the five level NAMES and
 * a marker at today's level. COMPLIANCE: labels only — NO 0–100 numbers, no
 * score, no advice. (The reference MMI shows numeric ticks 0/25/50/75/100; we
 * show the named zones instead, per non-neg #2.)
 */

import { REGIME_COLOR } from '@/components/mood/MoodGauge';
import type { Regime } from '@/features/mood/types';

const ORDINAL: Record<string, number> = {
  extreme_fear: 0,
  fear: 1,
  neutral: 2,
  greed: 3,
  extreme_greed: 4,
};

const ZONE_LABELS = ['Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed'];

const GRADIENT =
  `linear-gradient(90deg, ${REGIME_COLOR.extreme_fear} 0%, ${REGIME_COLOR.fear} 25%, ` +
  `${REGIME_COLOR.neutral} 50%, ${REGIME_COLOR.greed} 75%, ${REGIME_COLOR.extreme_greed} 100%)`;

export function MoodScale({ regime }: { regime: Regime }) {
  const ord = ORDINAL[regime];
  const hasMarker = ord !== undefined;
  const pct = hasMarker ? ((ord + 0.5) / 5) * 100 : 50;

  return (
    <section
      aria-label="How to read the mood scale"
      className="rounded-lg border border-line bg-surface p-4 sm:p-5"
    >
      <p className="text-small font-medium text-ink">How to read the scale</p>
      <p className="mt-1 text-caption text-ink-muted">
        Left is fear, right is greed. Today&rsquo;s read sits where the marker points.
      </p>

      <div className="relative mx-1 mb-2 mt-9">
        {hasMarker && (
          <span
            className="absolute -top-7 -translate-x-1/2 whitespace-nowrap rounded bg-navy px-2 py-0.5 text-caption font-medium text-white shadow-sm"
            style={{ left: `${pct}%` }}
          >
            {ZONE_LABELS[ord]}
          </span>
        )}
        <div className="h-2.5 rounded-full" style={{ background: GRADIENT }} />
        {hasMarker && (
          <span
            className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-navy bg-surface shadow-sm"
            style={{ left: `${pct}%` }}
            aria-hidden="true"
          />
        )}
      </div>

      <div className="mt-3 grid grid-cols-5 gap-1 text-center">
        {ZONE_LABELS.map((label, i) => (
          <span
            key={label}
            className={`text-caption leading-tight ${ord === i ? 'font-medium text-ink' : 'text-ink-muted'}`}
          >
            {label}
          </span>
        ))}
      </div>

      <p className="mt-4 text-caption text-ink-faint">
        Near the fear end, sentiment is cautious; in the middle it is balanced; near the greed end it
        is exuberant. The level is a descriptive read, not a signal to act.
      </p>
    </section>
  );
}
