/**
 * MoodMovement — COMPLIANCE-CRITICAL hero line.
 *
 * Renders how sentiment MOVED versus yesterday, using LABELS ONLY plus the
 * existing trend word:
 *
 *     Yesterday: Neutral  →  Today: Greed · trend improving
 *
 * Architecture rule "No numeric in DOM" (non-negotiable #2):
 *   Renders ONLY regime display words + the trend word. ABSOLUTELY NO number,
 *   NO percent, NO 0-100 delta. The server-side trend diff stays server-side;
 *   only its descriptive label ("improving"/"stable"/"deteriorating") is shown.
 *
 * Advisory verb ban (non-negotiable #1):
 *   Pure description of sentiment movement — no buy/sell/hold framing, no
 *   "opportunity"/"now is the time". The arrow is a neutral movement glyph.
 *
 * Safe fallbacks (mirror MoodGauge / MoodContextSection):
 *   - No meaningful yesterday → render only "Today: <regime>" (no arrow).
 *   - Out-of-enum / sentinel regimes → fall back via REGIME_DISPLAY, never a
 *     bare snake_case enum, never a throw.
 *   - trend null → omit the "· trend …" clause entirely.
 */

import * as React from 'react';
import { cn } from '@/lib/cn';
import { REGIME_DISPLAY } from '@/components/mood/MoodGauge';
import type { Regime, MoodTrend } from '@/features/mood/types';

// The five real sentiment regimes. A "yesterday" outside this set
// (insufficient_data / data_unavailable / unknown) is treated as no history,
// so we never render "Yesterday: Data Unavailable".
const MEANINGFUL_REGIMES: ReadonlySet<string> = new Set<Regime>([
  'extreme_fear',
  'fear',
  'neutral',
  'greed',
  'extreme_greed',
]);

const TREND_DISPLAY: Record<MoodTrend, string> = {
  improving: 'improving',
  stable: 'stable',
  deteriorating: 'deteriorating',
};

// Never a bare enum: fall back to the muted "Insufficient Data" word.
function regimeLabel(regime: Regime): string {
  return REGIME_DISPLAY[regime] ?? REGIME_DISPLAY.insufficient_data;
}

export interface MoodMovementProps {
  /** Today's regime — the current MoodPublic.regime. */
  todayRegime: Regime;
  /** Previous snapshot's regime, or null/undefined when no prior day exists. */
  yesterdayRegime?: Regime | null;
  /** MoodPublic.trend; clause omitted entirely when null/undefined. */
  trend?: MoodTrend | null;
  className?: string;
}

export function MoodMovement({
  todayRegime,
  yesterdayRegime,
  trend,
  className,
}: MoodMovementProps) {
  const today = regimeLabel(todayRegime);
  const hasYesterday =
    !!yesterdayRegime && MEANINGFUL_REGIMES.has(yesterdayRegime);
  const trendWord = trend ? (TREND_DISPLAY[trend] ?? null) : null;

  return (
    <p
      className={cn('text-small text-ink-secondary', className)}
      data-testid="mood-movement"
    >
      {hasYesterday && (
        <>
          <span className="text-ink-muted">Yesterday: </span>
          <span className="font-medium text-ink">
            {regimeLabel(yesterdayRegime as Regime)}
          </span>
          <span className="mx-2 text-ink-muted" aria-hidden="true">
            →
          </span>
        </>
      )}
      <span className="text-ink-muted">Today: </span>
      <span className="font-medium text-ink">{today}</span>
      {trendWord && (
        <span className="text-ink-muted"> · trend {trendWord}</span>
      )}
    </p>
  );
}
